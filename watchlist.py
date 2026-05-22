"""Watchlist scanner — alerts only, never auto-trades."""

import csv
import logging
import os
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

from config import WATCHLIST, WATCHLIST_ALERTS, WATCHLIST_LOG

logger = logging.getLogger(__name__)

ALERT_DAILY_MOVE = 0.10
ALERT_SENTIMENT = 0.75
ALERT_5D_MOM = 0.15


def _fetch_ticker_data(ticker: str) -> dict | None:
    try:
        raw = yf.download(ticker, period="30d", auto_adjust=True, progress=False, multi_level_index=False)
        if raw.empty or len(raw) < 5:
            return None
        close = raw["Close"]
        today_pct = float((close.iloc[-1] / close.iloc[-2]) - 1) if len(close) >= 2 else 0.0
        mom5d = float((close.iloc[-1] / close.iloc[-6]) - 1) if len(close) >= 6 else 0.0
        mom20d = float((close.iloc[-1] / close.iloc[-21]) - 1) if len(close) >= 21 else 0.0
        return {
            "ticker": ticker,
            "price": float(close.iloc[-1]),
            "today_pct": today_pct,
            "mom_5d": mom5d,
            "mom_20d": mom20d,
        }
    except Exception as exc:
        logger.warning("Failed to fetch watchlist data for %s: %s", ticker, exc)
        return None


def _get_sentiment(ticker: str) -> dict:
    """Single-ticker sentiment call reusing the same prompt as sentiment.py."""
    import anthropic
    from sentiment import MODEL, MAX_TOKENS, _build_prompt, _extract_text, _parse_json, _default_result

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return _default_result()
    client = anthropic.Anthropic(api_key=api_key)
    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
            messages=[{"role": "user", "content": _build_prompt(ticker)}],
        )
        return _parse_json(_extract_text(response.content))
    except Exception as exc:
        logger.warning("Watchlist sentiment failed for %s: %s", ticker, exc)
        return _default_result()


def _check_alerts(data: dict, sentiment: dict) -> list[str]:
    reasons: list[str] = []
    score = sentiment.get("score", 0.0)

    if abs(data["today_pct"]) >= ALERT_DAILY_MOVE:
        reasons.append(f"single-day move {data['today_pct']:+.1%}")
    if abs(score) >= ALERT_SENTIMENT:
        reasons.append(f"sentiment score {score:+.2f}")
    if data["mom_5d"] >= ALERT_5D_MOM:
        reasons.append(f"5d momentum {data['mom_5d']:+.1%}")
    return reasons


def _write_log(rows: list[dict]) -> None:
    path = Path(WATCHLIST_LOG)
    write_header = not path.exists()
    with open(path, "a", newline="") as f:
        fields = ["timestamp", "ticker", "price", "today_pct", "mom_5d", "mom_20d", "sentiment_score", "sentiment_summary"]
        w = csv.DictWriter(f, fieldnames=fields)
        if write_header:
            w.writeheader()
        w.writerows(rows)


def _write_alerts(alerts: list[dict]) -> None:
    if not alerts:
        return
    path = Path(WATCHLIST_ALERTS)
    write_header = not path.exists()
    with open(path, "a", newline="") as f:
        fields = ["timestamp", "ticker", "price", "today_pct", "mom_5d", "sentiment_score", "reason"]
        w = csv.DictWriter(f, fieldnames=fields)
        if write_header:
            w.writeheader()
        w.writerows(alerts)


def scan_watchlist(tickers: list[str] | None = None) -> list[dict]:
    """Scan watchlist tickers, write logs/alerts, return FULL scan data (one row per ticker).

    Returned list is used by alpha_sleeve.py to pick top stocks. Each row has
    ticker, price, today_pct, mom_5d, mom_20d, sentiment_score, sentiment_summary.
    """
    if tickers is None:
        tickers = WATCHLIST

    log_rows: list[dict] = []
    alert_rows: list[dict] = []
    now = datetime.now().isoformat()

    for ticker in tickers:
        data = _fetch_ticker_data(ticker)
        if data is None:
            continue
        sentiment = _get_sentiment(ticker)
        score = sentiment.get("score", 0.0)
        summary = sentiment.get("summary", "")

        row = {
            "timestamp": now,
            "ticker": ticker,
            "price": round(data["price"], 2),
            "today_pct": round(data["today_pct"], 4),
            "mom_5d": round(data["mom_5d"], 4),
            "mom_20d": round(data["mom_20d"], 4),
            "sentiment_score": round(score, 3),
            "sentiment_summary": summary,
        }
        log_rows.append(row)

        reasons = _check_alerts(data, sentiment)
        if reasons:
            alert_rows.append({
                "timestamp": now,
                "ticker": ticker,
                "price": round(data["price"], 2),
                "today_pct": round(data["today_pct"], 4),
                "mom_5d": round(data["mom_5d"], 4),
                "sentiment_score": round(score, 3),
                "reason": "; ".join(reasons),
            })
            logger.info("ALERT  %-6s  %s", ticker, "; ".join(reasons))

    _write_log(log_rows)
    _write_alerts(alert_rows)
    logger.info("Watchlist scan complete — %d tickers, %d alerts", len(log_rows), len(alert_rows))
    return log_rows   # full scan data, not just alerts
