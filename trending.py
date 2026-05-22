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
        f"It's {today}. Search the web for US stocks that are TRENDING today "
        f"because of news, big moves, or events.\n\n"
        f"Find {TRENDING_MAX_PICKS} stocks that match ANY of these criteria:\n"
        f"- Up or down more than 5% on news today\n"
        f"- Major M&A announcement, merger, or buyout\n"
        f"- Earnings beat or miss with big stock reaction\n"
        f"- FDA approval, contract win, or regulatory news\n"
        f"- IPO, SPAC, or breakout from technical resistance\n"
        f"- Major analyst upgrade/downgrade with price impact\n\n"
        f"Return JSON only, no preamble:\n"
        f"{{\n"
        f'  "tickers": ["TICKER1", "TICKER2", ...],\n'
        f'  "reasons": {{"TICKER1": "one sentence why", "TICKER2": "..."}}\n'
        f"}}\n\n"
        f"Rules:\n"
        f"- ONLY valid US stock tickers (NYSE/NASDAQ), no crypto, no foreign\n"
        f"- ONLY tradable common stock or ETFs, no warrants/rights\n"
        f"- Each ticker must be 1-5 letters, all uppercase\n"
        f"- Skip if you can't find {TRENDING_MAX_PICKS} good picks — quality over quantity\n"
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
            max_tokens=1500,
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
