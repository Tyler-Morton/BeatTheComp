"""Risk-overlay math: exact scaling, cash parking, HAR timing, HAR loud failure."""
import numpy as np
import pandas as pd
import pytest

import risk_overlay as ro


def _rets(n, vol=0.02, seed=0, cols=("A", "B")):
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2020-01-01", periods=n)
    return pd.DataFrame({c: rng.normal(0, vol, n) for c in cols}, index=idx)


def test_scaler_is_exactly_target_over_vol():
    r = _rets(120, vol=0.03)
    w = {"A": 0.5, "B": 0.5}
    pv = ro.portfolio_vol(r, w, window=40)
    s = ro.vol_target_scaler(r, w, target_vol=0.20, model="trailing")
    assert s == pytest.approx(min(1.0, 0.20 / pv))


def test_apply_overlay_preserves_total_and_parks_cash():
    r = _rets(120, vol=0.03)
    w = {"A": 0.6, "B": 0.4}
    out, info = ro.apply_overlay(w, r, target_vol=0.10, cash_asset="SHV")
    s = info["combined_scaler"]
    assert sum(out.values()) == pytest.approx(1.0)
    assert out["A"] == pytest.approx(0.6 * ro.vol_target_scaler(r, w, 0.10))
    assert out["SHV"] == pytest.approx(1.0 - (out["A"] + out["B"]))
    assert 0 < s < 1


def _har_reference(r: pd.DataFrame, w: dict, win=500):
    """Textbook one-step HAR: fit RV_{t+1} on (RV_t, RV5_t, RV22_t), predict from the LAST row."""
    pr = r[list(w)].values @ np.array(list(w.values())) / sum(w.values())
    rv = pd.Series(pr ** 2)
    X = pd.concat([rv, rv.rolling(5).mean(), rv.rolling(22).mean()], axis=1)
    y = rv.shift(-1)
    fit = pd.concat([X, y.rename("y")], axis=1).dropna().tail(win)
    A = np.column_stack([np.ones(len(fit)), fit.iloc[:, :3].values])
    beta = np.linalg.lstsq(A, fit["y"].values, rcond=None)[0]
    x_T = X.iloc[-1].values                          # today's features — not yesterday's
    return float(np.sqrt((np.r_[1.0, x_T] @ beta) * 252))


def test_har_forecasts_from_todays_features():
    r = _rets(700, seed=3)
    r.iloc[-1] = 0.08                                # a shock on the final day must move the forecast
    w = {"A": 0.5, "B": 0.5}
    assert ro.har_forecast(r, w) == pytest.approx(_har_reference(r, w), rel=1e-9)


def test_har_raises_instead_of_silent_trailing_fallback():
    r = _rets(250)                                   # what main.py actually supplies
    with pytest.raises(RuntimeError, match="har"):
        ro.vol_target_scaler(r, {"A": 1.0}, 0.2, model="har")


def test_har_runs_with_enough_history():
    r = _rets(600, seed=1)
    s = ro.vol_target_scaler(r, {"A": 1.0}, 0.2, model="har")
    assert 0 < s <= 1


def test_unknown_model_rejected():
    with pytest.raises(ValueError):
        ro.vol_target_scaler(_rets(100), {"A": 1.0}, 0.2, model="ewma")


def test_production_config_is_trailing():
    from config import OVERLAY_VOL_MODEL
    assert OVERLAY_VOL_MODEL == "trailing"
