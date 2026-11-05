"""Tests for the risk overlay and the concentration check. Plain asserts, no pytest needed.

Run: python3 test_risk_overlay.py
"""

import os
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

import config
import risk
import risk_overlay as ro
from risk import check_concentration

# A tripped check calls risk._alert, which appends to the real alerts.log and emails if
# EMAIL_USER and EMAIL_PASS are set. Without this redirect, every local run of the TQQQ 78%
# case below wrote a concentration breach into the real log, where it looks like a live breach.
# Tests must never write to the live alert channel.
_PROD_ALERTS_LOG = Path(config.ALERTS_LOG)
risk.ALERTS_LOG = Path(tempfile.gettempdir()) / "test_risk_overlay_alerts.log"
os.environ.pop("EMAIL_USER", None)
os.environ.pop("EMAIL_PASS", None)


def _synthetic_returns(vol_annual: float, n: int = 120, cols=("TQQQ", "SOXL", "TECL")):
    """Builds a returns frame where each asset's vol is about vol_annual."""
    rng = np.random.default_rng(0)
    daily = vol_annual / np.sqrt(252)
    idx = pd.date_range("2025-01-01", periods=n, freq="B")
    data = {c: rng.normal(0.0003, daily, n) for c in cols}
    return pd.DataFrame(data, index=idx)


def test_portfolio_vol_reasonable():
    # A single 50% vol asset has about 50% portfolio vol, with nothing to diversify it.
    rets = _synthetic_returns(0.50, cols=("TQQQ",))
    pv = ro.portfolio_vol(rets, {"TQQQ": 1.0})
    assert 0.35 < pv < 0.65, f"portfolio vol off: {pv}"
    print(f"  portfolio_vol is about {pv:.1%} for a single ~50% asset")


def test_scaler_caps_at_one_when_calm():
    # A low-vol book shouldn't lever up, so the scaler stays at 1.0.
    rets = _synthetic_returns(0.10)
    w = {"TQQQ": 1.0}
    s = ro.vol_target_scaler(rets, w, target_vol=0.20)
    assert s == 1.0, f"expected 1.0 cap, got {s}"
    print("  calm book: scaler capped at 1.0")


def test_scaler_cuts_when_wild():
    # With a single ~60% vol asset, a 20% target should cut to roughly 0.20/0.55, about 0.36.
    rets = _synthetic_returns(0.60, cols=("TQQQ",))
    s = ro.vol_target_scaler(rets, {"TQQQ": 1.0}, target_vol=0.20)
    assert 0.2 < s < 0.6, f"expected meaningful cut, got {s}"
    print(f"  wild book: scaler cuts to {s:.2f}")


def test_apply_overlay_parks_cash_and_sums_to_one():
    # With a single ~60% vol asset, a 20% target forces a big cut, about 2/3 parked in cash.
    # There's no diversification to muddy the math.
    rets = _synthetic_returns(0.60, cols=("TQQQ",))
    w = {"TQQQ": 1.0}
    new_w, info = ro.apply_overlay(w, rets, target_vol=0.20, use_ml=False)
    total = sum(new_w.values())
    assert abs(total - 1.0) < 1e-6, f"weights should sum to 1, got {total}"
    assert new_w.get("SHV", 0) > 0.2, "expected a meaningful cash park"
    assert info["combined_scaler"] < 1.0
    print(f"  overlay sums to 1.0, parked {new_w['SHV']:.0%} in SHV")


def test_ml_disabled_is_noop_scaler():
    rets = _synthetic_returns(0.60)
    w = {"TQQQ": 1.0}
    _, info = ro.apply_overlay(w, rets, use_ml=False)
    assert info["ml_scaler"] == 1.0 and info["crash_prob"] is None
    print("  ML disabled: neutral 1.0, no crash prob")


def test_ml_graceful_on_bad_input():
    # No usable price data has to return neutral and never raise.
    mult, p = ro.ml_crash_multiplier(pd.DataFrame({"SPY": [1, 2, 3]}))
    assert mult == 1.0 and p is None
    print("  ML returns neutral 1.0 on bad input")


def test_empty_weights_safe():
    rets = _synthetic_returns(0.40)
    assert ro.portfolio_vol(rets, {}) == 0.0
    assert ro.vol_target_scaler(rets, {}) == 1.0
    print("  empty weights return 0 vol and a 1.0 scaler")


def test_concentration_exempts_cash():
    # SHV at 78% must not trip the cap, but a 78% stock must.
    ok, _ = check_concentration({"SHV": 0.78, "TQQQ": 0.22})
    assert ok, "cash park should be exempt from concentration cap"
    bad, _ = check_concentration({"TQQQ": 0.78, "SHV": 0.22})
    assert not bad, "a 78% stock should still trip the cap"
    print("  concentration check exempts SHV cash and still catches a 78% stock")


def test_tripped_checks_do_not_touch_production_alert_log():
    def _stat(p):
        return (p.stat().st_size, p.stat().st_mtime_ns) if p.exists() else None
    before = _stat(_PROD_ALERTS_LOG)
    bad, _ = check_concentration({"TQQQ": 0.78, "SHV": 0.22})
    assert not bad
    assert _stat(_PROD_ALERTS_LOG) == before, "a unit test wrote the live alerts.log"
    assert risk.ALERTS_LOG != _PROD_ALERTS_LOG
    print("  tripped checks write a temp alert log, not the production one")


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    print(f"Running {len(tests)} risk-overlay tests...\n")
    for t in tests:
        t()
    print(f"\nAll {len(tests)} tests passed.")
