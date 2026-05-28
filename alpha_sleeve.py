"""Alpha sleeve — allocates a small % of the portfolio to top watchlist stocks.

Filters by sentiment + momentum, caps per-stock exposure, and merges into
the main ETF weights so the broker can execute everything in one rebalance.
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
    """Return (passes, reject_reason) for a single watchlist row at given thresholds."""
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
    """Composite: bullish news + sustained trend, penalize chasing today's spike."""
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
    """Run watchlist through filters at given thresholds. Returns qualifiers."""
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
    """Return {ticker: weight_within_sleeve} for top qualifying watchlist stocks.

    Tries strict filters first (config defaults). If that returns nothing,
    falls back to a relaxed pass (~60% of each threshold). Empty dict only if
    even the relaxed pass produces nothing — which triggers a loud alert.
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
        # Relaxed fallback: better to take moderate-conviction picks than nothing.
        # Cuts sentiment/momentum bars ~40%, drops the positive-20d requirement.
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
