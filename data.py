"""Price data. Alpaca first, then yfinance, then a saved copy of the last good prices, so a bad
day at one source doesn't take the whole bot down.
"""

import logging
import time
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import requests
import yfinance as yf

logger = logging.getLogger(__name__)

# Latest prices saved to disk. They stay between runs so the dashboard can read prices
# without hitting yfinance itself.
PRICE_CACHE = Path(__file__).parent / "prices_cache.parquet"

# Browser-like headers. yfinance throttles anything that looks like a bot, and without these
# it starts returning "Too Many Requests" within seconds.
_yf_session = requests.Session()
_yf_session.headers.update({
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
})


def save_price_cache(prices: pd.DataFrame) -> None:
    try:
        prices.to_parquet(PRICE_CACHE)
        logger.info("Saved %d days × %d tickers to %s",
                    len(prices), len(prices.columns), PRICE_CACHE.name)
    except Exception as exc:
        logger.warning("Could not save price cache: %s", exc)


def load_price_cache(max_age_hours: float = 6.0) -> pd.DataFrame | None:
    """Read the saved prices back, but only if they're recent enough to trust."""
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
    """Daily closes from Alpaca's IEX feed, our main source.

    Every ticker comes in one batch, where yfinance goes one at a time.
    """
    import os
    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.data.requests import StockBarsRequest
    from alpaca.data.timeframe import TimeFrame
    from alpaca.data.enums import Adjustment, DataFeed

    client = StockHistoricalDataClient(
        api_key=os.getenv("ALPACA_API_KEY"),
        secret_key=os.getenv("ALPACA_SECRET_KEY"),
    )

    req = StockBarsRequest(
        symbol_or_symbols=list(tickers),
        timeframe=TimeFrame.Day,
        start=datetime.strptime(start, "%Y-%m-%d"),
        end=datetime.strptime(end, "%Y-%m-%d") - timedelta(minutes=20),
        feed=DataFeed.IEX,
        # Without this Alpaca returns raw prices and a split looks like a crash. VGT's 8:1 split
        # read as a -87.5% day and TQQQ's 2:1 as -50%, which poisoned every covariance and
        # momentum number built on top.
        adjustment=Adjustment.ALL,
    )
    bars = client.get_stock_bars(req).df
    if bars.empty:
        raise RuntimeError("Alpaca returned empty bars")

    # Alpaca returns everything stacked. Reshape it to one column of closes per ticker.
    frames: dict[str, pd.Series] = {}
    for t in tickers:
        try:
            sub = bars.xs(t, level=0)["close"].sort_index()
            if sub.index.tz is not None:
                sub.index = sub.index.tz_localize(None)
            sub.index = pd.to_datetime(sub.index.date)
            frames[t] = sub
        except KeyError:
            logger.warning("No Alpaca data for %s — skipping", t)
    if not frames:
        raise RuntimeError("No tickers retrievable from Alpaca")
    prices = pd.DataFrame(frames).ffill().dropna(how="all")
    _check_for_split_artifacts(prices, "Alpaca")
    return prices


# A one-day move past this is treated as a split or a bad bar. The Alpaca table gets refused and
# the run falls back to yfinance. Real moves can pass it too: SOXL rose 54.8% on 2025-04-09.
MAX_PLAUSIBLE_DAILY_MOVE = 0.45


def _check_for_split_artifacts(prices: pd.DataFrame, source: str) -> None:
    """Refuse a price table that contains a split-sized one-day jump."""
    moves = prices.pct_change().abs().max()
    bad = moves[moves > MAX_PLAUSIBLE_DAILY_MOVE]
    if not bad.empty:
        raise RuntimeError(
            f"{source} prices have implausible one-day moves (split or bad bar?): "
            + ", ".join(f"{t} {m:.0%}" for t, m in bad.items()))


def _yfinance_download(
    tickers: list[str], start: str, end: str, retries: int = 3,
) -> pd.DataFrame:
    """Backup source, only used when Alpaca fails.

    Goes ticker by ticker with retries and the browser-header session, since yfinance is flaky
    and quick to throttle.
    """
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
    """Try Alpaca first. If it raises for any reason, switch to yfinance."""
    try:
        logger.info("Fetching prices via Alpaca IEX (%d tickers)...", len(tickers))
        return _alpaca_download(tickers, start, end)
    except Exception as exc:
        logger.warning("Alpaca fetch failed: %s — falling back to yfinance", exc)
        return _yfinance_download(tickers, start, end, retries)


def fetch_prices(tickers: list[str], lookback_days: int = 252) -> pd.DataFrame:
    """Adjusted closes. This is the main way the bot asks for prices.

    If both live sources are down, falls back to the saved copy so a run can still go on
    slightly stale data.
    """
    end = datetime.today()
    start = end - timedelta(days=lookback_days + 90)
    try:
        return fetch_prices_range(tickers, start, end, tail=lookback_days)
    except RuntimeError as exc:
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
    """Like fetch_prices, but for an exact start/end window (handy for backtests)."""
    prices = _batch_download(
        tickers,
        start=start.strftime("%Y-%m-%d"),
        end=end.strftime("%Y-%m-%d"),
    )
    if tail:
        prices = prices.tail(tail)
    return prices


def get_returns(prices: pd.DataFrame) -> pd.DataFrame:
    """Day-over-day percent changes, dropping any row with a NaN."""
    return prices.pct_change().dropna()
