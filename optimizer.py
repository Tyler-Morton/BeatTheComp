"""Portfolio optimization — MAX_SHARPE | HRP | HRP_MOMENTUM."""

import logging

import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import leaves_list, linkage
from scipy.optimize import minimize
from scipy.spatial.distance import squareform

from config import (
    ACTIVE_STRATEGY,
    AUTO_SELECT_STRATEGY,
    ASSETS,
    LOOKBACK_DAYS,
    MAX_SINGLE_WEIGHT,
    MIN_SINGLE_WEIGHT,
    RISK_FREE_RATE,
    STRATEGY_BY_REGIME,
)

logger = logging.getLogger(__name__)

_LEVERAGED_ETFS = {"TQQQ", "UPRO", "SOXL", "TECL"}    # 3x leveraged growth
_EQUITY_ETFS = {"QQQ", "AVUV", "VGT", "IWM", "BITO", "VEA", "XLC", "MTUM"} | _LEVERAGED_ETFS


# ── Bound helpers ──────────────────────────────────────────────────────────────

def _base_bounds(n: int) -> list[tuple[float, float]]:
    return [(MIN_SINGLE_WEIGHT, MAX_SINGLE_WEIGHT)] * n


def _apply_regime_bounds(
    tickers: list[str], bounds: list[tuple], regime: str
) -> list[tuple]:
    """Apply regime-specific weight caps. AGGRESSIVE PAPER TRADING CONFIG.

    RISK_ON:  no defense. SHV/TLT effectively zero. Leveraged ETFs unleashed.
    CHOPPY:   moderate. Cap leveraged at 10%, force some GLD/TLT for stability.
    RISK_OFF: pure defense. Kill leveraged ETFs, force SHV ≥ 30%, TLT ≥ 20%.
    """
    result = list(bounds)
    for i, ticker in enumerate(tickers):
        lo, hi = result[i]
        if regime == "RISK_ON":
            # Defense killed — bot must commit to growth
            if ticker == "SHV":
                lo, hi = 0.0, 0.01
            elif ticker == "TLT":
                lo, hi = 0.0, 0.01
            elif ticker == "GLD":
                lo, hi = 0.0, 0.05
            # Equity ETFs (incl. leveraged) allowed up to MAX_SINGLE_WEIGHT (70%)
        elif regime == "CHOPPY":
            if ticker in _LEVERAGED_ETFS:
                hi = min(hi, 0.10)         # leveraged ETFs dangerous in chop
            elif ticker == "GLD":
                lo = max(lo, 0.10)
            elif ticker == "TLT":
                lo = max(lo, 0.10)
            elif ticker in _EQUITY_ETFS:
                hi = min(hi, 0.30)
        elif regime == "RISK_OFF":
            if ticker in _LEVERAGED_ETFS:
                hi = min(hi, 0.02)         # leveraged ETFs DEATH in crashes
            elif ticker == "SHV":
                lo = max(lo, 0.30)
            elif ticker == "TLT":
                lo = max(lo, 0.20)
            elif ticker in _EQUITY_ETFS:
                hi = min(hi, 0.10)
        result[i] = (max(lo, 0.0), min(hi, 1.0))
    return result


def _apply_sentiment_bounds(
    tickers: list[str], bounds: list[tuple], sentiment: dict
) -> list[tuple]:
    result = list(bounds)
    for i, ticker in enumerate(tickers):
        if ticker not in sentiment:
            continue
        score = sentiment[ticker].get("score", 0.0)
        lo, hi = result[i]
        if score > 0.6:
            hi = min(hi + 0.05, 1.0)
        elif score < -0.8:
            hi = max(lo, min(hi, 0.05))
        elif score < -0.5:
            hi = max(lo, hi - 0.10)
        result[i] = (lo, hi)
    return result


def _clip_and_renorm(weights: pd.Series, bounds: dict | list) -> pd.Series:
    """Enforce BOTH min and max bounds, redistribute to keep sum = 1.0.

    bounds dict form {ticker: (lo, hi)} is preferred — order-safe when weights
    have been reordered by HRP clustering.

    Algorithm:
      1. Force-promote anything below its min (RISK_OFF SHV ≥ 30%, etc.)
      2. Iteratively cap anything above its max, redistribute to eligible assets
      3. Final safety: hard-cap any leftover violations
    """
    tickers = weights.index.tolist()
    if isinstance(bounds, dict):
        min_bounds = {t: bounds[t][0] for t in tickers if t in bounds}
        max_bounds = {t: bounds[t][1] for t in tickers if t in bounds}
    else:
        min_bounds = {tickers[i]: bounds[i][0] for i in range(len(tickers))}
        max_bounds = {tickers[i]: bounds[i][1] for i in range(len(tickers))}

    total = weights.sum()
    if total > 0:
        weights = weights / total

    # Step 1: Force-promote anything below its minimum (required floors)
    # This funds the promotion by pulling proportionally from other assets.
    needed = 0.0
    for t in tickers:
        if weights[t] < min_bounds[t]:
            needed += min_bounds[t] - weights[t]
            weights[t] = min_bounds[t]
    if needed > 0:
        # Pull from assets that are above their min (have donate-able weight)
        donors = [t for t in tickers if weights[t] > min_bounds[t] + 1e-9]
        donor_excess = sum(weights[t] - min_bounds[t] for t in donors)
        if donor_excess > 0:
            scale = min(needed / donor_excess, 1.0)
            for t in donors:
                weights[t] -= (weights[t] - min_bounds[t]) * scale

    # Step 2: Iteratively cap maximums, redistribute excess to assets with room
    locked: set[str] = set()
    for _ in range(50):
        excess = 0.0
        for t in tickers:
            if weights[t] > max_bounds[t] + 1e-9:
                excess += weights[t] - max_bounds[t]
                weights[t] = max_bounds[t]
                locked.add(t)
            elif abs(weights[t] - max_bounds[t]) < 1e-9:
                locked.add(t)

        if excess < 1e-9:
            break

        # Only redistribute to assets that aren't capped and aren't at min-only floors
        eligible = [t for t in tickers if t not in locked]
        if not eligible:
            break

        eligible_nonzero = [t for t in eligible if weights[t] > 1e-9]
        if eligible_nonzero:
            total_pool = sum(weights[t] for t in eligible_nonzero)
            for t in eligible_nonzero:
                weights[t] += excess * (weights[t] / total_pool)
        else:
            per_asset = excess / len(eligible)
            for t in eligible:
                weights[t] += per_asset

    # Step 3: Final safety — hard-cap any remaining max violations
    for t in tickers:
        if weights[t] > max_bounds[t]:
            weights[t] = max_bounds[t]

    # Step 4: Fill deficit using assets with remaining room (but never below min)
    deficit = 1.0 - float(weights.sum())
    if abs(deficit) > 1e-6:
        room = [(t, max_bounds[t] - weights[t]) for t in tickers if max_bounds[t] - weights[t] > 1e-9]
        total_room = sum(r for _, r in room)
        if total_room > 0:
            for t, r in room:
                weights[t] += deficit * (r / total_room)

    return weights


# ── Strategy implementations ───────────────────────────────────────────────────

def _max_sharpe(returns: pd.DataFrame, bounds: list[tuple]) -> np.ndarray:
    mean_ret = returns.mean().values
    cov = returns.cov().values * 252
    n = len(returns.columns)

    def neg_sharpe(w: np.ndarray) -> float:
        port_ret = float(np.dot(w, mean_ret)) * 252
        port_vol = float(np.sqrt(np.dot(w, np.dot(cov, w))))
        if port_vol < 1e-9:
            return 0.0
        return -(port_ret - RISK_FREE_RATE) / port_vol

    x0 = np.array([1.0 / n] * n)
    x0 = np.clip(x0, [b[0] for b in bounds], [b[1] for b in bounds])
    x0 /= x0.sum()

    res = minimize(
        neg_sharpe,
        x0,
        method="SLSQP",
        bounds=bounds,
        constraints=[{"type": "eq", "fun": lambda w: w.sum() - 1.0}],
        options={"maxiter": 2000, "ftol": 1e-10},
    )
    if not res.success:
        logger.warning("MAX_SHARPE did not fully converge: %s", res.message)
    return res.x


def _hrp(returns: pd.DataFrame) -> pd.Series:
    """Hierarchical Risk Parity via recursive bisection."""
    corr = returns.corr()
    cov = returns.cov()
    tickers = returns.columns.tolist()

    dist = np.sqrt(np.clip((1.0 - corr.values) / 2.0, 0.0, 1.0))
    dist = (dist + dist.T) / 2          # force exact symmetry (float precision fix)
    np.fill_diagonal(dist, 0.0)
    link = linkage(squareform(dist), method="ward")
    sorted_tickers = [tickers[i] for i in leaves_list(link)]

    weights = pd.Series(1.0, index=sorted_tickers)
    clusters: list[list[str]] = [sorted_tickers]

    while clusters:
        next_clusters: list[list[str]] = []
        for cluster in clusters:
            if len(cluster) <= 1:
                continue
            mid = len(cluster) // 2
            left, right = cluster[:mid], cluster[mid:]

            def _cluster_var(sub: list[str]) -> float:
                sub_cov = cov.loc[sub, sub].values
                ivp = 1.0 / np.diag(sub_cov)
                ivp /= ivp.sum()
                return float(ivp @ sub_cov @ ivp)

            lv, rv = _cluster_var(left), _cluster_var(right)
            alpha = 1.0 - lv / (lv + rv)
            weights[left] *= alpha
            weights[right] *= 1.0 - alpha
            next_clusters.extend([left, right])
        clusters = next_clusters

    return weights / weights.sum()


def _hrp_momentum(returns: pd.DataFrame) -> pd.Series:
    """HRP base + absolute momentum filter + relative momentum tilt."""
    weights = _hrp(returns)

    # Absolute momentum: 12-week (≈63 trading days) lookback
    period = min(63, len(returns))
    cum_ret = (1 + returns.tail(period)).prod() - 1
    tbill_hurdle = RISK_FREE_RATE * (period / 252)

    zeroed_mass = 0.0
    for ticker in list(weights.index):
        if ticker == "SHV":
            continue
        if cum_ret.get(ticker, 0.0) < tbill_hurdle:
            zeroed_mass += weights[ticker]
            weights[ticker] = 0.0

    # Move failed allocations: half to SHV (capped at MAX_SINGLE_WEIGHT),
    # remainder spread across passing assets so SHV never breaches concentration limit.
    if zeroed_mass > 0:
        live_assets = [t for t in weights.index if t != "SHV" and weights[t] > 0]
        shv_room = MAX_SINGLE_WEIGHT - weights.get("SHV", 0.0)
        shv_add = min(zeroed_mass, max(shv_room, 0.0))
        remainder = zeroed_mass - shv_add
        if "SHV" in weights.index:
            weights["SHV"] += shv_add
        if remainder > 0 and live_assets:
            per_asset = remainder / len(live_assets)
            for t in live_assets:
                weights[t] += per_asset
        elif remainder > 0 and "SHV" in weights.index:
            # No live assets — SHV absorbs everything (override cap)
            weights["SHV"] += remainder

    # Relative momentum: +60% bonus to top 3, take 40% from bottom 3
    # Bigger tilt = leveraged ETFs (TQQQ etc) get proper allocation when winning
    live = weights[weights > 0].index.tolist()
    if len(live) >= 6:
        ranked = cum_ret.reindex(live).sort_values(ascending=False)
        top3 = ranked.index[:3].tolist()
        bot3 = ranked.index[-3:].tolist()
        for t in top3:
            weights[t] *= 1.60                # was 1.20 — much harder lean into winners
        for t in bot3:
            reduction = weights[t] * 0.40     # was 0.20 — bigger trim of losers
            weights[t] -= reduction
            for tt in top3:
                weights[tt] += reduction / 3

    total = weights.sum()
    return weights / total if total > 0 else weights


# ── Strategy selector ─────────────────────────────────────────────────────────

ADAPTIVE_LOOKBACK_DAYS = 60       # window for measuring recent strategy performance
ADAPTIVE_OVERRIDE_MARGIN = 0.15   # default: best must beat baseline by 15% Sharpe
ADAPTIVE_OVERRIDE_MARGIN_RISK_ON = 1.00   # nearly impossible to override in bull — HRP_MOMENTUM locked in


def _score_strategy_recent(
    strategy_name: str,
    returns: pd.DataFrame,
    regime: str,
    lookback: int = ADAPTIVE_LOOKBACK_DAYS,
) -> float:
    """Simulate a strategy on out-of-sample recent data and return its Sharpe.

    Uses returns BEFORE the lookback period to compute weights (avoids look-ahead),
    then applies those weights to the most recent `lookback` days to score actual
    realized performance.
    """
    if len(returns) < lookback + 60:
        return 0.0
    train = returns.iloc[:-lookback]
    test = returns.tail(lookback)
    try:
        # Run strategy on training data (no sentiment — historical doesn't have it)
        result = optimize(strategy=strategy_name, returns=train, regime=regime)
        weights = result["weights"]
        # Apply weights to test period
        cols = [c for c in test.columns if c in weights]
        if not cols:
            return 0.0
        w = np.array([weights[c] for c in cols])
        port_returns = (test[cols].values @ w)
        if port_returns.std() < 1e-9:
            return 0.0
        sharpe = (port_returns.mean() - RISK_FREE_RATE / 252) / port_returns.std() * np.sqrt(252)
        return float(sharpe)
    except Exception as exc:
        logger.warning("Recent score failed for %s: %s", strategy_name, exc)
        return 0.0


def select_strategy(regime: str, returns: pd.DataFrame | None = None) -> str:
    """Return the best strategy for current conditions.

    Logic:
      1. Start with regime-based mapping (STRATEGY_BY_REGIME) as baseline.
      2. If returns data is available and AUTO_SELECT_STRATEGY is on, score all
         three strategies on the last 60 days of actual data.
      3. Override the regime choice ONLY if another strategy beats the baseline
         by a significant margin (15% better Sharpe) — prevents chasing noise.
    """
    if not AUTO_SELECT_STRATEGY:
        return ACTIVE_STRATEGY

    baseline = STRATEGY_BY_REGIME.get(regime, ACTIVE_STRATEGY)

    # Without enough data, fall back to pure regime mapping
    if returns is None or len(returns) < ADAPTIVE_LOOKBACK_DAYS + 60:
        logger.info("Strategy: %s (regime=%s, no adaptive override — insufficient history)", baseline, regime)
        return baseline

    # Score every strategy on actual recent performance
    scores: dict[str, float] = {}
    for strat in ("MAX_SHARPE", "HRP", "HRP_MOMENTUM"):
        scores[strat] = _score_strategy_recent(strat, returns, regime)

    baseline_score = scores.get(baseline, 0.0)
    best_strat = max(scores, key=scores.get)
    best_score = scores[best_strat]

    log_scores = ", ".join(f"{k}={v:.2f}" for k, v in scores.items())
    logger.info("Recent Sharpe by strategy: %s", log_scores)

    # Tougher override threshold in RISK_ON — bias toward HRP_MOMENTUM in bull markets
    margin = ADAPTIVE_OVERRIDE_MARGIN_RISK_ON if regime == "RISK_ON" else ADAPTIVE_OVERRIDE_MARGIN

    # Override baseline only if the winner clearly beats it
    if best_strat != baseline and best_score > baseline_score * (1.0 + margin):
        logger.info(
            "ADAPTIVE OVERRIDE: %s (Sharpe %.2f) beats regime pick %s (Sharpe %.2f) by %.0f%%",
            best_strat, best_score, baseline, baseline_score,
            (best_score / baseline_score - 1) * 100 if baseline_score > 0 else 0,
        )
        return best_strat

    logger.info("Strategy: %s (regime=%s, baseline kept — no clear winner)", baseline, regime)
    return baseline


# ── Public API ─────────────────────────────────────────────────────────────────

def _portfolio_stats(weights: np.ndarray, mean_ret: np.ndarray, cov252: np.ndarray) -> dict:
    port_return = float(np.dot(weights, mean_ret) * 252)
    port_vol = float(np.sqrt(np.dot(weights, np.dot(cov252, weights))))
    sharpe = (port_return - RISK_FREE_RATE) / port_vol if port_vol > 0 else 0.0
    return {
        "expected_annual_return": round(port_return, 4),
        "annual_volatility": round(port_vol, 4),
        "sharpe_ratio": round(sharpe, 4),
    }


def optimize(
    strategy: str | None = None,
    returns: pd.DataFrame | None = None,
    sentiment_modifiers: dict | None = None,
    regime: str = "RISK_ON",
) -> dict:
    """Run optimization. Returns {weights, expected_annual_return, annual_volatility, sharpe_ratio}."""
    if strategy is None:
        strategy = ACTIVE_STRATEGY
    if sentiment_modifiers is None:
        sentiment_modifiers = {}

    if returns is None:
        from data import fetch_prices, get_returns
        prices = fetch_prices(ASSETS, LOOKBACK_DAYS)
        returns = get_returns(prices)

    tickers = returns.columns.tolist()
    n = len(tickers)
    bounds = _base_bounds(n)
    bounds = _apply_regime_bounds(tickers, bounds, regime)
    bounds = _apply_sentiment_bounds(tickers, bounds, sentiment_modifiers)

    # Build a ticker-keyed bounds dict — safe for any Series ordering
    bounds_by_ticker = {tickers[i]: bounds[i] for i in range(n)}

    if strategy == "MAX_SHARPE":
        # MAX_SHARPE uses the positional list with the original ticker order
        raw = _max_sharpe(returns, bounds)
        weights = pd.Series(raw, index=tickers)

    elif strategy == "HRP":
        weights = _hrp(returns)
        weights = _clip_and_renorm(weights, bounds_by_ticker)

    elif strategy == "HRP_MOMENTUM":
        weights = _hrp_momentum(returns)
        weights = _clip_and_renorm(weights, bounds_by_ticker)

    else:
        raise ValueError(f"Unknown strategy: {strategy!r}")

    mean_ret = returns.mean().values
    cov252 = returns.cov().values * 252
    stats = _portfolio_stats(weights.values, mean_ret, cov252)

    return {"weights": weights.to_dict(), **stats}
