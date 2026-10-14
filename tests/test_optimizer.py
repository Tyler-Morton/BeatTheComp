"""Core optimizer math: weights sum, bounds, stats ordering, strategy selector."""
import numpy as np
import pandas as pd
import pytest

import optimizer as opt
from config import MAX_SINGLE_WEIGHT

STRATS = ["MAX_SHARPE", "HRP", "HRP_MOMENTUM"]
REGIMES = ["RISK_ON", "CHOPPY", "RISK_OFF"]


@pytest.mark.parametrize("strategy", STRATS)
@pytest.mark.parametrize("regime", REGIMES)
def test_weights_sum_to_one_and_respect_bounds(asset_returns, strategy, regime):
    res = opt.optimize(strategy=strategy, returns=asset_returns, regime=regime)
    w = pd.Series(res["weights"])
    assert abs(w.sum() - 1.0) < 1e-4
    assert (w >= -1e-6).all()
    bounds = opt._apply_regime_bounds(list(asset_returns.columns),
                                      opt._base_bounds(asset_returns.shape[1]), regime)
    for t, (lo, hi) in zip(asset_returns.columns, bounds):
        assert w[t] <= hi + 1e-4, f"{t} {w[t]} > {hi}"
        if strategy != "HRP_MOMENTUM" or lo == 0:
            assert w[t] >= lo - 1e-4, f"{t} {w[t]} < {lo}"
    assert w.drop("SHV", errors="ignore").max() <= MAX_SINGLE_WEIGHT + 1e-4


@pytest.mark.parametrize("strategy", STRATS)
def test_reported_stats_match_column_order(asset_returns, strategy):
    """Regression: HRP returned weights in dendrogram order while mean/cov were in
    column order, so the logged Sharpe/vol/return paired the wrong assets."""
    res = opt.optimize(strategy=strategy, returns=asset_returns, regime="RISK_ON")
    w = pd.Series(res["weights"]).reindex(asset_returns.columns).values
    mu = asset_returns.mean().values * 252
    cov = asset_returns.cov().values * 252
    ret = float(w @ mu)
    vol = float(np.sqrt(w @ cov @ w))
    assert res["expected_annual_return"] == pytest.approx(ret, abs=1e-4)
    assert res["annual_volatility"] == pytest.approx(vol, abs=1e-4)
    assert list(res["weights"]) == list(asset_returns.columns)


def test_clip_and_renorm_obeys_bounds():
    w = pd.Series({"A": 0.9, "B": 0.05, "C": 0.05})
    b = {"A": (0.0, 0.5), "B": (0.2, 1.0), "C": (0.0, 1.0)}
    out = opt._clip_and_renorm(w.copy(), b)
    assert abs(out.sum() - 1.0) < 1e-9
    assert out["A"] <= 0.5 + 1e-9 and out["B"] >= 0.2 - 1e-9


# ── select_strategy override bar (the 0.5 floor from 1e94b61) ─────────────────

def _select_with_scores(monkeypatch, asset_returns, regime, scores):
    monkeypatch.setattr(opt, "_score_strategy_recent",
                        lambda name, returns, regime: scores[name])
    return opt.select_strategy(regime, returns=asset_returns)


def test_override_bar_negative_baseline_needs_absolute_gap(monkeypatch, asset_returns):
    # CHOPPY baseline = HRP, margin 0.15. Baseline -1.0 -> gap needed 0.15.
    # A rival at -0.9 (gap 0.10) must NOT override (the old multiplicative bar let it).
    s = {"HRP": -1.0, "MAX_SHARPE": -0.9, "HRP_MOMENTUM": -2.0}
    assert _select_with_scores(monkeypatch, asset_returns, "CHOPPY", s) == "HRP"
    s["MAX_SHARPE"] = -0.80                      # gap 0.20 > 0.15
    assert _select_with_scores(monkeypatch, asset_returns, "CHOPPY", s) == "MAX_SHARPE"


def test_override_bar_floor_for_near_zero_baseline(monkeypatch, asset_returns):
    # Baseline ~0 -> |baseline| floored at 0.5 -> required gap 0.15 * 0.5 = 0.075.
    s = {"HRP": 0.01, "MAX_SHARPE": 0.08, "HRP_MOMENTUM": 0.0}   # gap 0.07 < 0.075
    assert _select_with_scores(monkeypatch, asset_returns, "CHOPPY", s) == "HRP"
    s["MAX_SHARPE"] = 0.09                                         # gap 0.08 > 0.075
    assert _select_with_scores(monkeypatch, asset_returns, "CHOPPY", s) == "MAX_SHARPE"


def test_override_bar_risk_on_margin(monkeypatch, asset_returns):
    # RISK_ON margin 1.0: baseline 1.0 -> rival needs > 2.0.
    s = {"HRP_MOMENTUM": 1.0, "HRP": 1.9, "MAX_SHARPE": 0.0}
    assert _select_with_scores(monkeypatch, asset_returns, "RISK_ON", s) == "HRP_MOMENTUM"
    s["HRP"] = 2.1
    assert _select_with_scores(monkeypatch, asset_returns, "RISK_ON", s) == "HRP"
