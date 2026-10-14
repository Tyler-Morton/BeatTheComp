"""Challenger: target-weight math, monthly freeze timing, pinned estimator, backtest causality."""
import importlib
import json
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

CH = Path(__file__).resolve().parent.parent / "challenger"


@pytest.fixture
def chmain(monkeypatch):
    for k in ("ALPACA_API_KEY", "ALPACA_SECRET_KEY"):
        monkeypatch.setenv(k, "unused")          # main.py overwrites these; restore after
    monkeypatch.setenv("CHALLENGER_ALPACA_API_KEY", "test-not-a-key")
    monkeypatch.setenv("CHALLENGER_ALPACA_SECRET_KEY", "test-not-a-key")
    monkeypatch.syspath_prepend(str(CH))
    sys.modules.pop("challenger_main", None)
    spec = importlib.util.spec_from_file_location("challenger_main", CH / "main.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


@pytest.fixture
def chbt(monkeypatch):
    monkeypatch.syspath_prepend(str(CH))
    spec = importlib.util.spec_from_file_location("challenger_backtest", CH / "backtest.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_target_weights_sum_to_one_and_fold_crumbs(chmain):
    base = {"QQQ": 0.45, "XLP": 0.004, "TLT": 0.30, "GLD": 0.246}
    w = chmain.target_weights(base, 0.5)
    assert sum(w.values()) == pytest.approx(1.0, abs=1e-3)
    assert "XLP" not in w                                   # 0.002 after scaling -> crumb
    assert w["SHV"] == pytest.approx(0.5 + 0.002, abs=1e-4)
    assert all(v >= chmain.MIN_WEIGHT for k, v in w.items() if k != "SHV")


def test_target_weights_unscaled_has_no_cash_when_none_needed(chmain):
    w = chmain.target_weights({"QQQ": 0.5, "TLT": 0.5}, 1.0)
    assert w == {"QQQ": 0.5, "TLT": 0.5}


def _px(last):
    idx = pd.bdate_range(end=last, periods=300)
    return pd.DataFrame({t: np.linspace(100, 120, 300) for t in
                         ["QQQ", "QLD", "IEF", "XLP", "XLU", "XLV", "TLT", "GLD", "SHV"]}, index=idx)


def test_monthly_base_recomputes_on_first_trading_day_of_month(chmain, tmp_path, monkeypatch):
    state = tmp_path / "base_state.json"
    monkeypatch.setattr(chmain, "BASE_STATE", state)
    state.write_text(json.dumps({"month": "2026-10", "base": {"STALE": 1.0}}))
    # Run on Mon 2026-11-02: newest close is Fri 2026-10-30 (the BME close).
    base = chmain.monthly_base(_px("2026-10-30"), today=date(2026, 11, 2))
    assert "STALE" not in base
    st = json.loads(state.read_text())
    assert st["month"] == "2026-11" and st["computed_on"] == "2026-10-30"
    assert not state.with_suffix(".tmp").exists()


def test_monthly_base_reused_within_month(chmain, tmp_path, monkeypatch):
    state = tmp_path / "base_state.json"
    monkeypatch.setattr(chmain, "BASE_STATE", state)
    state.write_text(json.dumps({"month": "2026-10", "base": {"KEEP": 1.0}}))
    assert chmain.monthly_base(_px("2026-10-14"), today=date(2026, 10, 15)) == {"KEEP": 1.0}


def test_challenger_pins_its_vol_estimator(chmain, chbt, monkeypatch):
    """A champion OVERLAY_VOL_MODEL change must not leak into the challenger."""
    import sleeves
    assert sleeves.VOL_MODEL == "trailing"
    seen = []
    monkeypatch.setattr(chbt, "vol_target_scaler",
                        lambda *a, **k: seen.append(k.get("model")) or 1.0)
    monkeypatch.setattr(chbt, "combined_weights", lambda px, b=None: {"QQQ": 1.0})
    chbt.run_book(_px("2026-10-30"), {"core": 1.0}, 0.16)
    assert seen and set(seen) == {"trailing"}
    src = (CH / "main.py").read_text()
    assert "model=VOL_MODEL" in src


def test_backtest_has_no_same_bar_lookahead(chbt, monkeypatch):
    """Scaler that 'knows' today's return: full size on up days, flat on down days.
    With look-ahead it books every up day and dodges every down day. Causally it
    is always one day late on an alternating series, so it must lose."""
    n = 400
    idx = pd.bdate_range("2015-01-01", periods=n)
    rets = np.where(np.arange(n) % 2 == 0, 0.01, -0.01)
    px = pd.DataFrame({"X": 100 * np.cumprod(1 + rets)}, index=idx)
    monkeypatch.setattr(chbt, "TCOST", 0.0)
    monkeypatch.setattr(chbt, "CASH_YIELD", 0.0)
    monkeypatch.setattr(chbt, "combined_weights", lambda p, b=None: {"X": 1.0})
    monkeypatch.setattr(chbt, "DRIFT", 0.0)
    monkeypatch.setattr(chbt, "vol_target_scaler",
                        lambda dr, w, tv, model=None: 1.0 if dr["X"].iloc[-1] > 0 else 0.0)
    out = chbt.run_book(px, {"core": 1.0}, 0.16)
    assert out.iloc[261:].sum() < 0
