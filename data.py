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


def _alpaca_download(tickers: list[str], start: str, end: str) -> pd.DataFrame:
    """Fetch daily close prices from Alpaca's IEX feed.
    Free with paper account, no rate limits, fast batch download.
    """
    import os
    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.data.requests import StockBarsRequest
    from alpaca.data.timeframe import TimeFrame
    from alpaca.data.enums import DataFeed

    client = StockHistoricalDataClient(
        api_key=os.getenv("ALPACA_API_KEY"),
        secret_key=os.getenv("ALPACA_SECRET_KEY"),
    )

    req = StockBarsRequest(
        symbol_or_symbols=list(tickers),
        timeframe=TimeFrame.Day,
        start=datetime.strptime(start, "%Y-%m-%d"),
        end=datetime.strptime(end, "%Y-%m-%d") - timedelta(minutes=20),  # IEX delay buffer
        feed=DataFeed.IEX,
    )
    bars = client.get_stock_bars(req).df
    if bars.empty:
        raise RuntimeError("Alpaca returned empty bars")

    # Pivot to ticker columns with close prices
    frames: dict[str, pd.Series] = {}
    for t in tickers:
        try:
            sub = bars.xs(t, level=0)["close"].sort_index()
            if sub.index.tz is not None:
                sub.index = sub.index.tz_localize(None)
            sub.index = pd.to_datetime(sub.index.date)   # date-only index
            frames[t] = sub
        except KeyError:
            logger.warning("No Alpaca data for %s — skipping", t)
    if not frames:
        raise RuntimeError("No tickers retrievable from Alpaca")
    return pd.DataFrame(frames).ffill().dropna(how="all")


def _yfinance_download(
    tickers: list[str], start: str, end: str, retries: int = 3,
) -> pd.DataFrame:
    """Fallback yfinance fetcher with browser session."""
    frames: list[pd.Series] = []
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
            except Exception as exc:
                wait = 2 ** attempt
                logger.warning("Failed %s (attempt %d): %s", ticker, attempt + 1, exc)
                time.sleep(wait)
    if not frames:
        raise RuntimeError("No price data could be fetched for any ticker.")
    return pd.concat(frames, axis=1).ffill().dropna(how="all")


def _batch_download(tickers: list[str], start: str, end: str, retries: int = 3) -> pd.DataFrame:
    """Try Alpaca IEX first (free + reliable), fall back to yfinance if it fails."""
    try:
        logger.info("Fetching prices via Alpaca IEX (%d tickers)...", len(tickers))
        return _alpaca_download(tickers, start, end)
    except Exception as exc:
        logger.warning("Alpaca fetch failed: %s — falling back to yfinance", exc)
        return _yfinance_download(tickers, start, end, retries)


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
