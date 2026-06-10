"""Challenger bot: daily pipeline for the SECOND Alpaca paper account.

A diversified 3-sleeve book (ramped leveraged core / low-vol equity / ballast)
under a 16% vol target. Validated in challenger/backtest.py before it was
allowed to trade (full-cycle Sharpe ~0.65 vs SPY 0.39, max DD -24% vs -55%,
DSR ~100% across K=4 configs).

SAFETY: this process swaps the Alpaca env vars to the CHALLENGER keys before
broker.py is ever imported, and aborts hard if those keys are missing. It
cannot fall back to the champion's account. It shares code with the live bot
(broker, risk_overlay) but no state: its own logs, its own price cache.

Run:        python3 challenger/main.py
Dry run:    python3 challenger/main.py --dry-run     (no orders, prints targets)
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

# ── Point this process at the CHALLENGER account, hard-fail if keys missing ──
# os.environ[...] raises KeyError if the challenger keys aren't set, so this
# can never silently run against the champion's account.
os.environ["ALPACA_API_KEY"] = os.environ["CHALLENGER_ALPACA_API_KEY"]
os.environ["ALPACA_SECRET_KEY"] = os.environ["CHALLENGER_ALPACA_SECRET_KEY"]

import numpy as np
import pandas as pd

import broker                                   # imported AFTER the key swap
from risk_overlay import vol_target_scaler, portfolio_vol
from sleeves import combined_weights, ALL_TICKERS, TARGET_VOL, CASH

DAILY_LOG = HERE / "daily_log.csv"
PRICE_CACHE = HERE / "live_prices.parquet"
MIN_WEIGHT = 0.005       # drop dust positions below 0.5%
DRIFT = 0.02             # skip trading if nothing drifted more than 2%


def fetch_prices() -> pd.DataFrame:
    """~2 years of daily closes from Tiingo (own cache, never the champion's)."""
    if PRICE_CACHE.exists():
        px = pd.read_parquet(PRICE_CACHE)
        age_days = (pd.Timestamp.now() - px.index[-1]).days
        if all(t in px.columns for t in ALL_TICKERS) and age_days < 1:
            return px
    import requests
    tok = os.getenv("TIINGO_API_KEY")
    start = (datetime.now() - timedelta(days=730)).strftime("%Y-%m-%d")
    frames = []
    for t in ALL_TICKERS:
        r = requests.get(f"https://api.tiingo.com/tiingo/daily/{t}/prices",
                         params={"startDate": start, "token": tok,
                                 "format": "json", "resampleFreq": "daily"}, timeout=30)
        j = r.json()
        if isinstance(j, list) and j:
            df = pd.DataFrame(j)
            df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None)
            frames.append(df.set_index("date")["adjClose"].rename(t))
    if not frames:
        if PRICE_CACHE.exists():
            px = pd.read_parquet(PRICE_CACHE)
            if (pd.Timestamp.now() - px.index[-1]).days <= 4:
                print("Tiingo failed; using cached prices (<4 days old)")
                return px
        raise RuntimeError("No price data and no usable cache; not trading today.")
    px = pd.concat(frames, axis=1).sort_index().ffill()
    px.to_parquet(PRICE_CACHE)
    return px


def already_ran_today() -> bool:
    if not DAILY_LOG.exists():
        return False
    try:
        df = pd.read_csv(DAILY_LOG)
        return str(datetime.now().date()) in set(df["date"].astype(str))
    except Exception:
        return False


def log_row(row: dict):
    df = pd.DataFrame([row])
    df.to_csv(DAILY_LOG, mode="a", header=not DAILY_LOG.exists(), index=False)


def main():
    dry = "--dry-run" in sys.argv
    today = str(datetime.now().date())
    print(f"\nChallenger bot - {today}{' (DRY RUN)' if dry else ''}")

    acct = broker._trading_client().get_account()
    print(f"Account ...{str(acct.account_number)[-4:]}  equity ${float(acct.equity):,.2f}")

    if not dry:
        if already_ran_today():
            print("Already ran today; exiting (duplicate-run guard).")
            return
        if not broker.is_market_open():
            print("Market is closed; exiting cleanly. Nothing traded.")
            return

    # ── Signals -> sleeve weights -> vol-target scaling (same code as backtest) ──
    px = fetch_prices()
    print(f"Prices: {len(px)} days, through {px.index[-1].date()}")
    base = combined_weights(px)
    dr = px.pct_change(fill_method=None)

    risky = {t: v for t, v in base.items() if t != CASH}
    s = vol_target_scaler(dr.tail(80), risky, TARGET_VOL)
    weights = {t: v * s for t, v in risky.items()}
    weights[CASH] = base.get(CASH, 0.0) + (1.0 - s) * sum(risky.values())
    weights = {t: round(v, 4) for t, v in weights.items() if v >= MIN_WEIGHT}

    est_vol = portfolio_vol(dr.tail(80), risky)
    print(f"Vol scaler {s:.2f} (book est. {est_vol:.0%} -> target {TARGET_VOL:.0%})")
    print("Target weights:")
    for t, v in sorted(weights.items(), key=lambda x: -x[1]):
        print(f"  {t:<5} {v:>6.1%}")

    if dry:
        print("\nDry run complete - no orders placed.")
        return

    # ── Skip-trade check: only rebalance if something actually drifted ──────────
    current = broker.get_current_positions()
    drift = max((abs(weights.get(t, 0) - current.get(t, 0))
                 for t in set(weights) | set(current)), default=1.0)
    if current and drift <= DRIFT:
        print(f"Max drift {drift:.1%} <= {DRIFT:.0%}; no rebalance needed.")
        log_row({"date": today, "equity": float(acct.equity), "vol_scaler": round(s, 3),
                 "est_vol": round(est_vol, 3), "orders": 0,
                 "weights": json.dumps(weights), "notes": "no_rebalance"})
        return

    orders = broker.rebalance(weights)
    print(f"\nPlaced {len(orders)} orders.")
    equity_after = broker.get_portfolio_value()
    log_row({"date": today, "equity": equity_after or float(acct.equity),
             "vol_scaler": round(s, 3), "est_vol": round(est_vol, 3),
             "orders": len(orders), "weights": json.dumps(weights), "notes": ""})
    print("Logged. Done.")


if __name__ == "__main__":
    main()
