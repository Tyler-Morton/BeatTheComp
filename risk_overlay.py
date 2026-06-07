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


def vol_target_scaler(returns: pd.DataFrame, weights: dict[str, float],
                      target_vol: float = 0.20, window: int = 40) -> float:
    """Scale factor in [0,1]: target_vol / realized_vol, capped at 1 (never lever up)."""
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
                  ) -> tuple[dict[str, float], dict]:
    """Scale `target_weights` toward `target_vol`; park the rest in `cash_asset`.

    Returns (new_weights, info). new_weights sum to ~1.0 (cash makes up the slack).
    Pure transform — never trades.
    """
    base_sum = sum(target_weights.values())
    s_vt = vol_target_scaler(asset_returns, target_weights, target_vol)
    if use_ml:
        s_ml, crash_p = ml_crash_multiplier(ml_prices)
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
        "est_portfolio_vol": round(portfolio_vol(asset_returns, target_weights), 3),
    }
    return scaled, info
