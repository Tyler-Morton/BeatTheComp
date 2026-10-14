"""Drawdown breaker: de-risk-only mode, broker-equity HWM, recovery, N-session reset.

Fully offline. No Alpaca client is ever built: broker functions are faked and the
production breaker_state.csv / daily_log.csv / alerts.log are never touched.
"""
from types import SimpleNamespace as NS

import pandas as pd
import pytest

import broker
import config
import risk

TRIP = 1 - config.DRAWDOWN_CIRCUIT_BREAKER     # 0.70
N = config.BREAKER_RESET_SESSIONS               # 63


class _NoBroker:
    def __getattr__(self, name):
        raise RuntimeError(f"broker.{name} called in a unit test")


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    """Point every file the breaker reads/writes at tmp, and drop email creds."""
    monkeypatch.setattr(risk, "ALERTS_LOG", tmp_path / "alerts.log")
    monkeypatch.setattr(risk, "BREAKER_STATE_FILE", tmp_path / "breaker_state.csv")
    monkeypatch.setattr(risk, "DAILY_LOG", tmp_path / "daily_log.csv")
    monkeypatch.delenv("EMAIL_USER", raising=False)
    monkeypatch.delenv("EMAIL_PASS", raising=False)
    # Any use of a broker client a test didn't explicitly fake fails loudly.
    monkeypatch.setattr(broker, "_client", _NoBroker())
    return tmp_path


def _day(i: int) -> str:
    return str((pd.Timestamp("2026-01-05") + pd.offsets.BDay(i)).date())


# ── high-water mark + seeding ──────────────────────────────────────────────────

def test_seed_uses_max_of_daily_log_and_broker_history(_isolate):
    pd.DataFrame({"portfolio_value": [1000.0, 1118.13, 950.0]}).to_csv(
        _isolate / "daily_log.csv", index=False)
    b = risk.update_breaker(920.0, today=_day(0), history_fn=lambda: [900, 1147.80, None, 0])
    assert b["hwm"] == pytest.approx(1147.80)
    assert not b["in_breaker"] and b["event"] == "ok"
    # persisted: a second call with no history_fn keeps the broker peak
    b2 = risk.update_breaker(925.0, today=_day(1))
    assert b2["hwm"] == pytest.approx(1147.80)


def test_history_failure_falls_back_to_daily_log(_isolate):
    pd.DataFrame({"portfolio_value": [1000.0]}).to_csv(_isolate / "daily_log.csv", index=False)
    def boom():
        raise ConnectionError("down")
    b = risk.update_breaker(990.0, today=_day(0), history_fn=boom)
    assert b["hwm"] == pytest.approx(1000.0)


def test_hwm_ratchets_up_on_new_highs():
    risk.update_breaker(1000.0, today=_day(0))
    b = risk.update_breaker(1100.0, today=_day(1))
    assert b["hwm"] == pytest.approx(1100.0)
    b = risk.update_breaker(1050.0, today=_day(2))
    assert b["hwm"] == pytest.approx(1100.0)


def test_state_write_is_atomic_and_leaves_no_temp_files(_isolate):
    risk.update_breaker(1000.0, today=_day(0))
    files = sorted(p.name for p in _isolate.iterdir())
    assert "breaker_state.csv" in files
    assert not [f for f in files if f.endswith(".tmp")]


# ── trip / de-risk / recovery / reset ──────────────────────────────────────────

def test_trip_enters_breaker_and_alerts(_isolate):
    risk.update_breaker(1000.0, today=_day(0))
    b = risk.update_breaker(TRIP * 1000 - 1, today=_day(1))
    assert b["in_breaker"] and b["event"] == "tripped" and b["sessions"] == 1
    assert "BREAKER de-risk only" in b["note"]
    assert "Drawdown circuit breaker" in (_isolate / "alerts.log").read_text()


def test_just_above_trip_does_not_trip():
    risk.update_breaker(1000.0, today=_day(0))
    assert not risk.update_breaker(TRIP * 1000 + 1, today=_day(1))["in_breaker"]


def test_recovery_above_trip_level_exits_breaker(_isolate):
    risk.update_breaker(1000.0, today=_day(0))
    risk.update_breaker(650.0, today=_day(1))
    b = risk.update_breaker(680.0, today=_day(2))
    assert b["in_breaker"] and b["event"] == "derisk" and b["sessions"] == 2
    b = risk.update_breaker(TRIP * 1000 + 0.01, today=_day(3))
    assert not b["in_breaker"] and b["event"] == "recovered" and b["sessions"] == 0
    assert b["hwm"] == pytest.approx(1000.0)   # HWM unchanged by a recovery
    assert "RELEASED" in (_isolate / "alerts.log").read_text()


def test_reset_after_n_sessions_rebases_hwm(_isolate):
    risk.update_breaker(1000.0, today=_day(0))
    for i in range(1, N + 1):                      # N de-risk sessions
        b = risk.update_breaker(600.0, today=_day(i))
        assert b["in_breaker"], i
    assert b["sessions"] == N
    b = risk.update_breaker(590.0, today=_day(N + 1))   # session N+1: reset
    assert b["event"] == "reset" and not b["in_breaker"]
    assert b["hwm"] == pytest.approx(590.0)
    assert "RESET" in (_isolate / "alerts.log").read_text()
    # the new reference is live: a further 30% fall from 590 trips again
    assert risk.update_breaker(590 * TRIP - 1, today=_day(N + 2))["event"] == "tripped"


def test_same_day_rerun_does_not_count_a_session():
    risk.update_breaker(1000.0, today=_day(0))
    risk.update_breaker(600.0, today=_day(1))
    b = risk.update_breaker(600.0, today=_day(1))
    assert b["in_breaker"] and b["sessions"] == 1


# ── bad-read guard ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("bad", [0.0, -5.0, 0.30, float("nan")])
def test_bad_read_neither_trips_nor_changes_state(bad, _isolate):
    risk.update_breaker(1000.0, today=_day(0))
    before = (_isolate / "breaker_state.csv").read_text()
    b = risk.update_breaker(bad, today=_day(1))
    assert b["event"] == "bad_read" and not b["in_breaker"]
    assert (_isolate / "breaker_state.csv").read_text() == before


def test_bad_read_while_in_breaker_stays_in_breaker():
    risk.update_breaker(1000.0, today=_day(0))
    risk.update_breaker(600.0, today=_day(1))
    b = risk.update_breaker(0.30, today=_day(2))
    assert b["in_breaker"] and b["event"] == "bad_read" and b["sessions"] == 1


def test_drawdown_no_longer_blocks_run_all_checks(asset_returns):
    # The breaker is not an all-or-nothing gate any more; the other checks still are.
    ok, fails = risk.run_all_checks(1.0, asset_returns[["SHV"]], {"SHV": 1.0})
    assert ok and fails == []


# ── de-risk targets ────────────────────────────────────────────────────────────

def test_derisk_targets_only_reduce_risk():
    current = {"TQQQ": 0.40, "SOXL": 0.20, "GLD": 0.10, "SHV": 0.25}   # 5% cash
    target = {"TQQQ": 0.30, "SOXL": 0.35, "UPRO": 0.20, "SHV": 0.15}
    d = risk.derisk_targets(current, target, "SHV")
    assert d["TQQQ"] == pytest.approx(0.30)          # reduced toward target
    assert d["SOXL"] == pytest.approx(0.20)          # increase blocked
    assert "UPRO" not in d and "GLD" not in d        # no new buy; exit allowed
    for sym, w in d.items():
        if sym != "SHV":
            assert w <= current.get(sym, 0.0) + 1e-12
    risky_before = sum(w for s, w in current.items() if s != "SHV")
    risky_after = sum(w for s, w in d.items() if s != "SHV")
    assert risky_after <= risky_before
    assert d["SHV"] == pytest.approx(0.50) and sum(d.values()) == pytest.approx(1.0)


# ── broker: buy allow-list (fake client, no network) ───────────────────────────

class FakeTC:
    def __init__(self, equity, cash, positions):
        self.equity, self.cash = equity, cash
        self.positions = positions
        self.orders, self.closed = [], []

    def get_account(self):
        return NS(equity=self.equity, cash=self.cash, buying_power=self.cash)

    def get_all_positions(self):
        return [NS(symbol=s, market_value=mv, qty=q) for s, (mv, q) in self.positions.items()]

    def get_asset(self, sym):
        return NS(fractionable=True)

    def submit_order(self, req):
        self.orders.append(req)
        if "SELL" in str(req.side).upper():
            self.cash += float(req.notional)
        return NS(id=f"o{len(self.orders)}")

    def close_position(self, sym):
        self.closed.append(sym)
        self.cash += self.positions[sym][0]
        return NS(id=f"c{sym}")

    def get_order_by_id(self, oid):
        return NS(status="OrderStatus.FILLED")


def test_breaker_rebalance_places_only_sells_and_cash_buys(monkeypatch):
    tc = FakeTC(1000.0, 50.0, {"TQQQ": (400.0, 4.0), "SOXL": (200.0, 2.0),
                               "GLD": (100.0, 1.0), "SHV": (250.0, 2.5)})
    monkeypatch.setattr(broker, "_client", tc)
    broker._fractionable_cache.clear()
    current = {s: mv / 1000.0 for s, (mv, _) in tc.positions.items()}
    target = {"TQQQ": 0.30, "SOXL": 0.35, "UPRO": 0.20, "SHV": 0.15}
    d = risk.derisk_targets(current, target, "SHV")
    # Even if prices drifted and a risky diff looked like a buy, the allow-list holds:
    d["SOXL"] = 0.30
    broker.rebalance(d, buy_only={"SHV"})
    buys = [o for o in tc.orders if "BUY" in str(o.side).upper()]
    assert buys and {o.symbol for o in buys} == {"SHV"}
    assert "GLD" in tc.closed
    sells = [o for o in tc.orders if "SELL" in str(o.side).upper()]
    assert {o.symbol for o in sells} == {"TQQQ"}


def test_rebalance_without_allowlist_is_unchanged(monkeypatch):
    tc = FakeTC(1000.0, 1000.0, {})
    monkeypatch.setattr(broker, "_client", tc)
    broker._fractionable_cache.clear()
    broker.rebalance({"QQQ": 1.0})
    assert [o.symbol for o in tc.orders] == ["QQQ"]


# ── main.py wiring: breaker day trades de-risk only, then exits 2 ──────────────

def _stub_pipeline(monkeypatch, tmp_path, equity, positions, target):
    import alpha_sleeve
    import data
    import main
    import sentiment
    import watchlist
    idx = pd.bdate_range("2026-01-01", periods=30)
    prices = pd.DataFrame({t: 100.0 for t in config.ASSETS + ["SPY", "TLT"]}, index=idx)
    monkeypatch.setattr(main, "DAILY_LOG", tmp_path / "daily_log.csv")
    monkeypatch.setattr(main, "_already_ran_today", lambda: False)
    monkeypatch.setattr(main, "fetch_prices", lambda *a, **k: prices)
    monkeypatch.setattr(main, "get_returns", lambda p: p.pct_change().fillna(0.0))
    monkeypatch.setattr(main, "detect_regime", lambda *a: "RISK_ON")
    monkeypatch.setattr(main, "select_strategy", lambda *a, **k: "HRP_MOMENTUM")
    monkeypatch.setattr(main, "optimize", lambda **k: {
        "weights": dict(target), "sharpe_ratio": 1.0,
        "expected_annual_return": 0.1, "annual_volatility": 0.2})
    monkeypatch.setattr(main, "run_all_checks", lambda *a: (True, []))
    monkeypatch.setattr(main, "TRENDING_DISCOVERY_ENABLED", False)
    monkeypatch.setattr(config, "RISK_OVERLAY_ENABLED", False)
    monkeypatch.setattr(data, "save_price_cache", lambda p: None)
    monkeypatch.setattr(sentiment, "run_sentiment_analysis", lambda t: {})
    monkeypatch.setattr(watchlist, "scan_watchlist", lambda t: [])
    monkeypatch.setattr(alpha_sleeve, "merge_with_etf_weights", lambda w, d: w)
    calls = {}
    monkeypatch.setattr(broker, "is_market_open", lambda: True)
    monkeypatch.setattr(broker, "get_portfolio_value", lambda: equity)
    monkeypatch.setattr(broker, "get_current_positions", lambda: dict(positions))
    monkeypatch.setattr(broker, "get_account_history",
                        lambda days=365: pd.DataFrame({"equity": [1000.0]}))
    monkeypatch.setattr(broker, "rebalance",
                        lambda w, buy_only=None: calls.update(w=w, buy_only=buy_only) or [])
    monkeypatch.setattr(broker, "sweep_idle_cash", lambda: None)
    return main, calls


def test_main_breaker_day_derisks_and_exits_2(monkeypatch, _isolate):
    positions = {"TQQQ": 0.5, "SOXL": 0.2, "SHV": 0.3}
    target = {"TQQQ": 0.3, "SOXL": 0.4, "UPRO": 0.2, "SHV": 0.1}
    main, calls = _stub_pipeline(monkeypatch, _isolate, 650.0, positions, target)
    assert main.main() == 2                     # HWM seeded $1000 -> $650 is -35%
    assert calls["buy_only"] == {"SHV"}
    w = calls["w"]
    assert w["TQQQ"] == pytest.approx(0.3) and w["SOXL"] == pytest.approx(0.2)
    assert "UPRO" not in w and w["SHV"] == pytest.approx(0.5)
    notes = pd.read_csv(_isolate / "daily_log.csv")["notes"].iloc[-1]
    assert "BREAKER de-risk only" in notes


def test_main_normal_day_unchanged(monkeypatch, _isolate):
    positions = {"TQQQ": 0.5, "SHV": 0.5}
    target = {"TQQQ": 0.3, "UPRO": 0.2, "SHV": 0.5}
    main, calls = _stub_pipeline(monkeypatch, _isolate, 990.0, positions, target)
    assert main.main() is None
    assert calls["buy_only"] is None and calls["w"] == target
