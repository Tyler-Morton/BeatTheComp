import logging
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)


def fetch_prices(tickers: list[str], lookback_days: int = 252) -> pd.DataFrame:
    """Return a DataFrame of adjusted closing prices (cols = tickers).

    Drops any ticker for which yfinance returns no data and logs a warning.
    Raises RuntimeError only when *all* tickers fail.
    """
    end = datetime.today()
    start = end - timedelta(days=lookback_days + 90)  # buffer for weekends/holidays
    return fetch_prices_range(tickers, start, end, tail=lookback_days)


def fetch_prices_range(
    tickers: list[str],
    start: datetime,
    end: datetime,
    tail: int | None = None,
) -> pd.DataFrame:
    """Fetch adjusted close prices for a date range, dropping failed tickers."""
    frames: list[pd.Series] = []
    for ticker in tickers:
        try:
            raw = yf.download(
                ticker,
                start=start.strftime("%Y-%m-%d"),
                end=end.strftime("%Y-%m-%d"),
                auto_adjust=True,
                progress=False,
                multi_level_index=False,
            )
            if raw.empty:
                logger.warning("No data for %s — skipping", ticker)
                continue
            close = raw["Close"]
            if isinstance(close, pd.DataFrame):
                close = close.squeeze()
            if close.isna().all():
                logger.warning("All NaN for %s — skipping", ticker)
                continue
            frames.append(close.rename(ticker))
        except Exception as exc:
            logger.warning("Failed to fetch %s: %s", ticker, exc)

    if not frames:
        raise RuntimeError("No price data could be fetched for any ticker.")

    prices = pd.concat(frames, axis=1)
    prices = prices.ffill().dropna(how="all")
    if tail:
        prices = prices.tail(tail)
    return prices


def get_returns(prices: pd.DataFrame) -> pd.DataFrame:
    """Simple daily percentage returns, NaN rows dropped."""
    return prices.pct_change().dropna()
