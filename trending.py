"""Trending-stock discovery with Claude and web search. Disabled (TRENDING_DISCOVERY_ENABLED).

When on, it runs before the watchlist scan, asks Claude what's moving right now (earnings pops,
buyouts, news) and adds those names to the small permanent watchlist.
"""

import json
import logging
import os
import re
from datetime import datetime
from pathlib import Path

import anthropic

from config import ALERTS_LOG, TRENDING_MAX_PICKS

TRENDING_RAW_LOG = Path(__file__).parent / "trending_raw.csv"


def _log_alert(message: str) -> None:
    """Write to the alerts file when discovery goes wrong."""
    try:
        with open(ALERTS_LOG, "a") as f:
            f.write(f"{datetime.now().isoformat()} | TRENDING: {message}\n")
    except Exception:
        pass


def _log_raw_candidates(tickers: list[str], reasons: dict[str, str]) -> None:
    """Save the names that passed _parse_response's ticker check and TRENDING_MAX_PICKS cut.

    If we later wonder why the bot didn't pick X, this shows whether X made it that far that
    morning.
    """
    try:
        new_file = not TRENDING_RAW_LOG.exists()
        with open(TRENDING_RAW_LOG, "a") as f:
            if new_file:
                f.write("timestamp,ticker,reason\n")
            ts = datetime.now().isoformat()
            for t in tickers:
                reason = (reasons.get(t, "") or "").replace(",", ";").replace("\n", " ")
                f.write(f"{ts},{t},{reason}\n")
    except Exception as exc:
        logger.warning("Could not write trending_raw.csv: %s", exc)

logger = logging.getLogger(__name__)

MODEL = "claude-haiku-4-5-20251001"


def _build_prompt() -> str:
    today = datetime.now().strftime("%B %d, %Y")
    return (
        f"It's {today}. Search the web for the {TRENDING_MAX_PICKS} most\n"
        f"actively traded / talked-about / surging US stocks RIGHT NOW.\n\n"
        f"Goal: build a watchlist of stocks with the highest chance of moving today\n"
        f"or this week. FRESH names — avoid stale picks from last week unless still\n"
        f"clearly trending.\n\n"
        f"Pull from ALL these categories — diversify across them:\n"
        f"  1. TOP DAILY GAINERS — biggest % gainers from yesterday's close\n"
        f"  2. UNUSUAL VOLUME — stocks with 5x+ normal trading volume\n"
        f"  3. EARNINGS WINNERS — beat last quarter, rallying since\n"
        f"  4. M&A / DEAL NEWS — merger announcements, buyouts, partnerships\n"
        f"  5. FDA / REGULATORY — drug approvals, contract wins, government deals\n"
        f"  6. SECTOR LEADERS — strongest stock in a sector that's currently hot\n"
        f"     (AI chips, quantum, defense, biotech, energy, crypto, etc.)\n"
        f"  7. SOCIAL MEDIA / RETAIL — names trending on Reddit, X, StockTwits\n"
        f"  8. ANALYST UPGRADES — recent target raises with price impact\n"
        f"  9. TECHNICAL BREAKOUTS — stocks breaking out to 52-week highs\n"
        f" 10. INDUSTRY SPECIFIC — small caps making waves in a specific industry\n\n"
        f"Return JSON only:\n"
        f"{{\n"
        f'  "tickers": ["TICKER1", "TICKER2", ...],\n'
        f'  "reasons": {{"TICKER1": "specific reason — news/move/catalyst", ...}}\n'
        f"}}\n\n"
        f"Hard rules:\n"
        f"- US-listed only (NYSE/NASDAQ), no crypto coins, no foreign tickers\n"
        f"- Tradable on Alpaca — common stock or ETFs only, no warrants\n"
        f"- 1-5 letter uppercase tickers\n"
        f"- DIVERSIFY: spread picks across multiple sectors, don't dump all into one theme\n"
        f"- AVOID the obvious mega-caps (AAPL/MSFT/GOOGL/AMZN) unless they're actually surging\n"
        f"- PREFER mid-cap and high-momentum names over $200B+ giants\n"
        f"- Each pick must have a SPECIFIC, RECENT (last 3 days) catalyst\n"
    )


_VALID_TICKER_RE = re.compile(r"^[A-Z]{1,5}$")


def _validate_ticker(ticker: str) -> bool:
    """A real ticker is just 1-5 capital letters."""
    return bool(_VALID_TICKER_RE.match(ticker))


def _extract_text(content: list) -> str:
    return " ".join(b.text for b in content if hasattr(b, "text"))


def _parse_response(text: str) -> tuple[list[str], dict[str, str]]:
    """Pull the ticker list and the reasons out of Claude's reply."""
    matches = re.findall(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", text, re.DOTALL)
    for m in matches:
        try:
            data = json.loads(m)
            if "tickers" in data and isinstance(data["tickers"], list):
                tickers = [t.upper() for t in data["tickers"] if _validate_ticker(t.upper())]
                reasons = data.get("reasons", {})
                return tickers[:TRENDING_MAX_PICKS], reasons
        except json.JSONDecodeError:
            continue
    return [], {}


def discover_trending() -> list[dict]:
    """Today's trending names, as a list of {ticker, reason}.

    If the API is down or something breaks it returns an empty list, and the run carries on with
    the small permanent watchlist.
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        logger.warning("No ANTHROPIC_API_KEY — skipping trending discovery")
        _log_alert("No ANTHROPIC_API_KEY — discovery skipped, alpha sleeve will be empty")
        return []

    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model=MODEL,
            max_tokens=3000,   # enough for 30 picks plus reasons
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
            messages=[{"role": "user", "content": _build_prompt()}],
        )
        text = _extract_text(response.content)
        tickers, reasons = _parse_response(text)

        # Record what came back no matter what.
        _log_raw_candidates(tickers, reasons)

        if not tickers:
            logger.warning("Trending discovery returned no valid tickers")
            _log_alert(
                f"Discovery returned 0 valid tickers. Response head: {text[:200]!r}"
            )
            return []

        result = [{"ticker": t, "reason": reasons.get(t, "trending")} for t in tickers]
        logger.info("Discovered %d trending stocks today:", len(result))
        for r in result:
            logger.info("  + %-6s — %s", r["ticker"], r["reason"][:80])
        return result

    except Exception as exc:
        logger.warning("Trending discovery failed: %s", exc)
        _log_alert(f"Discovery exception: {type(exc).__name__}: {exc}")
        return []
