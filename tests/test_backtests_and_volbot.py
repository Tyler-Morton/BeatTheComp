"""Champion backtest circuit breaker, and volbot's pure pieces (settlement, state file)."""
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent


def test_backtest_breaker_does_not_erase_losses(monkeypatch):
    """The breaker used to drop any day that would close >30% under the high, so
    equity could never fall below 0.70x ATH. Live, it only blocks rebalancing."""
    import backtest as bt
    n = 300
    idx = pd.bdate_range("2020-01-01", periods=n)
    qqq = 100 * np.cumprod(np.r_[1.0, np.full(n - 1, 1 - 0.004)])   # steady 70% slide
    px = pd.DataFrame({"QQQ": qqq, "SPY": qqq, "TLT": 100.0}, index=idx)
    monkeypatch.setattr(bt, "_compute_weights", lambda s, h, r: {"QQQ": 1.0})
    monkeypatch.setattr(bt, "_detect_regime_from_prices", lambda p: "RISK_ON")
    eq = bt._simulate(px, "HRP")
    assert eq.min() < 0.5


def test_backtest_no_bfill_zero_variance(monkeypatch):
    """Assets before inception must stay NaN (and out of the optimizer), not a
    backfilled flat line with zero variance."""
    import backtest as bt
    seen = []
    n = 120
    idx = pd.bdate_range("2020-01-01", periods=n)
    rng = np.random.default_rng(0)
    a = 100 * np.cumprod(1 + rng.normal(0, 0.01, n))
    late = np.r_[np.full(60, np.nan), 50 * np.cumprod(1 + rng.normal(0, 0.01, n - 60))]
    px = pd.DataFrame({"QQQ": a, "BITO": late, "SPY": a, "TLT": 100.0}, index=idx)
    monkeypatch.setattr(bt, "_compute_weights",
                        lambda s, h, r: seen.append(list(h.columns)) or {c: 1 / h.shape[1] for c in h})
    monkeypatch.setattr(bt, "_detect_regime_from_prices", lambda p: "RISK_ON")
    bt._simulate(px, "HRP")
    assert seen and all("BITO" not in cols for cols in seen)   # never a full window
    assert all(h for h in seen)


# ── volbot (retired, but its ledger math must stay right for the record) ──────

@pytest.fixture
def volbot(monkeypatch, tmp_path):
    vb = ROOT / "volbot"
    saved = sys.modules.get("config")
    spec = importlib.util.spec_from_file_location("config", vb / "config.py")
    vcfg = importlib.util.module_from_spec(spec)
    sys.modules["config"] = vcfg
    try:
        spec.loader.exec_module(vcfg)
        s2 = importlib.util.spec_from_file_location("volbot_mod", vb / "volbot.py")
        m = importlib.util.module_from_spec(s2)
        s2.loader.exec_module(m)
    finally:
        if saved is not None:
            sys.modules["config"] = saved
        else:
            sys.modules.pop("config", None)
    monkeypatch.setattr(m.C, "STATE_FILE", tmp_path / "volbot_state.json")
    return m


RUNG = dict(u="SPY", exp="2026-08-21", spk=700.0, lpk=693.0, sck=760.0, lck=767.0)


@pytest.mark.parametrize("close,expected", [(730.0, 0.0), (698.0, 2.0), (650.0, 7.0),
                                            (762.5, 2.5), (800.0, 7.0)])
def test_settle_value(volbot, close, expected):
    bars = pd.DataFrame({"SPY": [close, 999.0]},
                        index=pd.to_datetime(["2026-08-21", "2026-08-24"]))
    cost, S = volbot.settle_value(RUNG, bars)
    assert S == close and cost == pytest.approx(expected)


def test_state_roundtrip_atomic(volbot):
    st = {"rungs": [dict(RUNG, qty=1, credit=0.5, maxloss=6.5)], "last_entry": {"SPY": "2026-07-27"}}
    volbot.save_state(st)
    assert volbot.load_state() == st
    assert not volbot.C.STATE_FILE.with_suffix(".tmp").exists()
    assert json.loads(volbot.C.STATE_FILE.read_text()) == st
