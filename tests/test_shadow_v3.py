"""V3 paper shadow (shadow_v3.py): read-only, monthly re-decision, 30% 3x cap.

All offline. The two guarantees Tyler asked for are tested directly:
  * the shadow never touches the broker (no order calls, no attribute access at all);
  * the champion's targets are byte-identical with and without the shadow imported/run.
"""
import ast
import csv
import json
import subprocess
import sys
import types
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import shadow_v3
from config import ASSETS

ROOT = Path(__file__).resolve().parent.parent
LEV = shadow_v3.LEV


def _prices(end="2026-10-30", n=300, seed=3) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range(end=end, periods=n)
    common = rng.normal(0.0008, 0.007, n)
    data = {}
    for t in list(dict.fromkeys(ASSETS + ["SPY", "TLT"])):
        lev = 3.0 if t in LEV else 1.0
        beta = 0.0 if t in ("SHV", "TLT", "GLD") else lev
        vol = 0.0003 if t == "SHV" else 0.004 * lev
        data[t] = 100 * np.cumprod(1 + beta * common + rng.normal(0.0002, vol, n))
    return pd.DataFrame(data, index=idx)


@pytest.fixture
def heavy_3x_decision(monkeypatch):
    """Pin the monthly decision to a 3x-heavy book so the cap has to bind."""
    calls = []
    B = {"TQQQ": 0.35, "TECL": 0.35, "VGT": 0.20, "SHV": 0.10}

    def fake(prices):
        calls.append(prices.index[-1])
        return "RISK_ON", "HRP_MOMENTUM", dict(B)
    monkeypatch.setattr(shadow_v3, "base_decision", fake)
    return calls


def _write_daily_log(path: Path, days, value=1000.0):
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date", "strategy", "regime", "portfolio_value"])
        for d in days:
            w.writerow([str(d), "HRP_MOMENTUM", "RISK_ON", value])


def _run_sessions(tmp_path, prices, sessions, **kw):
    """Drive shadow_v3.run() through `sessions`, feeding the cache the closes through D−1."""
    out = []
    daily = tmp_path / "daily_log.csv"
    _write_daily_log(daily, sessions)
    for d in sessions:
        cache = tmp_path / "prices_cache.parquet"
        prices[prices.index.date < d].to_parquet(cache)
        out.append(shadow_v3.run(d, state_path=tmp_path / "state.json",
                                 log_path=tmp_path / "log.csv", price_cache=cache,
                                 daily_log=daily, **kw))
    return out


def _rows(tmp_path):
    with open(tmp_path / "log.csv", newline="") as f:
        return list(csv.DictReader(f))


# ── V3 rules ──────────────────────────────────────────────────────────────────

def test_cap_binds_and_excess_goes_to_shv(asset_returns):
    B = {"TQQQ": 0.30, "UPRO": 0.20, "TECL": 0.20, "VGT": 0.25, "SHV": 0.05}
    s, pre, post, T = shadow_v3.final_target(B, asset_returns)
    assert pre > 0.30                                     # overlay alone leaves > 30% 3x
    assert post <= 0.30 + 1e-12
    assert sum(T.values()) == pytest.approx(1.0, abs=1e-9)
    # ratios inside the 3x sleeve are preserved by the proportional cap
    assert T["TQQQ"] / T["UPRO"] == pytest.approx(1.5)
    # the non-3x, non-cash names are untouched by the cap (only the overlay scales them)
    assert T["VGT"] == pytest.approx(0.25 * s)


def test_cap_does_not_touch_book_under_30pct(asset_returns):
    B = {"TQQQ": 0.05, "VGT": 0.60, "GLD": 0.35}
    s, pre, post, T = shadow_v3.final_target(B, asset_returns)
    assert pre <= 0.30 and post == pytest.approx(pre)
    assert T["VGT"] == pytest.approx(0.60 * s)


def test_crumbs_fold_into_shv_after_cap(asset_returns):
    B = {"TQQQ": 0.003, "VGT": 0.597, "GLD": 0.40}
    _, _, _, T = shadow_v3.final_target(B, asset_returns)
    assert "TQQQ" not in T and sum(T.values()) == pytest.approx(1.0)


def test_redecides_only_on_first_session_of_month(tmp_path, heavy_3x_decision):
    prices = _prices(end="2026-11-06")
    sessions = [d.date() for d in prices.index[-12:]]         # spans Oct → Nov
    statuses = _run_sessions(tmp_path, prices, sessions)
    assert statuses == ["logged"] * len(sessions)
    rows = _rows(tmp_path)
    redecided = [r["date"] for r in rows if r["redecided"] == "1"]
    first_nov = next(str(d) for d in sessions if d.month == 11)
    assert redecided == [str(sessions[0]), first_nov]
    assert len(heavy_3x_decision) == 2
    # every decision used closes through the PRIOR session only
    for (d, used) in zip([sessions[0], date.fromisoformat(first_nov)], heavy_3x_decision):
        assert used.date() < d
    # scaler, cap and gates still ran every day
    assert all(r["scaler"] != "" for r in rows)
    assert all(float(r["w3x_post_cap"]) <= 0.30 + 1e-9 for r in rows)
    assert all(float(r["w3x_pre_cap"]) > 0.30 for r in rows)


def test_regime_matches_live_detect_regime(monkeypatch):
    import regime
    monkeypatch.setattr(regime, "_log_regime", lambda *a, **k: None)
    for seed in range(5):
        p = _prices(seed=seed)
        assert shadow_v3.regime_from_prices(p) == regime.detect_regime(p["SPY"], p["TLT"])


# ── Accounting ────────────────────────────────────────────────────────────────

def test_first_day_starts_at_champion_equity_in_shv_and_trades_in(tmp_path, heavy_3x_decision):
    prices = _prices()
    d0 = prices.index[-1].date()
    state, row = shadow_v3.step(None, prices.iloc[:-1], d0, 912.34)
    assert row["shadow_equity"] == 912.34 and row["champion_equity"] == 912.34
    assert row["traded"] == 1
    T = json.loads(row["target_weights"])
    expected_turnover = sum(abs(T.get(k, 0) - (1.0 if k == "SHV" else 0.0))
                            for k in set(T) | {"SHV"})
    assert row["turnover"] == pytest.approx(expected_turnover, abs=1e-6)
    assert state["pending_cost"] == pytest.approx(0.0005 * expected_turnover, abs=1e-9)


def test_equity_marks_held_book_and_books_5bp_cost(tmp_path, heavy_3x_decision):
    prices = _prices()
    d0, d1 = prices.index[-2].date(), prices.index[-1].date()
    s0, r0 = shadow_v3.step(None, prices.iloc[:-2], d0, 1000.0)
    held, cost = dict(s0["held"]), s0["pending_cost"]
    s1, r1 = shadow_v3.step(s0, prices.iloc[:-1], d1, 1000.0)
    r = prices.iloc[-2] / prices.iloc[-3] - 1                  # close(d0−1) → close(d0)
    g = sum(w * r[k] for k, w in held.items())
    assert s1["equity"] == pytest.approx(1000.0 * (1 + g - cost), rel=1e-12)
    assert r1["marked_through"] == str(prices.index[-2].date())
    assert s0["held"] == held                                  # step() never mutates its input


def test_risk_gate_blocks_on_shadow_drawdown(asset_returns):
    T = {"VGT": 0.5, "SHV": 0.5}
    assert "drawdown" in shadow_v3.risk_gate(T, asset_returns, equity=60.0, ath=100.0)
    assert "drawdown" not in shadow_v3.risk_gate(T, asset_returns, equity=80.0, ath=100.0)
    assert "concentration" in shadow_v3.risk_gate({"TQQQ": 0.8, "SHV": 0.2}, asset_returns,
                                                  100.0, 100.0)


# ── Run-level behaviour ───────────────────────────────────────────────────────

def test_idempotent_and_atomic(tmp_path, heavy_3x_decision):
    prices = _prices()
    d = prices.index[-1].date()
    _run_sessions(tmp_path, prices, [d])
    again = shadow_v3.run(d, state_path=tmp_path / "state.json", log_path=tmp_path / "log.csv",
                          price_cache=tmp_path / "prices_cache.parquet",
                          daily_log=tmp_path / "daily_log.csv")
    assert again == "already_ran"
    assert len(_rows(tmp_path)) == 1
    assert json.loads((tmp_path / "state.json").read_text())["last_run_date"] == str(d)
    assert not list(tmp_path.glob("*.tmp"))
    assert list(_rows(tmp_path)[0].keys()) == shadow_v3.LOG_FIELDS


def test_skips_when_champion_did_not_run_today(tmp_path):
    prices = _prices()
    d = prices.index[-1].date()
    prices.iloc[:-1].to_parquet(tmp_path / "p.parquet")
    _write_daily_log(tmp_path / "daily.csv", [prices.index[-2].date()])
    status = shadow_v3.run(d, state_path=tmp_path / "s.json", log_path=tmp_path / "l.csv",
                           price_cache=tmp_path / "p.parquet", daily_log=tmp_path / "daily.csv")
    assert status == "no_champion_row"
    assert not (tmp_path / "s.json").exists() and not (tmp_path / "l.csv").exists()


def test_ignores_any_price_row_dated_today(tmp_path, heavy_3x_decision):
    prices = _prices()
    d = prices.index[-1].date()
    prices.to_parquet(tmp_path / "p.parquet")                 # includes a row for D itself
    _write_daily_log(tmp_path / "daily.csv", [d])
    shadow_v3.run(d, state_path=tmp_path / "s.json", log_path=tmp_path / "l.csv",
                  price_cache=tmp_path / "p.parquet", daily_log=tmp_path / "daily.csv")
    assert heavy_3x_decision[0].date() < d


# ── Read-only guarantees ──────────────────────────────────────────────────────

class _BrokerTripwire(types.ModuleType):
    """A stand-in `broker` module that records ANY attribute access."""
    def __init__(self):
        super().__init__("broker")
        object.__setattr__(self, "touched", [])

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        self.touched.append(name)
        raise AssertionError(f"shadow_v3 touched broker.{name}")


def test_never_calls_the_broker(tmp_path, monkeypatch):
    trip = _BrokerTripwire()
    monkeypatch.setitem(sys.modules, "broker", trip)
    order_calls = []
    try:
        from alpaca.trading.client import TradingClient
        for meth in ("submit_order", "close_position", "close_all_positions",
                     "cancel_orders", "replace_order_by_id"):
            if hasattr(TradingClient, meth):
                monkeypatch.setattr(TradingClient, meth,
                                    lambda *a, _m=meth, **k: order_calls.append(_m))
        monkeypatch.setattr(TradingClient, "__init__",
                            lambda *a, **k: order_calls.append("TradingClient()"))
    except ImportError:
        pass
    prices = _prices(end="2026-11-06")
    sessions = [d.date() for d in prices.index[-10:]]
    # the real decision path (regime → select_strategy → optimize), not a stub
    assert _run_sessions(tmp_path, prices, sessions) == ["logged"] * len(sessions)
    assert trip.touched == []
    assert order_calls == []


def test_source_never_imports_broker_or_trading_clients():
    tree = ast.parse((ROOT / "shadow_v3.py").read_text())
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    banned = {m for m in imported if m.split(".")[0] in ("broker", "alpaca", "requests",
                                                          "yfinance", "risk", "main")}
    assert banned == set(), banned
    called = {n.func.id if isinstance(n.func, ast.Name) else getattr(n.func, "attr", None)
              for n in ast.walk(tree) if isinstance(n, ast.Call)}
    forbidden = {"detect_regime", "run_all_checks", "rebalance", "submit_order",
                 "sweep_idle_cash", "save_price_cache", "fetch_prices", "_alert"}
    assert called & forbidden == set()


def test_writes_nothing_outside_its_own_files(tmp_path, heavy_3x_decision):
    before = {p.name: p.stat().st_mtime_ns for p in ROOT.iterdir() if p.is_file()}
    prices = _prices()
    _run_sessions(tmp_path, prices, [d.date() for d in prices.index[-3:]])
    after = {p.name: p.stat().st_mtime_ns for p in ROOT.iterdir() if p.is_file()}
    assert after == before
    assert sorted(p.name for p in tmp_path.iterdir()) == sorted(
        ["daily_log.csv", "log.csv", "prices_cache.parquet", "state.json"])


def test_champion_targets_identical_with_and_without_shadow():
    """main.main() in a fresh interpreter, with and without shadow_v3 imported and run first.
    The targets handed to broker.rebalance must match byte for byte."""
    harness = ROOT / "tests" / "champion_harness.py"
    outs = []
    for args in ([], ["--with-shadow"]):
        p = subprocess.run([sys.executable, str(harness), *args], capture_output=True,
                           text=True, cwd=ROOT, timeout=300)
        assert p.returncode == 0, p.stderr[-2000:]
        outs.append(p.stdout)
    assert outs[0].strip() not in ("", "null")
    assert outs[0] == outs[1]
