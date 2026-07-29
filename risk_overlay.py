"""Risk overlay: vol-targeting (+ optional ML throttle) on top of the bot's weights.

This sits AFTER the optimizer/alpha-sleeve produce target weights and BEFORE the
trade. It scales the whole book up/down toward a target volatility — parking the
unused portion in cash (SHV) — so a high-octane (3x) book can't run at 50-90%
volatility into a crash. Validated in backtests to cut a 3x book's vol ~53%→20%
and max drawdown ~-71%→-24% while keeping returns above SPY.

Two independent scalers, multiplied together (each in [0,1]):
  • vol-target  — target_vol / recent realized portfolio vol (the workhorse)
  • ML throttle — optional; a crash-probability model trims further when risk is
    high. Fully graceful: ANY failure (missing lib, short data, fit error) returns
    a neutral 1.0 so the bot keeps running. Off by default until proven live.

Nothing here trades. It only transforms a weights dict.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

TRADING_DAYS = 252
RISK_FREE_RATE = 0.045


# ── Vol targeting (the workhorse) ────────────────────────────────────────────

def portfolio_vol(returns: pd.DataFrame, weights: dict[str, float],
                  window: int = 40) -> float:
    """Annualized realized vol of the target portfolio, from a trailing covariance."""
    cols = [t for t in weights if t in returns.columns and abs(weights[t]) > 1e-9]
    if not cols:
        return 0.0
    w = np.array([weights[t] for t in cols], dtype=float)
    s = w.sum()
    if s <= 0:
        return 0.0
    w = w / s
    hist = returns[cols].tail(window).dropna(how="all")
    if len(hist) < 10:
        return 0.0
    cov = hist.cov().values * TRADING_DAYS
    var = float(w @ cov @ w)
    return float(np.sqrt(var)) if var > 0 else 0.0


def har_forecast(returns: pd.DataFrame, weights: dict[str, float],
                 har_window: int = 500) -> float:
    """One-step-ahead annualized vol from HAR-RV (Corsi 2009). 0.0 if unavailable.

        RV_{t+1} = b0 + bd*RV_daily + bw*RV_weekly + bm*RV_monthly

    on the CURRENT portfolio's daily returns, rolling OLS, causal throughout.
    The 1/5/22 horizons are canonical — do NOT search them. Three coefficients
    is the whole point: it captures vol clustering and multi-horizon persistence
    without the fragility that makes fancier models fail out of sample.

    Returns 0.0 (not a guess) when there isn't enough history, so the caller
    falls back to the trailing estimator rather than to something invented.
    """
    cols = [t for t in weights if t in returns.columns and abs(weights[t]) > 1e-9]
    if not cols:
        return 0.0
    w = np.array([weights[t] for t in cols], dtype=float)
    if w.sum() <= 0:
        return 0.0
    w = w / w.sum()
    # errstate: Apple's Accelerate BLAS raises a spurious "divide by zero
    # encountered in matmul" on clean finite float64 input. Verified: inputs
    # finite, output finite, warning bogus. Suppressed HERE ONLY, and paired
    # with an explicit finiteness check below — never suppress a warning without
    # replacing it with a real test.
    with np.errstate(all="ignore"):
        pr = returns[cols].fillna(0.0).values @ w
    if not np.isfinite(pr).all():
        return 0.0
    if len(pr) < har_window + 30:
        return 0.0
    rv = pd.Series(pr ** 2)
    X = pd.concat([rv, rv.rolling(5).mean(), rv.rolling(22).mean()], axis=1).dropna()
    y = rv.shift(-1).reindex(X.index)
    ok = y.notna()
    X, y = X[ok], y[ok]
    if len(X) < 60:
        return 0.0
    A = np.column_stack([np.ones(len(X.tail(har_window))), X.tail(har_window).values])
    try:
        beta, *_ = np.linalg.lstsq(A, y.tail(har_window).values, rcond=None)
    except np.linalg.LinAlgError:
        return 0.0
    rv_hat = float(np.concatenate([[1.0], X.iloc[-1].values]) @ beta)
    if not np.isfinite(rv_hat) or rv_hat <= 0:
        return 0.0
    return float(np.sqrt(rv_hat * TRADING_DAYS))


def vol_target_scaler(returns: pd.DataFrame, weights: dict[str, float],
                      target_vol: float = 0.20, window: int = 40,
                      model: str | None = None) -> float:
    """Scale factor in [0,1]: target_vol / estimated_vol, capped at 1 (never lever up).

    `model` selects how vol is ESTIMATED — "trailing" (40d realized) or "har"
    (forecast). Defaults to config.OVERLAY_VOL_MODEL. HAR falls back to trailing
    whenever it can't produce a number, so a thin history degrades to today's
    behaviour instead of to something arbitrary.
    """
    if model is None:
        try:
            from config import OVERLAY_VOL_MODEL as model
        except Exception:
            model = "trailing"
    pv = 0.0
    if model == "har":
        pv = har_forecast(returns, weights)
    if pv <= 1e-6:
        pv = portfolio_vol(returns, weights, window)
    if pv <= 1e-6:
        return 1.0
    return float(np.clip(target_vol / pv, 0.0, 1.0))


# ── ML throttle (optional, fully graceful) ───────────────────────────────────

def _ml_features(prices: pd.DataFrame) -> pd.DataFrame:
    spy, qqq = prices["SPY"], prices["QQQ"]
    r = spy.pct_change(fill_method=None)
    f = pd.DataFrame(index=prices.index)
    f["ret20"] = spy.pct_change(20, fill_method=None)
    f["ret60"] = spy.pct_change(60, fill_method=None)
    f["vol20"] = r.rolling(20).std() * np.sqrt(TRADING_DAYS)
    f["vol60"] = r.rolling(60).std() * np.sqrt(TRADING_DAYS)
    f["vol_ratio"] = f["vol20"] / f["vol60"]
    f["dd60"] = spy / spy.rolling(60).max() - 1.0
    f["trend"] = spy / spy.rolling(200).mean() - 1.0
    f["qtrend"] = qqq / qqq.rolling(200).mean() - 1.0
    f["skew20"] = r.rolling(20).skew()
    return f


def ml_crash_multiplier(prices: pd.DataFrame | None = None, horizon: int = 10,
                        dd_thresh: float = 0.05) -> tuple[float, float | None]:
    """Train on history (purged) → predict today's P(drawdown) → leverage multiplier.

    Returns (multiplier in [0.4, 1.1], crash_prob or None). On ANY problem returns
    (1.0, None) — a neutral no-op — so this can never break a live run.
    """
    try:
        from sklearn.ensemble import HistGradientBoostingClassifier

        if prices is None:
            from data import fetch_prices
            prices = fetch_prices(["SPY", "QQQ"], lookback_days=1500)
        if prices is None or "SPY" not in prices or "QQQ" not in prices:
            return 1.0, None
        if len(prices) < 800:
            logger.info("ML overlay: only %d rows (<800) — skipping", len(prices))
            return 1.0, None

        f = _ml_features(prices)
        spy = prices["SPY"].values
        # label: does SPY fall >dd_thresh at any point in the next `horizon` days?
        label = np.full(len(spy), np.nan)
        for i in range(len(spy) - 1):
            end = min(i + 1 + horizon, len(spy))
            w = spy[i + 1:end]
            if len(w):
                label[i] = 1.0 if (w.min() / spy[i] - 1.0) < -dd_thresh else 0.0

        X = f.values
        ok = np.isfinite(X).all(axis=1)
        tr = ok & np.isfinite(label)
        tr[len(spy) - horizon:] = False     # purge: last horizon rows have peeking labels
        if tr.sum() < 300 or not (0 < label[tr].sum() < tr.sum()):
            return 1.0, None

        model = HistGradientBoostingClassifier(max_depth=3, max_iter=150,
                                               learning_rate=0.05,
                                               l2_regularization=1.0, random_state=0)
        model.fit(X[tr], label[tr])

        last = X[-1]
        if not np.isfinite(last).all():
            return 1.0, None
        p = float(model.predict_proba(last.reshape(1, -1))[0, 1])
        mult = float(np.clip(1.1 - 1.3 * p, 0.4, 1.1))
        return mult, p
    except Exception as exc:
        logger.warning("ML overlay failed (%s) — using neutral 1.0", exc)
        return 1.0, None


# ── The one function main.py calls ───────────────────────────────────────────

def apply_overlay(target_weights: dict[str, float], asset_returns: pd.DataFrame,
                  target_vol: float = 0.20, use_ml: bool = False,
                  cash_asset: str = "SHV", ml_prices: pd.DataFrame | None = None,
                  shadow_ml: bool = False,
                  ) -> tuple[dict[str, float], dict]:
    """Scale `target_weights` toward `target_vol`; park the rest in `cash_asset`.

    Returns (new_weights, info). new_weights sum to ~1.0 (cash makes up the slack).
    Pure transform — never trades. `shadow_ml` computes the crash model's verdict
    for LOGGING only (multiplier is not applied) — the trust-building mode.
    """
    base_sum = sum(target_weights.values())
    s_vt = vol_target_scaler(asset_returns, target_weights, target_vol)
    shadow_mult = None
    if use_ml:
        s_ml, crash_p = ml_crash_multiplier(ml_prices)
    elif shadow_ml:
        shadow_mult, crash_p = ml_crash_multiplier(ml_prices)   # observe only
        s_ml = 1.0
    else:
        s_ml, crash_p = 1.0, None
    s = float(np.clip(s_vt * s_ml, 0.0, 1.0))

    scaled = {k: v * s for k, v in target_weights.items()}
    cash = max(base_sum - sum(scaled.values()), 0.0)
    if cash > 1e-6:
        scaled[cash_asset] = scaled.get(cash_asset, 0.0) + cash

    info = {
        "vol_target": target_vol,
        "vol_scaler": round(s_vt, 3),
        "ml_scaler": round(s_ml, 3),
        "combined_scaler": round(s, 3),
        "cash_parked": round(cash, 3),
        "crash_prob": (round(crash_p, 3) if crash_p is not None else None),
        "ml_shadow_mult": (round(shadow_mult, 3) if shadow_mult is not None else None),
        "est_portfolio_vol": round(portfolio_vol(asset_returns, target_weights), 3),
    }
    return scaled, info
