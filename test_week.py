"""Simulate the new aggressive paper trading bot Mon-Fri May 18-22, 2026.

For each trading day:
  1. Use data up to (but not including) that morning — no look-ahead bias
  2. Run the full pipeline (regime → strategy → optimizer)
  3. Show the chosen allocation
  4. Calculate that day's actual return using REAL market data
  5. Compare cumulative performance to SPY

Skips the alpha sleeve (no historical Claude sentiment data available).
The ETF-only allocation gives a clean read of the strategy's mechanics.
"""

import warnings; warnings.filterwarnings("ignore")
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import yfinance as yf

from config import ASSETS
from optimizer import optimize, select_strategy, _LEVERAGED_ETFS
from regime import _vol_signal, _trend_signal, _flight_signal, _majority_vote


# ── Date setup ─────────────────────────────────────────────────────────────────
WEEK_START = datetime(2026, 5, 18)   # Monday
WEEK_END = datetime(2026, 5, 22)     # Friday
HIST_START = datetime(2025, 1, 1)    # need ~16 months of history for 252-day lookback


def _detect_regime(prices_slice: pd.DataFrame) -> str:
    spy = prices_slice.get("SPY", pd.Series())
    tlt = prices_slice.get("TLT", pd.Series())
    if spy.empty or len(spy) < 20:
        return "CHOPPY"
    spy_returns = spy.pct_change().dropna()
    return _majority_vote([
        _vol_signal(spy_returns),
        _trend_signal(spy),
        _flight_signal(spy, tlt if not tlt.empty else spy),
    ])


def _download_history(tickers: list[str]) -> pd.DataFrame:
    print("Downloading price history (this may take 30s)…")
    raw = yf.download(
        tickers,
        start=HIST_START.strftime("%Y-%m-%d"),
        end=(WEEK_END + timedelta(days=2)).strftime("%Y-%m-%d"),
        auto_adjust=True,
        progress=False,
        multi_level_index=True,
    )
    if isinstance(raw.columns, pd.MultiIndex):
        prices = raw["Close"]
    else:
        prices = raw[["Close"]].rename(columns={"Close": tickers[0]})
    return prices.ffill().dropna(how="all")


def main():
    all_tickers = list(set(ASSETS + ["SPY", "TLT"]))
    prices = _download_history(all_tickers)

    # Filter to trading days within the test week
    week_days = prices.loc[WEEK_START:WEEK_END].index.tolist()
    if not week_days:
        print("No trading days found in that range!")
        return

    print(f"\n{'='*78}")
    print(f"  WEEK BACKTEST: {WEEK_START.date()} → {WEEK_END.date()}  ({len(week_days)} trading days)")
    print(f"{'='*78}")

    portfolio_value = 1000.0
    spy_value = 1000.0
    initial_spy_price = None
    daily_records = []

    prev_weights = {t: 1.0 / len(ASSETS) for t in ASSETS if t in prices.columns}

    for trading_day in week_days:
        # Use ALL data up to (but NOT including) trading_day for decisions
        prior_data = prices.loc[:trading_day - pd.Timedelta(days=1)]
        if len(prior_data) < 60:
            continue

        # Calculate returns for asset universe (excluding SPY/TLT auxiliary)
        asset_cols = [a for a in ASSETS if a in prior_data.columns]
        returns = prior_data[asset_cols].pct_change().dropna().tail(252)

        # Regime
        regime_slice = prior_data[[c for c in ["SPY", "TLT"] if c in prior_data.columns]].tail(252)
        regime = _detect_regime(regime_slice)

        # Strategy + optimize
        strategy = select_strategy(regime, returns=returns)
        try:
            result = optimize(strategy=strategy, returns=returns, regime=regime)
            weights = result["weights"]
        except Exception as exc:
            print(f"  {trading_day.date()}: optimize failed ({exc}), keeping previous weights")
            weights = prev_weights

        # ── Compute the day's actual return using these weights ──
        if trading_day in prices.index:
            todays_returns = prices.loc[trading_day] / prices.loc[prior_data.index[-1]] - 1
            port_ret = sum(weights.get(t, 0) * todays_returns.get(t, 0) for t in weights if pd.notna(todays_returns.get(t)))
        else:
            port_ret = 0.0

        portfolio_value *= (1 + port_ret)

        # SPY benchmark
        if "SPY" in prices.columns:
            spy_close = prices.loc[trading_day, "SPY"]
            if initial_spy_price is None:
                initial_spy_price = prices.loc[prior_data.index[-1], "SPY"]
                spy_prev = initial_spy_price
            else:
                spy_prev = prices.loc[prior_data.index[-1], "SPY"]
            spy_ret = spy_close / spy_prev - 1
            spy_value *= (1 + spy_ret)
        else:
            spy_ret = 0.0

        prev_weights = weights
        daily_records.append({
            "date": trading_day.date(),
            "regime": regime,
            "strategy": strategy,
            "port_ret": port_ret,
            "spy_ret": spy_ret,
            "port_val": portfolio_value,
            "spy_val": spy_value,
            "weights": weights,
        })

        # ── Print day summary ──
        print(f"\n──── {trading_day.strftime('%A, %b %d')} ────")
        print(f"  Regime: {regime}  |  Strategy: {strategy}")
        print(f"  Top 5 positions:")
        for t, w in sorted(weights.items(), key=lambda x: -x[1])[:5]:
            if w > 0.01:
                lev = " ⚡" if t in _LEVERAGED_ETFS else ""
                print(f"    {t:6} {w*100:5.1f}%{lev}")
        print(f"  Day return: portfolio {port_ret*100:+.2f}%  |  SPY {spy_ret*100:+.2f}%  |  diff {(port_ret-spy_ret)*100:+.2f}%")

    # ── Summary ─────────────────────────────────────────────────────────────
    print(f"\n{'='*78}")
    print(f"  WEEK SUMMARY")
    print(f"{'='*78}")
    port_total = portfolio_value / 1000.0 - 1
    spy_total = spy_value / 1000.0 - 1
    print(f"\n  {'Day':<22} {'Bot':>10} {'SPY':>10} {'Diff':>10}")
    print(f"  {'-'*52}")
    for r in daily_records:
        diff = (r['port_ret'] - r['spy_ret']) * 100
        mark = "✓" if diff > 0 else "✗"
        print(f"  {str(r['date']):<22} {r['port_ret']*100:>+9.2f}% {r['spy_ret']*100:>+9.2f}% {diff:>+9.2f}% {mark}")
    print(f"  {'-'*52}")
    print(f"  {'WEEK TOTAL':<22} {port_total*100:>+9.2f}% {spy_total*100:>+9.2f}% {(port_total-spy_total)*100:>+9.2f}%")
    print()
    print(f"  Starting capital: $1,000")
    print(f"  Bot final value:  ${portfolio_value:,.2f}  ({port_total*100:+.2f}%)")
    print(f"  SPY final value:  ${spy_value:,.2f}  ({spy_total*100:+.2f}%)")
    print(f"  Outperformance:   ${portfolio_value - spy_value:+,.2f}  ({(port_total - spy_total)*100:+.2f} pp)")

    winner = "BOT 🎉" if port_total > spy_total else "SPY"
    print(f"\n  Winner: {winner}")
    print(f"{'='*78}\n")


if __name__ == "__main__":
    main()
