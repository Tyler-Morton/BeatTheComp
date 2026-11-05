"""News sentiment for each stock, using Claude with web search. Off right now (SENTIMENT_ENABLED).

Claude reads the last day of headlines for each ticker and scores how bullish or bearish they are.
All tickers go in one batch, half the price of separate calls. If it fails, we call one at a time.
"""

import csv
import json
import logging
import os
import re
import time
from datetime import datetime
from pathlib import Path

import anthropic

from config import SENTIMENT_LOG, SENTIMENT_ENABLED

logger = logging.getLogger(__name__)

MODEL = "claude-haiku-4-5-20251001"
MAX_TOKENS = 600
BATCH_TIMEOUT_SEC = 600
POLL_INTERVAL_SEC = 8


def _build_prompt(ticker: str) -> str:
    return (
        f"Search news for {ticker} in the last 24 hours. "
        "Return JSON only, no preamble:\n"
        "{\n"
        '  "score": <float -1.0 to 1.0>,\n'
        '  "confidence": <float 0.0 to 1.0>,\n'
        '  "summary": "<one sentence>",\n'
        '  "key_headlines": ["<headline1>", "<headline2>", "<headline3>"]\n'
        "}\n"
        "Consider: earnings, analyst calls, macro events, sector news.\n"
        "-1.0 = very bearish, 0.0 = neutral, 1.0 = very bullish"
    )


def _parse_json(text: str) -> dict:
    """Pull the JSON answer out of Claude's reply.

    Models sometimes wrap the JSON in extra text, so look for the {...} block first.
    """
    # Find {...} chunks. The regex handles objects nested one level deep. Arrays are fine since they
    # have no braces, and anything nested deeper won't match as a whole.
    matches = re.findall(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", text, re.DOTALL)
    for m in matches:
        try:
            data = json.loads(m)
            if isinstance(data, dict) and "score" in data:
                return data
        except json.JSONDecodeError:
            continue
    # Nothing matched, so last try: the whole reply as JSON.
    try:
        return json.loads(text.strip())
    except Exception:
        pass
    return {"score": 0.0, "confidence": 0.0, "summary": "parse error", "key_headlines": []}


def _extract_text(content: list) -> str:
    parts = []
    for block in content:
        if hasattr(block, "text"):
            parts.append(block.text)
    return " ".join(parts)


def _default_result() -> dict:
    return {"score": 0.0, "confidence": 0.0, "summary": "unavailable", "key_headlines": []}


def _run_batch(client: anthropic.Anthropic, tickers: list[str]) -> dict[str, dict]:
    """Send every ticker in a single batch, then wait for the results."""
    requests = [
        {
            "custom_id": ticker,
            "params": {
                "model": MODEL,
                "max_tokens": MAX_TOKENS,
                "tools": [{"type": "web_search_20250305", "name": "web_search"}],
                "messages": [{"role": "user", "content": _build_prompt(ticker)}],
            },
        }
        for ticker in tickers
    ]

    batch = client.messages.batches.create(requests=requests)
    logger.info("Batch %s submitted (%d tickers)", batch.id, len(tickers))

    deadline = time.time() + BATCH_TIMEOUT_SEC
    while True:
        batch = client.messages.batches.retrieve(batch.id)
        if batch.processing_status == "ended":
            break
        if time.time() > deadline:
            raise TimeoutError(f"Batch {batch.id} timed out after {BATCH_TIMEOUT_SEC}s")
        time.sleep(POLL_INTERVAL_SEC)

    results: dict[str, dict] = {}
    for item in client.messages.batches.results(batch.id):
        ticker = item.custom_id
        if item.result.type == "succeeded":
            text = _extract_text(item.result.message.content)
            results[ticker] = _parse_json(text)
        else:
            logger.warning("Batch result failed for %s: %s", ticker, item.result.type)
            results[ticker] = _default_result()
    return results


def _run_sync(client: anthropic.Anthropic, tickers: list[str]) -> dict[str, dict]:
    """Fallback for when the batch fails: ask about each ticker separately."""
    results: dict[str, dict] = {}
    for ticker in tickers:
        try:
            response = client.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                tools=[{"type": "web_search_20250305", "name": "web_search"}],
                messages=[{"role": "user", "content": _build_prompt(ticker)}],
            )
            text = _extract_text(response.content)
            results[ticker] = _parse_json(text)
        except Exception as exc:
            logger.warning("Sync sentiment failed for %s: %s", ticker, exc)
            results[ticker] = _default_result()
    return results


def _log_results(results: dict[str, dict]) -> None:
    path = Path(SENTIMENT_LOG)
    write_header = not path.exists()
    now = datetime.now().isoformat()
    with open(path, "a", newline="") as f:
        fields = ["timestamp", "ticker", "score", "confidence", "summary"]
        w = csv.DictWriter(f, fieldnames=fields)
        if write_header:
            w.writeheader()
        for ticker, data in results.items():
            w.writerow({
                "timestamp": now,
                "ticker": ticker,
                "score": data.get("score", 0.0),
                "confidence": data.get("confidence", 0.0),
                "summary": data.get("summary", ""),
            })


def run_sentiment_analysis(tickers: list[str]) -> dict[str, dict]:
    """Returns {ticker: {score, confidence, summary, key_headlines}}.

    Tries the batch, then sync calls. If both fail it returns neutral scores so the run can keep
    going.
    """
    if not SENTIMENT_ENABLED:
        # Sentiment is off: neutral scores for everything and no API calls. Neutral scores have
        # no effect on the optimizer, so the bot trades as if sentiment weren't there.
        return {t: _default_result() for t in tickers}

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        logger.error("ANTHROPIC_API_KEY not set — returning neutral sentiment")
        return {t: _default_result() for t in tickers}

    client = anthropic.Anthropic(api_key=api_key)

    try:
        results = _run_batch(client, tickers)
    except Exception as exc:
        logger.warning("Batch API failed (%s) — falling back to sync calls", exc)
        try:
            results = _run_sync(client, tickers)
        except Exception as exc2:
            logger.error("Sync fallback also failed: %s", exc2)
            results = {t: _default_result() for t in tickers}

    _log_results(results)

    for ticker, data in results.items():
        logger.info(
            "Sentiment  %-6s  score=%.2f  conf=%.2f  %s",
            ticker, (data.get("score") or 0.0), (data.get("confidence") or 0.0), data.get("summary", ""),
        )
    return results
