"""The alpha sleeve — our hand-picked individual-stock bets.

Most of the portfolio sits in ETFs, but this carves off a slice (40%) for a few
specific stocks that look hot right now. We screen the day's watchlist on news
sentiment and momentum, keep only the strongest few, cap how big any one of them
can get, and then fold them into the ETF weights so the broker can trade the whole
thing in a single rebalance.
"""

import logging
from datetime import datetime
from typing import Iterable

from config import (
    ALERTS_LOG,
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


def _log_alert(message: str) -> None:
    """Write a loud alert when alpha sleeve does something unusual."""
    try:
        with open(ALERTS_LOG, "a") as f:
            f.write(f"{datetime.now().isoformat()} | ALPHA: {message}\n")
    except Exception:
        pass


def _evaluate(row: dict, min_sent: float, min_5d: float, require_pos_20d: bool) -> tuple[bool, str]:
    """Does this one stock clear the bar? Returns (yes/no, and if no, why not)."""
    sent = float(row.get("sentiment_score", 0.0) or 0.0)
    mom_5d = float(row.get("mom_5d", 0.0) or 0.0)
    mom_20d = float(row.get("mom_20d", 0.0) or 0.0)
    today_pct = float(row.get("today_pct", 0.0) or 0.0)
    price = float(row.get("price", 0.0) or 0.0)

    if price < ALPHA_MIN_PRICE:
        return False, f"price ${price:.2f} < ${ALPHA_MIN_PRICE}"
    if today_pct > ALPHA_MAX_TODAY_PCT:
        return False, f"already up {today_pct:.1%} today"
    if sent < min_sent:
        return False, f"sentiment {sent:+.2f} < {min_sent}"
    if mom_5d < min_5d:
        return False, f"5d mom {mom_5d:+.1%} < {min_5d:.1%}"
    if require_pos_20d and mom_20d <= 0:
        return False, f"20d mom {mom_20d:+.1%} not positive"
    return True, ""


def _score(row: dict) -> float:
    """Rank the survivors. Reward bullish news and a steady climb; dock points for
    a stock that's already spiked hard today (we don't want to buy the very top).
    """
    sent = float(row.get("sentiment_score", 0.0) or 0.0)
    mom_5d = float(row.get("mom_5d", 0.0) or 0.0)
    mom_20d = float(row.get("mom_20d", 0.0) or 0.0)
    today_pct = float(row.get("today_pct", 0.0) or 0.0)
    return sent + 1.5 * mom_5d + 0.5 * mom_20d - 0.5 * max(today_pct - 0.10, 0)


def _pass(
    watchlist_data: list[dict],
    min_sent: float,
    min_5d: float,
    require_pos_20d: bool,
    log_rejections: bool,
) -> list[dict]:
    """Push the whole watchlist through the filters and hand back whoever made it."""
    qualified: list[dict] = []
    for row in watchlist_data:
        ticker = row.get("ticker", "")
        ok, reason = _evaluate(row, min_sent, min_5d, require_pos_20d)
        if not ok:
            if log_rejections:
                logger.info("  Rejected %-6s — %s", ticker, reason)
            continue
        qualified.append({
            "ticker": ticker,
            "score": _score(row),
            "sentiment": float(row.get("sentiment_score", 0.0) or 0.0),
            "momentum_5d": float(row.get("mom_5d", 0.0) or 0.0),
            "momentum_20d": float(row.get("mom_20d", 0.0) or 0.0),
            "today_pct": float(row.get("today_pct", 0.0) or 0.0),
        })
    return qualified


def select_alpha_picks(watchlist_data: list[dict]) -> dict[str, float]:
    """Pick the final stocks and decide how to split the sleeve between them.

    First we try the strict filters (the config defaults). If literally nothing
    clears them, we loosen the bars to about 60% and try again — better to own a
    few okay names than to leave the sleeve empty. Only if even the relaxed pass
    comes up empty do we bail out, and that fires a loud alert.
    """
    if not watchlist_data:
        logger.warning("Alpha sleeve called with empty watchlist — no candidates to score")
        _log_alert("Watchlist empty when alpha sleeve ran — check trending discovery")
        return {}

    logger.info("Alpha sleeve: evaluating %d candidates (strict pass)", len(watchlist_data))
    qualified = _pass(
        watchlist_data,
        min_sent=ALPHA_MIN_SENTIMENT,
        min_5d=ALPHA_MIN_5D_MOMENTUM,
        require_pos_20d=ALPHA_REQUIRE_POSITIVE_20D,
        log_rejections=True,
    )

    relaxed_used = False
    if not qualified:
        # Nobody passed — so lower the bar rather than sit the day out. We cut the
        # sentiment/momentum thresholds by ~40% and stop insisting on a positive month.
        relaxed_sent = ALPHA_MIN_SENTIMENT * 0.6
        relaxed_5d = ALPHA_MIN_5D_MOMENTUM * 0.6
        logger.warning(
            "Strict filters produced 0 picks — retrying with relaxed thresholds "
            "(sent ≥ %.2f, 5d ≥ %.1f%%, 20d-positive off)",
            relaxed_sent, relaxed_5d * 100,
        )
        qualified = _pass(
            watchlist_data,
            min_sent=relaxed_sent,
            min_5d=relaxed_5d,
            require_pos_20d=False,
            log_rejections=False,
        )
        relaxed_used = True

    if not qualified:
        logger.warning("Alpha sleeve: NO picks even with relaxed filters — sleeve will be empty")
        _log_alert(
            f"Sleeve empty after relaxed pass — {len(watchlist_data)} candidates all rejected. "
            f"Top sentiment: {max((r.get('sentiment_score', 0) or 0) for r in watchlist_data):.2f}, "
            f"top 5d mom: {max((r.get('mom_5d', 0) or 0) for r in watchlist_data):.1%}"
        )
        return {}

    if relaxed_used:
        _log_alert(
            f"Strict filters failed today; using {len(qualified)} relaxed picks. "
            "Top names: " + ", ".join(p["ticker"] for p in qualified[:5])
        )

    qualified.sort(key=lambda r: -r["score"])
    picks = qualified[:ALPHA_SLEEVE_PICKS]

    # Hand out weight in proportion to score — the higher-rated names get more.
    total_score = sum(p["score"] for p in picks)
    raw_weights = {p["ticker"]: p["score"] / total_score for p in picks}

    # Don't let any single pick hog the sleeve. Note the cap is set as a slice of the
    # whole portfolio, so we convert it into a slice of just the sleeve here.
    sleeve_max = ALPHA_MAX_PER_STOCK / ALPHA_SLEEVE_PCT if ALPHA_SLEEVE_PCT > 0 else 1.0
    sleeve_max = min(sleeve_max, 1.0)
    capped = {t: min(w, sleeve_max) for t, w in raw_weights.items()}

    # After capping, scale the sleeve back up so it adds to 100% of itself.
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
    """Blend the ETF weights and the stock picks into one final target.

    We shrink every ETF weight by the sleeve percentage to free up room, then drop
    the stock picks into that space. The result still adds up to 100%.
    """
    if not ALPHA_SLEEVE_ENABLED:
        return etf_weights

    sleeve_picks = select_alpha_picks(watchlist_data)
    if not sleeve_picks:
        return etf_weights   # nothing made the cut today → just stay all-ETF

    # Make room: shrink the ETFs down to whatever's left after the sleeve's share.
    etf_scale = 1.0 - ALPHA_SLEEVE_PCT
    scaled_etfs = {t: w * etf_scale for t, w in etf_weights.items()}

    # Drop the stock picks into that freed-up space.
    combined = dict(scaled_etfs)
    for ticker, sleeve_w in sleeve_picks.items():
        combined[ticker] = combined.get(ticker, 0.0) + sleeve_w * ALPHA_SLEEVE_PCT

    # Tidy up so it sums to exactly 1.0 (it should already be basically there).
    total = sum(combined.values())
    if total > 0:
        combined = {t: w / total for t, w in combined.items()}

    logger.info(
        "Alpha sleeve active: %d picks taking %.0f%% of portfolio",
        len(sleeve_picks), ALPHA_SLEEVE_PCT * 100,
    )
    return combined
