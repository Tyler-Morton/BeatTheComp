"""Sentiment analysis via Claude Batch API with web search.

One batch call per run — all tickers in a single request for 50% cost savings.
Falls back to individual synchronous calls if batch mode fails.
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

from config import SENTIMENT_LOG

logger = logging.getLogger(__name__)

MODEL = "claude-haiku-4-5-20251001"
MAX_TOKENS = 600
BATCH_TIMEOUT_SEC = 600   # 10 min max wait
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
    """Extract JSON object from model text output."""
    match = re.search(r"\{.*?\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    return {"score": 0.0, "confidence": 0.0, "summary": "parse error", "key_headlines": []}


def _extract_text(content: list) -> str:
    """Pull all text blocks from a message content list."""
    parts = []
    for block in content:
        if hasattr(block, "text"):
            parts.append(block.text)
    return " ".join(parts)


def _default_result() -> dict:
    return {"score": 0.0, "confidence": 0.0, "summary": "unavailable", "key_headlines": []}


# ── Batch path ─────────────────────────────────────────────────────────────────

def _run_batch(client: anthropic.Anthropic, tickers: list[str]) -> dict[str, dict]:
    """Submit a message batch and poll until complete."""
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


# ── Synchronous fallback ───────────────────────────────────────────────────────

def _run_sync(client: anthropic.Anthropic, tickers: list[str]) -> dict[str, dict]:
    """Individual synchronous calls — used when batch fails."""
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


# ── Logging ────────────────────────────────────────────────────────────────────

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


# ── Public API ─────────────────────────────────────────────────────────────────

def run_sentiment_analysis(tickers: list[str]) -> dict[str, dict]:
    """Return {ticker: {score, confidence, summary, key_headlines}} for each ticker."""
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
            ticker, data.get("score", 0.0), data.get("confidence", 0.0), data.get("summary", ""),
        )
    return results
