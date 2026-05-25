"""Full 2026 YTD backtest with the aggressive paper trading config.

Includes alpha sleeve with synthetic sentiment proxy:
  - Big positive 1-day moves (+5%+) → simulated bullish news catalyst
  - Sustained 20d momentum → trend confirmation
  - Combined into a "sentiment-like" score

This is an APPROXIMATION of what the bot would have done if it had been
running with the current config since Jan 2, 2026.
"""

import warnings; warnings.filterwarnings("ignore")
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import yfinance as yf

from config import (ASSETS, WATCHLIST, ALPHA_SLEEVE_PCT, ALPHA_SLEEVE_PICKS,
                    ALPHA_MIN_5D_MOMENTUM, ALPHA_MIN_PRICE,
                    ALPHA_MAX_TODAY_PCT, ALPHA_REQUIRE_POSITIVE_20D,
                    DRAWDOWN_CIRCUIT_BREAKER)
from optimizer import optimize, select_strategy, _LEVERAGED_ETFS
from regime import _vol_signal, _trend_signal, _flight_signal, _majority_vote


YTD_START = datetime(2026, 1, 1)
YTD_END = datetime(2026, 5, 22)
HIST_START = datetime(2024, 1, 1)


def _detect_regime(prices_slice):
    spy = prices_slice.get("SPY", pd.Series())
    tlt = prices_slice.get("TLT", pd.Series())
    if spy.empty or len(spy) < 20: return "CHOPPY"
    return _majority_vote([
        _vol_signal(spy.pct_change().dropna()),
        _trend_signal(spy),
        _flight_signal(spy, tlt if not tlt.empty else spy),
    ])


def _synthetic_sentiment(mom_5d, mom_20d, today_pct):
    """Approximate sentiment score from price action alone.
    Big single-day moves act like news catalysts. Sustained momentum confirms.
    """
    catalyst_score = min(max(today_pct * 3, -1), 1)        # big moves dominate
    trend_score = min(max(mom_20d * 2, -1), 1)             # 20d trend
    momentum_score = min(max(mom_5d * 1.5, -1), 1)         # 5d strength
    return float(0.4 * catalyst_score + 0.3 * trend_score + 0.3 * momentum_score)


def _select_alpha_with_sentiment(stocks_data):
    """Full alpha sleeve picker WITH synthetic sentiment."""
    qualified = []
    for row in stocks_data:
        sent = row["synth_sentiment"]
        mom_5d = row['mom_5d']; mom_20d = row['mom_20d']
        price = row['price']; today_pct = row['today_pct']

        if sent < 0.5: continue                        # sentiment gate
        if mom_5d < ALPHA_MIN_5D_MOMENTUM: continue
        if price < ALPHA_MIN_PRICE: continue
        if today_pct > ALPHA_MAX_TODAY_PCT: continue
        if ALPHA_REQUIRE_POSITIVE_20D and mom_20d <= 0: continue

        # Composite score (same formula as production alpha_sleeve.py)
        score = sent + 1.5 * mom_5d + 0.5 * mom_20d - 0.5 * max(today_pct - 0.10, 0)
        qualified.append({**row, 'score': score})

    qualified.sort(key=lambda r: -r['score'])
    picks = qualified[:ALPHA_SLEEVE_PICKS]
    if not picks: return {}
    total = sum(p['score'] for p in picks)
    return {p['ticker']: p['score'] / total for p in picks}


def _get_stock_features(stock_prices, trading_day):
    prior = stock_prices.loc[:trading_day - pd.Timedelta(days=1)]
    if len(prior) < 21: return None
    price = float(prior.iloc[-1])
    prev_price = float(prior.iloc[-2])
    today_pct = price / prev_price - 1
    mom_5d = price / float(prior.iloc[-6]) - 1
    mom_20d = price / float(prior.iloc[-21]) - 1
    return {
        "price": price, "today_pct": today_pct,
        "mom_5d": mom_5d, "mom_20d": mom_20d,
        "synth_sentiment": _synthetic_sentiment(mom_5d, mom_20d, today_pct),
    }


def _chunked_download(tickers, start, end, chunk_size=10, delay=3):
    """Download in chunks to avoid yfinance rate limits."""
    import time as _time
    all_frames = []
    for i in range(0, len(tickers), chunk_size):
        chunk = tickers[i:i+chunk_size]
        for attempt in range(3):
            try:
                raw = yf.download(chunk, start=start, end=end, auto_adjust=True,
                                  progress=False, multi_level_index=True)
                if isinstance(raw.columns, pd.MultiIndex):
                    closes = raw["Close"]
                else:
                    closes = raw[["Close"]].rename(columns={"Close": chunk[0]})
                if not closes.empty:
                    all_frames.append(closes)
                    break
            except Exception:
                pass
            _time.sleep(delay * (attempt + 1))
        _time.sleep(delay)
    return pd.concat(all_frames, axis=1) if all_frames else pd.DataFrame()


def main():
    all_tickers = list(set(ASSETS + WATCHLIST + ["SPY", "TLT"]))
    print(f"Downloading {len(all_tickers)} tickers from {HIST_START.date()} to {YTD_END.date()}…")
    prices = _chunked_download(
        all_tickers,
        start=HIST_START.strftime("%Y-%m-%d"),
        end=(YTD_END + timedelta(days=2)).strftime("%Y-%m-%d"),
    )
    if prices.empty:
        print("All downloads failed. Try again in a few minutes.")
        return
    prices = prices.ffill().dropna(how="all")
    print(f"  Got {len(prices)} trading days for {len(prices.columns)} tickers")

    ytd_days = prices.loc[YTD_START:YTD_END].index.tolist()
    print(f"\n{'='*78}")
    print(f"  YTD 2026 BACKTEST · {YTD_START.date()} → {YTD_END.date()}")
    print(f"  {len(ytd_days)} trading days · aggressive paper config · synthetic sentiment")
    print(f"{'='*78}")

    portfolio_value = 1000.0
    spy_value = 1000.0
    portfolio_high = 1000.0
    daily_records = []
    pick_history = {}   # ticker → days held

    for trading_day in ytd_days:
        prior_data = prices.loc[:trading_day - pd.Timedelta(days=1)]
        if len(prior_data) < 60: continue
        prev_day = prior_data.index[-1]

        # ETF allocation
        asset_cols = [a for a in ASSETS if a in prior_data.columns]
        returns = prior_data[asset_cols].pct_change().dropna().tail(252)
        regime_slice = prior_data[[c for c in ["SPY","TLT"] if c in prior_data.columns]].tail(252)
        regime = _detect_regime(regime_slice)
        strategy = select_strategy(regime, returns=returns)
        try:
            etf_weights = optimize(strategy=strategy, returns=returns, regime=regime)["weights"]
        except Exception:
            etf_weights = {t: 1.0/len(asset_cols) for t in asset_cols}

        # Alpha sleeve with synthetic sentiment
        wl_data = []
        for stock in WATCHLIST:
            if stock not in prices.columns: continue
            feats = _get_stock_features(prices[stock], trading_day)
            if feats is None: continue
            wl_data.append({"ticker": stock, **feats})
        sleeve_picks = _select_alpha_with_sentiment(wl_data)
        for t in sleeve_picks:
            pick_history[t] = pick_history.get(t, 0) + 1

        # Merge weights
        combined = {t: w * (1 - ALPHA_SLEEVE_PCT) for t, w in etf_weights.items()}
        for stock, sleeve_w in sleeve_picks.items():
            combined[stock] = combined.get(stock, 0) + sleeve_w * ALPHA_SLEEVE_PCT

        # Drawdown breaker check
        current_dd = (portfolio_value / portfolio_high - 1)
        if current_dd < -DRAWDOWN_CIRCUIT_BREAKER:
            # Pause trading: keep portfolio in cash equivalent return ~= 0
            port_ret = 0.0
            breaker_active = True
        else:
            port_ret = 0.0
            for t, w in combined.items():
                if t in prices.columns and trading_day in prices.index:
                    tprev = prices.loc[prev_day, t]; tnow = prices.loc[trading_day, t]
                    if pd.notna(tprev) and pd.notna(tnow) and tprev > 0:
                        port_ret += w * (tnow / tprev - 1)
            breaker_active = False

        portfolio_value *= (1 + port_ret)
        portfolio_high = max(portfolio_high, portfolio_value)

        spy_ret = prices.loc[trading_day, "SPY"] / prices.loc[prev_day, "SPY"] - 1
        spy_value *= (1 + spy_ret)

        daily_records.append({
            "date": trading_day.date(), "regime": regime, "strategy": strategy,
            "port_ret": port_ret, "spy_ret": spy_ret,
            "port_val": portfolio_value, "spy_val": spy_value,
            "picks": list(sleeve_picks.keys()), "breaker": breaker_active,
            "leveraged_pct": sum(etf_weights.get(t,0) for t in _LEVERAGED_ETFS) * (1 - ALPHA_SLEEVE_PCT),
        })

    # ── SUMMARY ──
    df = pd.DataFrame(daily_records)
    df["date"] = pd.to_datetime(df["date"])

    print(f"\n  Day-by-day too long to show — showing monthly summary…\n")

    df["month"] = df["date"].dt.to_period("M")
    monthly = df.groupby("month").agg(
        port_start=("port_val", "first"),
        port_end=("port_val", "last"),
        spy_start=("spy_val", "first"),
        spy_end=("spy_val", "last"),
        days=("date", "count"),
    )
    monthly["bot_ret"] = monthly["port_end"] / monthly["port_start"] - 1
    monthly["spy_ret"] = monthly["spy_end"] / monthly["spy_start"] - 1
    monthly["diff"] = monthly["bot_ret"] - monthly["spy_ret"]

    print(f"  {'Month':<10} {'Days':>5} {'Bot':>10} {'SPY':>10} {'Diff':>10}")
    print(f"  {'-'*48}")
    for m, row in monthly.iterrows():
        mark = "✓" if row["diff"] > 0 else "✗"
        print(f"  {str(m):<10} {int(row['days']):>5} {row['bot_ret']*100:>+9.2f}% {row['spy_ret']*100:>+9.2f}% {row['diff']*100:>+9.2f}% {mark}")
    print(f"  {'-'*48}")

    # Total
    pt = portfolio_value / 1000 - 1
    st = spy_value / 1000 - 1
    print(f"  {'YTD TOTAL':<10} {len(df):>5} {pt*100:>+9.2f}% {st*100:>+9.2f}% {(pt-st)*100:>+9.2f}%")

    # Stats
    daily_ret_bot = df["port_ret"]
    daily_ret_spy = df["spy_ret"]
    print(f"\n  {'─'*60}")
    print(f"  PERFORMANCE STATISTICS")
    print(f"  {'─'*60}")
    print(f"  Starting capital:    $1,000")
    print(f"  Bot final:           ${portfolio_value:,.2f}  ({pt*100:+.2f}%)")
    print(f"  SPY final:           ${spy_value:,.2f}  ({st*100:+.2f}%)")
    print(f"  Outperformance:      ${portfolio_value - spy_value:+,.2f}  ({(pt-st)*100:+.2f} pp)")
    print()
    bot_vol = daily_ret_bot.std() * np.sqrt(252)
    spy_vol = daily_ret_spy.std() * np.sqrt(252)
    bot_sharpe = (daily_ret_bot.mean() * 252) / (daily_ret_bot.std() * np.sqrt(252)) if daily_ret_bot.std() > 0 else 0
    spy_sharpe = (daily_ret_spy.mean() * 252) / (daily_ret_spy.std() * np.sqrt(252)) if daily_ret_spy.std() > 0 else 0
    print(f"  Annualized vol:      bot {bot_vol*100:.1f}%   SPY {spy_vol*100:.1f}%")
    print(f"  Sharpe (annualized): bot {bot_sharpe:.2f}     SPY {spy_sharpe:.2f}")
    print(f"  Best day:            bot {daily_ret_bot.max()*100:+.2f}%   SPY {daily_ret_spy.max()*100:+.2f}%")
    print(f"  Worst day:           bot {daily_ret_bot.min()*100:+.2f}%   SPY {daily_ret_spy.min()*100:+.2f}%")
    print(f"  Win days:            {(daily_ret_bot > daily_ret_spy).sum()}/{len(df)} ({(daily_ret_bot > daily_ret_spy).mean()*100:.0f}%)")

    # Drawdown
    cum = (1 + daily_ret_bot).cumprod()
    roll_max = cum.cummax()
    dd = (cum - roll_max) / roll_max
    spy_cum = (1 + daily_ret_spy).cumprod()
    spy_dd = (spy_cum - spy_cum.cummax()) / spy_cum.cummax()
    print(f"  Max drawdown:        bot {dd.min()*100:.1f}%  SPY {spy_dd.min()*100:.1f}%")

    # Top picks
    print(f"\n  Most-picked stocks by alpha sleeve:")
    sorted_picks = sorted(pick_history.items(), key=lambda x: -x[1])[:10]
    for t, days in sorted_picks:
        print(f"    {t:6} {days:3d} days ({days/len(df)*100:.0f}% of YTD)")


if __name__ == "__main__":
    main()
