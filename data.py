import logging
import time
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)


def _batch_download(
    tickers: list[str],
    start: str,
    end: str,
    retries: int = 3,
) -> pd.DataFrame:
    """Download all tickers in one request — far less likely to hit rate limits.
    Falls back to one-by-one with delays if batch fails.
    """
    # Try batch first
    for attempt in range(retries):
        try:
            raw = yf.download(
                tickers,
                start=start,
                end=end,
                auto_adjust=True,
                progress=False,
                multi_level_index=True,
            )
            if raw.empty:
                raise ValueError("Empty response")

            # Multi-ticker download returns MultiIndex columns: (Field, Ticker)
            if isinstance(raw.columns, pd.MultiIndex):
                close = raw["Close"]
            else:
                # Single ticker — wrap in DataFrame
                close = raw[["Close"]].rename(columns={"Close": tickers[0]})

            close = close.ffill().dropna(how="all")
            missing = set(tickers) - set(close.columns)
            for t in missing:
                logger.warning("No data for %s — skipping", t)
            return close

        except Exception as exc:
            wait = 2 ** attempt
            logger.warning("Batch download attempt %d failed: %s — retrying in %ds", attempt + 1, exc, wait)
            time.sleep(wait)

    # Fallback: one ticker at a time with delays
    logger.warning("Batch failed — falling back to individual downloads")
    frames: list[pd.Series] = []
    for ticker in tickers:
        for attempt in range(retries):
            try:
                raw = yf.download(
                    ticker,
                    start=start,
                    end=end,
                    auto_adjust=True,
                    progress=False,
                    multi_level_index=False,
                )
                if not raw.empty:
                    close = raw["Close"]
                    if isinstance(close, pd.DataFrame):
                        close = close.squeeze()
                    if not close.isna().all():
                        frames.append(close.rename(ticker))
                break
            except Exception as exc:
                wait = 2 ** attempt
                logger.warning("Failed %s (attempt %d): %s — retrying in %ds", ticker, attempt + 1, exc, wait)
                time.sleep(wait)
        time.sleep(0.5)   # gentle delay between tickers

    if not frames:
        raise RuntimeError("No price data could be fetched for any ticker.")
    return pd.concat(frames, axis=1).ffill().dropna(how="all")


def fetch_prices(tickers: list[str], lookback_days: int = 252) -> pd.DataFrame:
    """Return a DataFrame of adjusted closing prices (cols = tickers)."""
    end = datetime.today()
    start = end - timedelta(days=lookback_days + 90)
    return fetch_prices_range(tickers, start, end, tail=lookback_days)


def fetch_prices_range(
    tickers: list[str],
    start: datetime,
    end: datetime,
    tail: int | None = None,
) -> pd.DataFrame:
    """Fetch adjusted close prices for a date range."""
    prices = _batch_download(
        tickers,
        start=start.strftime("%Y-%m-%d"),
        end=end.strftime("%Y-%m-%d"),
    )
    if tail:
        prices = prices.tail(tail)
    return prices


def get_returns(prices: pd.DataFrame) -> pd.DataFrame:
    """Simple daily percentage returns, NaN rows dropped."""
    return prices.pct_change().dropna()
