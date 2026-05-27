import logging
import time
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import requests
import yfinance as yf

logger = logging.getLogger(__name__)

# Disk price cache — survives across runs, lets dashboard avoid yfinance hits
PRICE_CACHE = Path(__file__).parent / "prices_cache.parquet"

# Browser-like session header — defeats yfinance's bot detection rate limiter.
# Without this, yfinance returns "Too Many Requests" within seconds.
_yf_session = requests.Session()
_yf_session.headers.update({
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
})


def save_price_cache(prices: pd.DataFrame) -> None:
    """Persist most recent price snapshot to disk for dashboard use."""
    try:
        prices.to_parquet(PRICE_CACHE)
        logger.info("Saved %d days × %d tickers to %s",
                    len(prices), len(prices.columns), PRICE_CACHE.name)
    except Exception as exc:
        logger.warning("Could not save price cache: %s", exc)


def load_price_cache(max_age_hours: float = 6.0) -> pd.DataFrame | None:
    """Return cached prices if fresh enough, else None."""
    if not PRICE_CACHE.exists():
        return None
    age_hours = (time.time() - PRICE_CACHE.stat().st_mtime) / 3600
    if age_hours > max_age_hours:
        logger.info("Price cache is %.1fh old — too stale", age_hours)
        return None
    try:
        return pd.read_parquet(PRICE_CACHE)
    except Exception as exc:
        logger.warning("Could not read price cache: %s", exc)
        return None


def _batch_download(
    tickers: list[str],
    start: str,
    end: str,
    retries: int = 3,
) -> pd.DataFrame:
    """Download all tickers in one request — far less likely to hit rate limits.
    Falls back to one-by-one with delays if batch fails.
    """
    # Per-ticker download with browser session — most reliable approach
    # (batch yf.download() doesn't accept session= so it gets rate-limited)
    frames: list[pd.Series] = []
    missing = []
    for ticker in tickers:
        for attempt in range(retries):
            try:
                tick = yf.Ticker(ticker, session=_yf_session)
                hist = tick.history(start=start, end=end, auto_adjust=True)
                if not hist.empty and "Close" in hist:
                    close = hist["Close"]
                    if not close.isna().all():
                        if close.index.tz is not None:
                            close.index = close.index.tz_localize(None)
                        frames.append(close.rename(ticker))
                        break
                else:
                    missing.append(ticker)
                    break
            except Exception as exc:
                wait = 2 ** attempt
                logger.warning("Failed %s (attempt %d): %s — retrying in %ds", ticker, attempt + 1, exc, wait)
                time.sleep(wait)

    for t in missing:
        logger.warning("No data for %s — skipping", t)
    if not frames:
        raise RuntimeError("No price data could be fetched for any ticker.")
    return pd.concat(frames, axis=1).ffill().dropna(how="all")


def fetch_prices(tickers: list[str], lookback_days: int = 252) -> pd.DataFrame:
    """Return adjusted closing prices. Uses disk cache as fallback if yfinance fails."""
    end = datetime.today()
    start = end - timedelta(days=lookback_days + 90)
    try:
        return fetch_prices_range(tickers, start, end, tail=lookback_days)
    except RuntimeError as exc:
        # yfinance fully blocked — try disk cache as last resort
        logger.warning("yfinance fetch failed: %s — trying disk cache", exc)
        cached = load_price_cache(max_age_hours=48)
        if cached is None:
            raise
        cols = [t for t in tickers if t in cached.columns]
        if len(cols) < 3:
            raise RuntimeError(f"Cache only has {len(cols)} of {len(tickers)} requested tickers")
        logger.info("Using cache with %d/%d tickers (skipping %s)",
                    len(cols), len(tickers), set(tickers) - set(cols))
        return cached[cols].tail(lookback_days)


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
