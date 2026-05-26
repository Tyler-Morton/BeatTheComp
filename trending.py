"""Dynamic trending stocks discovery via Claude with web search.

Runs every morning before the watchlist scan. Asks Claude to identify
stocks making big moves today (earnings, M&A, breakouts, news) and adds
them to the watchlist alongside the static list.
"""

import json
import logging
import os
import re
from datetime import datetime

import anthropic

from config import TRENDING_MAX_PICKS

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
    """Quick sanity check — must be 1-5 uppercase letters."""
    return bool(_VALID_TICKER_RE.match(ticker))


def _extract_text(content: list) -> str:
    return " ".join(b.text for b in content if hasattr(b, "text"))


def _parse_response(text: str) -> tuple[list[str], dict[str, str]]:
    """Pull tickers + reasons out of Claude's response."""
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
    """Return list of {ticker, reason} for today's trending stocks.

    Empty list if API unavailable or discovery fails — main pipeline falls
    back to just the static WATCHLIST.
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        logger.warning("No ANTHROPIC_API_KEY — skipping trending discovery")
        return []

    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model=MODEL,
            max_tokens=3000,   # was 1500 — need more tokens for 30 picks + reasons
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
            messages=[{"role": "user", "content": _build_prompt()}],
        )
        text = _extract_text(response.content)
        tickers, reasons = _parse_response(text)

        if not tickers:
            logger.warning("Trending discovery returned no valid tickers")
            return []

        result = [{"ticker": t, "reason": reasons.get(t, "trending")} for t in tickers]
        logger.info("Discovered %d trending stocks today:", len(result))
        for r in result:
            logger.info("  + %-6s — %s", r["ticker"], r["reason"][:80])
        return result

    except Exception as exc:
        logger.warning("Trending discovery failed: %s", exc)
        return []
