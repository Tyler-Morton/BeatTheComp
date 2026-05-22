"""Alpha sleeve — allocates a small % of the portfolio to top watchlist stocks.

Filters by sentiment + momentum, caps per-stock exposure, and merges into
the main ETF weights so the broker can execute everything in one rebalance.
"""

import logging
from typing import Iterable

from config import (
    ALPHA_MAX_PER_STOCK,
    ALPHA_MAX_TODAY_PCT,
    ALPHA_MIN_5D_MOMENTUM,
    ALPHA_MIN_PRICE,
    ALPHA_MIN_SENTIMENT,
    ALPHA_REQUIRE_POSITIVE_20D,
    ALPHA_SLEEVE_ENABLED,
    ALPHA_SLEEVE_PCT,
    ALPHA_SLEEVE_PICKS,
)

logger = logging.getLogger(__name__)


def select_alpha_picks(watchlist_data: list[dict]) -> dict[str, float]:
    """Return {ticker: weight_within_sleeve} for top qualifying watchlist stocks.

    A stock qualifies if:
      - sentiment_score >= ALPHA_MIN_SENTIMENT
      - 5-day momentum >= ALPHA_MIN_5D_MOMENTUM

    Top N picks are weighted by combined score (sentiment + momentum).
    Returns empty dict if nothing qualifies (sleeve cash stays in main ETFs).
    """
    if not watchlist_data:
        return {}

    qualified = []
    for row in watchlist_data:
        ticker = row.get("ticker", "")
        sent = float(row.get("sentiment_score", 0.0) or 0.0)
        mom_5d = float(row.get("mom_5d", 0.0) or 0.0)
        mom_20d = float(row.get("mom_20d", 0.0) or 0.0)
        today_pct = float(row.get("today_pct", 0.0) or 0.0)
        price = float(row.get("price", 0.0) or 0.0)

        # Hard filters — must pass ALL to qualify
        if sent < ALPHA_MIN_SENTIMENT:
            continue
        if mom_5d < ALPHA_MIN_5D_MOMENTUM:
            continue
        if price < ALPHA_MIN_PRICE:
            continue                                   # avoid penny stocks
        if today_pct > ALPHA_MAX_TODAY_PCT:
            continue                                   # already gapped up, bad entry
        if ALPHA_REQUIRE_POSITIVE_20D and mom_20d <= 0:
            continue                                   # filter short-term fakeouts

        # Composite score: bullish news + sustained trend, penalize chasing the top
        # sentiment (0-1) + 1.5x 5-day momentum + 0.5x 20-day momentum
        # - small penalty for already running today (avoid buying spikes)
        score = sent + 1.5 * mom_5d + 0.5 * mom_20d - 0.5 * max(today_pct - 0.10, 0)

        qualified.append({
            "ticker": ticker,
            "score": score,
            "sentiment": sent,
            "momentum_5d": mom_5d,
            "momentum_20d": mom_20d,
            "today_pct": today_pct,
        })

    if not qualified:
        logger.info("Alpha sleeve: no qualifying stocks today")
        return {}

    qualified.sort(key=lambda r: -r["score"])
    picks = qualified[:ALPHA_SLEEVE_PICKS]

    # Weight by relative score, but cap per stock
    total_score = sum(p["score"] for p in picks)
    raw_weights = {p["ticker"]: p["score"] / total_score for p in picks}

    # Apply per-stock cap (as a fraction of the SLEEVE, not the whole portfolio)
    sleeve_max = ALPHA_MAX_PER_STOCK / ALPHA_SLEEVE_PCT if ALPHA_SLEEVE_PCT > 0 else 1.0
    sleeve_max = min(sleeve_max, 1.0)
    capped = {t: min(w, sleeve_max) for t, w in raw_weights.items()}

    # Renormalize the sleeve to 100%
    total = sum(capped.values())
    sleeve_weights = {t: w / total for t, w in capped.items()} if total > 0 else {}

    for p in picks:
        t = p["ticker"]
        logger.info(
            "  Alpha pick: %-6s  sent=%+.2f  mom_5d=%+.1f%%  mom_20d=%+.1f%%  sleeve=%.0f%%",
            t, p["sentiment"], p["momentum_5d"] * 100, p["momentum_20d"] * 100,
            sleeve_weights.get(t, 0) * 100,
        )

    return sleeve_weights


def merge_with_etf_weights(
    etf_weights: dict[str, float],
    watchlist_data: list[dict],
) -> dict[str, float]:
    """Combine ETF target weights with alpha sleeve picks.

    Reduces all ETF weights proportionally by ALPHA_SLEEVE_PCT, then adds the
    alpha picks to fill that space. Returns the merged weights summing to 1.0.
    """
    if not ALPHA_SLEEVE_ENABLED:
        return etf_weights

    sleeve_picks = select_alpha_picks(watchlist_data)
    if not sleeve_picks:
        return etf_weights   # no qualified picks → keep 100% in ETFs

    # Scale ETFs down to (1 - sleeve_pct)
    etf_scale = 1.0 - ALPHA_SLEEVE_PCT
    scaled_etfs = {t: w * etf_scale for t, w in etf_weights.items()}

    # Add alpha picks at sleeve_pct total
    combined = dict(scaled_etfs)
    for ticker, sleeve_w in sleeve_picks.items():
        combined[ticker] = combined.get(ticker, 0.0) + sleeve_w * ALPHA_SLEEVE_PCT

    # Final renorm (should already be ~1.0)
    total = sum(combined.values())
    if total > 0:
        combined = {t: w / total for t, w in combined.items()}

    logger.info(
        "Alpha sleeve active: %d picks taking %.0f%% of portfolio",
        len(sleeve_picks), ALPHA_SLEEVE_PCT * 100,
    )
    return combined
