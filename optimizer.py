"""Deciding how much of each ETF to hold — the math brain of the bot.

There are three ways it can carve up the money:
  - MAX_SHARPE:     classic optimizer, chases the best return-per-unit-of-risk
  - HRP:            spreads risk evenly by grouping similar assets together
  - HRP_MOMENTUM:   HRP, but then leans harder into whatever's been winning lately
Whichever one main.py picks, this file turns it into an actual set of weights.
"""

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
    """Tighten or loosen the per-asset limits based on the market mood.

    Worth saying again: this is the aggressive paper-trading config, not something
    you'd run with real money.
      RISK_ON:  go for it. Basically no defense — SHV/TLT near zero, leverage off the leash.
      CHOPPY:   ease off. Cap the leveraged ETFs at 10% and keep some GLD/TLT around for ballast.
      RISK_OFF: hunker down. Leveraged ETFs out, and force at least 30% SHV and 20% TLT.
    """
    result = list(bounds)
    for i, ticker in enumerate(tickers):
        lo, hi = result[i]
        if regime == "RISK_ON":
            # No hiding in safe stuff — we want the money working for growth.
            if ticker == "SHV":
                lo, hi = 0.0, 0.01
            elif ticker == "TLT":
                lo, hi = 0.0, 0.01
            elif ticker == "GLD":
                lo, hi = 0.0, 0.05
            # The stock ETFs (leveraged ones included) can go all the way up to 70%.
        elif regime == "CHOPPY":
            if ticker in _LEVERAGED_ETFS:
                hi = min(hi, 0.03)         # 3x ETFs both decay AND crash in chop — keep them tiny (near RISK_OFF)
            elif ticker == "GLD":
                lo = max(lo, 0.10)
            elif ticker == "TLT":
                lo = max(lo, 0.10)
            elif ticker in _EQUITY_ETFS:
                hi = min(hi, 0.30)
        elif regime == "RISK_OFF":
            if ticker in _LEVERAGED_ETFS:
                hi = min(hi, 0.02)         # leverage in a crash is how you blow up the account — almost zero
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
        score = sentiment[ticker].get("score")
        if score is None:          # sentiment couldn't be determined -> no adjustment
            continue
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
    """Make the weights obey their min/max limits while still adding up to 100%.

    Pass bounds as a {ticker: (lo, hi)} dict when you can — that way it doesn't
    matter that HRP has shuffled the assets into a different order.

    The gist of it:
      1. Bump anything that's under its floor up to the floor (e.g. SHV must be ≥ 30% in RISK_OFF).
      2. Trim anything over its ceiling back down, and hand the spillover to assets that still have room.
      3. One last pass to hard-cap any stragglers that slipped through.
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

    # Step 1: lift anything sitting below its required floor up to that floor.
    # We pay for those bumps by skimming a little off everyone who has spare weight.
    needed = 0.0
    for t in tickers:
        if weights[t] < min_bounds[t]:
            needed += min_bounds[t] - weights[t]
            weights[t] = min_bounds[t]
    if needed > 0:
        # The "donors" are assets sitting above their floor — they have weight to spare.
        donors = [t for t in tickers if weights[t] > min_bounds[t] + 1e-9]
        donor_excess = sum(weights[t] - min_bounds[t] for t in donors)
        if donor_excess > 0:
            scale = min(needed / donor_excess, 1.0)
            for t in donors:
                weights[t] -= (weights[t] - min_bounds[t]) * scale

    # Step 2: trim anything over its ceiling and pour the overflow into assets that
    # still have headroom. We loop because moving weight around can push a new asset
    # over its own ceiling, so it takes a few passes to settle.
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

        # Only hand the overflow to assets that aren't already maxed out.
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

    # Step 3: belt-and-suspenders — force-cap anything still poking over its ceiling.
    for t in tickers:
        if weights[t] > max_bounds[t]:
            weights[t] = max_bounds[t]

    # Step 4: if all that capping left us short of 100%, top it back up using
    # whatever assets still have room (without ever dropping anyone below their floor).
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
    """Hierarchical Risk Parity.

    Plain-English version: it groups assets that move alike into a family tree,
    then splits the money down that tree so risk ends up shared evenly — instead
    of betting big on a handful of names that all rise and fall together.
    """
    corr = returns.corr()
    cov = returns.cov()
    tickers = returns.columns.tolist()

    dist = np.sqrt(np.clip((1.0 - corr.values) / 2.0, 0.0, 1.0))
    dist = (dist + dist.T) / 2          # nudge it perfectly symmetric — rounding can leave it a hair off, and the clustering step is picky
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
    """Start from HRP, then add a momentum opinion on top.

    Two extra steps: first kick out anything that hasn't even beaten cash lately
    (absolute momentum), then tilt the remaining money toward the strongest names
    and away from the weakest (relative momentum).
    """
    weights = _hrp(returns)

    # Absolute momentum check: how has each asset done over the last ~12 weeks (63 trading days)?
    period = min(63, len(returns))
    cum_ret = (1 + returns.tail(period)).prod() - 1
    tbill_hurdle = RISK_FREE_RATE * (period / 252)

    zeroed_mass = 0.0
    for ticker in list(weights.index):
        if ticker == "SHV":
            continue
        if cum_ret.get(ticker, 0.0) < tbill_hurdle:
            # Couldn't even beat a T-bill — it doesn't earn a spot, so zero it out.
            zeroed_mass += weights[ticker]
            weights[ticker] = 0.0

    # Now rehome the weight we just freed up. Park what we can in SHV (cash), but
    # not so much that SHV blows past the concentration cap — spread the rest across
    # the names that are still in the game.
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
            # Everything failed the momentum test, so there's nowhere else to put it —
            # SHV (cash) soaks up the rest even if that breaks the usual cap.
            weights["SHV"] += remainder

    # Relative momentum tilt: give the top 3 a +60% boost and trim the bottom 3 by 40%.
    # Leaning this hard is deliberate — it's what lets the leveraged ETFs (TQQQ etc.)
    # get a real allocation on the days they're the ones leading.
    live = weights[weights > 0].index.tolist()
    if len(live) >= 6:
        ranked = cum_ret.reindex(live).sort_values(ascending=False)
        top3 = ranked.index[:3].tolist()
        bot3 = ranked.index[-3:].tolist()
        for t in top3:
            weights[t] *= 1.60                # really lean into the winners
        for t in bot3:
            reduction = weights[t] * 0.40     # and meaningfully shave the laggards
            weights[t] -= reduction
            for tt in top3:
                weights[tt] += reduction / 3

    total = weights.sum()
    return weights / total if total > 0 else weights


# ── Strategy selector ─────────────────────────────────────────────────────────

ADAPTIVE_LOOKBACK_DAYS = 60       # how far back we look to judge "recent" performance
ADAPTIVE_OVERRIDE_MARGIN = 0.15   # a challenger has to be 15% better before we'll switch off the regime's pick
ADAPTIVE_OVERRIDE_MARGIN_RISK_ON = 1.00   # in a bull market the bar is so high it basically never switches — HRP_MOMENTUM stays put


def _score_strategy_recent(
    strategy_name: str,
    returns: pd.DataFrame,
    regime: str,
    lookback: int = ADAPTIVE_LOOKBACK_DAYS,
) -> float:
    """Score a strategy by replaying it on recent history — fairly.

    The trick is to avoid cheating with hindsight: we work out the weights using
    only the data from BEFORE the test window, then see how those weights would
    have actually done over the most recent `lookback` days. The result is a Sharpe
    ratio — basically, how good were the returns relative to how bumpy the ride was.
    """
    if len(returns) < lookback + 60:
        return 0.0
    train = returns.iloc[:-lookback]
    test = returns.tail(lookback)
    try:
        # Build the weights on the older "training" slice. No sentiment here — we
        # didn't record news scores back in history, so it wouldn't be a fair test.
        result = optimize(strategy=strategy_name, returns=train, regime=regime)
        weights = result["weights"]
        # Now see how those weights would've performed over the held-out recent days.
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
    """Pick which strategy to actually run today.

    How it decides:
      1. Start with the regime's default pick (from STRATEGY_BY_REGIME) as the baseline.
      2. If we have data and auto-select is on, replay all three strategies on the
         last 60 days and grade them.
      3. Only ditch the baseline if a rival clearly wins — 15% better — so we're
         reacting to a real edge, not random short-term noise.
    """
    if not AUTO_SELECT_STRATEGY:
        return ACTIVE_STRATEGY

    baseline = STRATEGY_BY_REGIME.get(regime, ACTIVE_STRATEGY)

    # Not enough history to grade anything fairly, so just trust the regime's pick.
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

    # In a bull market we make the bar to switch nearly unbeatable, so we stay in
    # HRP_MOMENTUM and don't get talked out of it by a hot streak somewhere else.
    margin = ADAPTIVE_OVERRIDE_MARGIN_RISK_ON if regime == "RISK_ON" else ADAPTIVE_OVERRIDE_MARGIN

    # Switch away from the baseline only when the winner clears that bar.
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
    """The main entry point — give it a strategy, get back the target weights.

    Along with the weights it also reports the expected annual return, how volatile
    that mix is, and the resulting Sharpe ratio.
    """
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

    # Key the bounds by ticker name so it doesn't matter if HRP reshuffles the order.
    bounds_by_ticker = {tickers[i]: bounds[i] for i in range(n)}

    if strategy == "MAX_SHARPE":
        # This one keeps the original ticker order, so it's fine to use the plain list.
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
