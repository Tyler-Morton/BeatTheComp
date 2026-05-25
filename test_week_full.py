"""Full week backtest May 18-22, 2026 — with simulated alpha sleeve.

Since we don't have historical Claude sentiment, the alpha sleeve here uses
only price/momentum/quality filters (no sentiment requirement). This is
an approximation but shows what the bot would have grabbed from watchlist.
"""

import warnings; warnings.filterwarnings("ignore")
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import yfinance as yf

from config import (ASSETS, WATCHLIST, ALPHA_SLEEVE_PCT, ALPHA_SLEEVE_PICKS,
                    ALPHA_MIN_5D_MOMENTUM, ALPHA_MIN_PRICE,
                    ALPHA_MAX_TODAY_PCT, ALPHA_REQUIRE_POSITIVE_20D)
from optimizer import optimize, select_strategy, _LEVERAGED_ETFS
from regime import _vol_signal, _trend_signal, _flight_signal, _majority_vote


WEEK_START = datetime(2026, 5, 18)
WEEK_END = datetime(2026, 5, 22)
HIST_START = datetime(2025, 1, 1)


def _detect_regime(prices_slice):
    spy = prices_slice.get("SPY", pd.Series())
    tlt = prices_slice.get("TLT", pd.Series())
    if spy.empty or len(spy) < 20: return "CHOPPY"
    return _majority_vote([
        _vol_signal(spy.pct_change().dropna()),
        _trend_signal(spy),
        _flight_signal(spy, tlt if not tlt.empty else spy),
    ])


def _select_alpha_momentum_only(stocks_data):
    """Alpha sleeve picks using ONLY momentum/price filters (no sentiment)."""
    qualified = []
    for row in stocks_data:
        mom_5d = row['mom_5d']
        mom_20d = row['mom_20d']
        price = row['price']
        today_pct = row['today_pct']
        if mom_5d < ALPHA_MIN_5D_MOMENTUM: continue
        if price < ALPHA_MIN_PRICE: continue
        if today_pct > ALPHA_MAX_TODAY_PCT: continue
        if ALPHA_REQUIRE_POSITIVE_20D and mom_20d <= 0: continue
        score = 1.5 * mom_5d + 0.5 * mom_20d - 0.5 * max(today_pct - 0.10, 0)
        qualified.append({**row, 'score': score})
    qualified.sort(key=lambda r: -r['score'])
    picks = qualified[:ALPHA_SLEEVE_PICKS]
    if not picks: return {}
    total_score = sum(p['score'] for p in picks)
    return {p['ticker']: p['score'] / total_score for p in picks}


def _get_stock_features(stock_prices, trading_day):
    """Build the row dict for one watchlist stock on a given day."""
    prior = stock_prices.loc[:trading_day - pd.Timedelta(days=1)]
    if len(prior) < 21: return None
    price = float(prior.iloc[-1])
    yesterday_price = float(prior.iloc[-2])
    today_pct = price / yesterday_price - 1
    mom_5d = price / float(prior.iloc[-6]) - 1
    mom_20d = price / float(prior.iloc[-21]) - 1
    return {
        "price": price, "today_pct": today_pct,
        "mom_5d": mom_5d, "mom_20d": mom_20d,
    }


def main():
    all_tickers = list(set(ASSETS + WATCHLIST + ["SPY", "TLT"]))
    print(f"Downloading {len(all_tickers)} tickers…")
    raw = yf.download(
        all_tickers,
        start=HIST_START.strftime("%Y-%m-%d"),
        end=(WEEK_END + timedelta(days=2)).strftime("%Y-%m-%d"),
        auto_adjust=True, progress=False, multi_level_index=True,
    )
    prices = raw["Close"] if isinstance(raw.columns, pd.MultiIndex) else raw[["Close"]]
    prices = prices.ffill().dropna(how="all")

    week_days = prices.loc[WEEK_START:WEEK_END].index.tolist()

    print(f"\n{'='*78}")
    print(f"  FULL WEEK BACKTEST WITH ALPHA SLEEVE")
    print(f"  May 18-22 2026 · ETFs 60% + Stocks 40% · momentum-only sleeve")
    print(f"{'='*78}")

    portfolio_value = 1000.0
    spy_value = 1000.0
    daily_records = []

    for trading_day in week_days:
        prior_data = prices.loc[:trading_day - pd.Timedelta(days=1)]
        prev_day = prior_data.index[-1]
        if len(prior_data) < 60: continue

        # ETF allocation
        asset_cols = [a for a in ASSETS if a in prior_data.columns]
        returns = prior_data[asset_cols].pct_change().dropna().tail(252)
        regime_slice = prior_data[[c for c in ["SPY", "TLT"] if c in prior_data.columns]].tail(252)
        regime = _detect_regime(regime_slice)
        strategy = select_strategy(regime, returns=returns)
        try:
            etf_weights = optimize(strategy=strategy, returns=returns, regime=regime)["weights"]
        except Exception:
            etf_weights = {t: 1.0/len(asset_cols) for t in asset_cols}

        # Alpha sleeve picks (momentum only)
        wl_data = []
        for stock in WATCHLIST:
            if stock not in prices.columns: continue
            feats = _get_stock_features(prices[stock], trading_day)
            if feats is None: continue
            wl_data.append({"ticker": stock, **feats})
        sleeve_picks = _select_alpha_momentum_only(wl_data)

        # Merge ETFs (scaled to 60%) + sleeve (40%)
        combined = {t: w * (1 - ALPHA_SLEEVE_PCT) for t, w in etf_weights.items()}
        for stock, sleeve_w in sleeve_picks.items():
            combined[stock] = combined.get(stock, 0) + sleeve_w * ALPHA_SLEEVE_PCT

        # Calculate today's actual return
        port_ret = 0.0
        for t, w in combined.items():
            if t in prices.columns and trading_day in prices.index:
                tprev = prices.loc[prev_day, t]
                tnow = prices.loc[trading_day, t]
                if pd.notna(tprev) and pd.notna(tnow) and tprev > 0:
                    port_ret += w * (tnow / tprev - 1)

        portfolio_value *= (1 + port_ret)
        spy_ret = prices.loc[trading_day, "SPY"] / prices.loc[prev_day, "SPY"] - 1
        spy_value *= (1 + spy_ret)

        daily_records.append({
            "date": trading_day.date(), "regime": regime, "strategy": strategy,
            "etf_weights": etf_weights, "sleeve_picks": sleeve_picks,
            "combined": combined, "port_ret": port_ret, "spy_ret": spy_ret,
            "port_val": portfolio_value, "spy_val": spy_value,
        })

        # Print day
        print(f"\n──── {trading_day.strftime('%A, %b %d')} ────")
        print(f"  Regime: {regime}  Strategy: {strategy}")

        etf_share = sum(combined.get(t, 0) for t in ASSETS if t in combined)
        stock_share = sum(combined.get(t, 0) for t in WATCHLIST if t in combined)
        print(f"  Split: ETFs {etf_share*100:.0f}%  +  Stocks {stock_share*100:.0f}%")

        print(f"  ETF top 4:")
        for t, w in sorted(etf_weights.items(), key=lambda x: -x[1])[:4]:
            if w > 0.01:
                marker = " ⚡" if t in _LEVERAGED_ETFS else ""
                print(f"    {t:6} {w*100*0.6:5.1f}% of portfolio (= {w*100:.0f}% of ETF allotment){marker}")

        print(f"  Alpha sleeve picks:")
        if sleeve_picks:
            for t, w in sorted(sleeve_picks.items(), key=lambda x: -x[1]):
                print(f"    {t:6} {w*100*0.4:5.1f}% of portfolio")
        else:
            print(f"    (no stocks qualified)")

        print(f"  Day: portfolio {port_ret*100:+.2f}%  vs SPY {spy_ret*100:+.2f}%  →  {(port_ret-spy_ret)*100:+.2f} pp")

    # Summary
    print(f"\n{'='*78}")
    print(f"  WEEK TOTALS")
    print(f"{'='*78}\n")
    print(f"  {'Day':<22} {'Bot':>10} {'SPY':>10} {'Diff':>10}")
    print(f"  {'-'*52}")
    for r in daily_records:
        diff = (r['port_ret'] - r['spy_ret']) * 100
        mark = "✓" if diff > 0 else "✗"
        print(f"  {str(r['date']):<22} {r['port_ret']*100:>+9.2f}% {r['spy_ret']*100:>+9.2f}% {diff:>+9.2f}% {mark}")
    print(f"  {'-'*52}")
    pt = portfolio_value / 1000.0 - 1
    st = spy_value / 1000.0 - 1
    print(f"  {'WEEK TOTAL':<22} {pt*100:>+9.2f}% {st*100:>+9.2f}% {(pt-st)*100:>+9.2f}%")
    print()
    print(f"  Starting capital: $1,000")
    print(f"  Bot end:          ${portfolio_value:,.2f}  ({pt*100:+.2f}%)")
    print(f"  SPY end:          ${spy_value:,.2f}  ({st*100:+.2f}%)")
    print(f"  Outperformance:   ${portfolio_value - spy_value:+,.2f}  ({(pt-st)*100:+.2f} pp)")


if __name__ == "__main__":
    main()
