"""Works out what kind of market we're in: RISK_ON (calm, trending up), CHOPPY (no clear
direction) or RISK_OFF (scared, heading down). Three signals vote (volatility, trend, and
whether money is running to safety) and two out of three wins.
"""

import csv
import logging
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from config import REGIME_LOG

logger = logging.getLogger(__name__)

RISK_ON = "RISK_ON"
CHOPPY = "CHOPPY"
RISK_OFF = "RISK_OFF"

# A 1-1-1 split is the only possible tie, and this order resolves it to CHOPPY.
_PRIORITY = [CHOPPY, RISK_ON, RISK_OFF]


# The three signals, one vote each

def _vol_signal(spy_returns: pd.Series) -> str:
    ann_vol = spy_returns.tail(20).std() * np.sqrt(252)
    if ann_vol < 0.15:
        return RISK_ON
    if ann_vol > 0.25:
        return RISK_OFF
    return CHOPPY


def _trend_signal(spy_prices: pd.Series) -> str:
    # Moving-average read: above both averages is an uptrend, below the long one is a downtrend.
    if len(spy_prices) < 200:
        return CHOPPY
    spy = spy_prices.iloc[-1]
    ma50 = spy_prices.tail(50).mean()
    ma200 = spy_prices.tail(200).mean()
    if ma50 > ma200 and spy > ma50:
        return RISK_ON
    if spy < ma200:
        return RISK_OFF
    return CHOPPY


def _flight_signal(spy_prices: pd.Series, tlt_prices: pd.Series) -> str:
    # Flight to safety: when people get nervous they sell stocks (SPY) and buy bonds (TLT).
    # Bonds clearly beating stocks is a worry.
    n = min(11, len(spy_prices), len(tlt_prices))
    if n < 2:
        return CHOPPY
    spy_ret = spy_prices.iloc[-1] / spy_prices.iloc[-n] - 1
    tlt_ret = tlt_prices.iloc[-1] / tlt_prices.iloc[-n] - 1
    if spy_ret > tlt_ret:
        return RISK_ON
    if tlt_ret - spy_ret > 0.03:
        return RISK_OFF
    return CHOPPY


def _majority_vote(signals: list[str]) -> str:
    counts = {RISK_ON: 0, CHOPPY: 0, RISK_OFF: 0}
    for s in signals:
        counts[s] += 1
    max_count = max(counts.values())
    winners = [k for k, v in counts.items() if v == max_count]
    # A tie can only be a 1-1-1 split, and _PRIORITY turns that into CHOPPY.
    return min(winners, key=lambda x: _PRIORITY.index(x))


def detect_regime(
    spy_prices: pd.Series | None = None,
    tlt_prices: pd.Series | None = None,
) -> str:
    """Work out the current regime, fetching SPY and TLT prices if they aren't passed in."""
    if spy_prices is None or tlt_prices is None:
        from data import fetch_prices_range
        end = datetime.today()
        start = end - timedelta(days=252 + 60)
        prices = fetch_prices_range(["SPY", "TLT"], start, end)
        spy_prices = prices.get("SPY", pd.Series(dtype=float))
        tlt_prices = prices.get("TLT", pd.Series(dtype=float))

    spy_returns = spy_prices.pct_change().dropna()
    vol_sig = _vol_signal(spy_returns)
    trend_sig = _trend_signal(spy_prices)
    flight_sig = _flight_signal(spy_prices, tlt_prices)

    regime = _majority_vote([vol_sig, trend_sig, flight_sig])
    _log_regime(regime, vol_sig, trend_sig, flight_sig)
    logger.info("Regime: %s  (vol=%s, trend=%s, flight=%s)", regime, vol_sig, trend_sig, flight_sig)
    return regime


def _log_regime(regime: str, vol_sig: str, trend_sig: str, flight_sig: str) -> None:
    row = {
        "timestamp": datetime.now().isoformat(),
        "regime": regime,
        "vol_signal": vol_sig,
        "trend_signal": trend_sig,
        "flight_signal": flight_sig,
    }
    path = Path(REGIME_LOG)
    write_header = not path.exists()
    with open(path, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(row.keys()))
        if write_header:
            w.writeheader()
        w.writerow(row)
