"""5-year backtest Jan 2020 → Dec 2024 with synthetic sentiment alpha sleeve.

Includes:
- New aggressive config (leveraged ETFs, 40% alpha sleeve)
- Synthetic sentiment from price action (no historical Claude data)
- Drawdown circuit breaker
- All regime detection + strategy selection
- Real handling of missing data (BITO pre-Oct 2021, quantum stocks pre-2022)
"""

import warnings; warnings.filterwarnings("ignore")
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import yfinance as yf
import time

from config import (ASSETS, WATCHLIST, ALPHA_SLEEVE_PCT, ALPHA_SLEEVE_PICKS,
                    ALPHA_MIN_5D_MOMENTUM, ALPHA_MIN_PRICE,
                    ALPHA_MAX_TODAY_PCT, ALPHA_REQUIRE_POSITIVE_20D,
                    DRAWDOWN_CIRCUIT_BREAKER)
from optimizer import optimize, select_strategy, _LEVERAGED_ETFS
from regime import _vol_signal, _trend_signal, _flight_signal, _majority_vote


# Curated historical watchlist — names that were big during 2020-2024
HISTORICAL_WATCHLIST = [
    "NVDA", "AMD", "MU", "AVGO",       # AI chip leaders
    "AAPL", "MSFT", "GOOGL", "META",   # mega-cap tech
    "TSLA", "AMZN", "NFLX",            # high-beta tech
    "GME", "AMC",                       # 2021 meme stocks
    "PLTR", "COIN", "MSTR",            # SPACs / crypto
    "LLY", "MRNA",                      # biotech
    "ENPH", "FSLR",                     # clean energy (2020-21 hot)
    "F", "RIVN",                        # autos
]

START_DATE = datetime(2020, 1, 1)
END_DATE = datetime(2024, 12, 31)
HIST_START = datetime(2018, 1, 1)  # buffer for 252-day lookback


def _detect_regime(prices_slice):
    spy = prices_slice.get("SPY", pd.Series())
    tlt = prices_slice.get("TLT", pd.Series())
    if spy.empty or len(spy) < 20: return "CHOPPY"
    return _majority_vote([
        _vol_signal(spy.pct_change().dropna()),
        _trend_signal(spy),
        _flight_signal(spy, tlt if not tlt.empty else spy),
    ])


def _synth_sentiment(mom_5d, mom_20d, today_pct):
    catalyst = min(max(today_pct * 3, -1), 1)
    trend = min(max(mom_20d * 2, -1), 1)
    momentum = min(max(mom_5d * 1.5, -1), 1)
    return float(0.4 * catalyst + 0.3 * trend + 0.3 * momentum)


def _alpha_picks(stocks_data):
    qualified = []
    for row in stocks_data:
        sent = row["sentiment"]
        if sent < 0.5: continue
        if row["mom_5d"] < ALPHA_MIN_5D_MOMENTUM: continue
        if row["price"] < ALPHA_MIN_PRICE: continue
        if row["today_pct"] > ALPHA_MAX_TODAY_PCT: continue
        if ALPHA_REQUIRE_POSITIVE_20D and row["mom_20d"] <= 0: continue
        score = sent + 1.5 * row["mom_5d"] + 0.5 * row["mom_20d"] - 0.5 * max(row["today_pct"] - 0.10, 0)
        qualified.append({**row, "score": score})
    qualified.sort(key=lambda r: -r["score"])
    picks = qualified[:ALPHA_SLEEVE_PICKS]
    if not picks: return {}
    total = sum(p["score"] for p in picks)
    return {p["ticker"]: p["score"]/total for p in picks}


def _stock_features(stock_prices, day):
    prior = stock_prices.loc[:day - pd.Timedelta(days=1)]
    if len(prior) < 21: return None
    px = float(prior.iloc[-1])
    if pd.isna(px): return None
    prev = float(prior.iloc[-2])
    if prev <= 0: return None
    today_pct = px/prev - 1
    mom_5d = px/float(prior.iloc[-6]) - 1
    mom_20d = px/float(prior.iloc[-21]) - 1
    return {
        "price": px, "today_pct": today_pct,
        "mom_5d": mom_5d, "mom_20d": mom_20d,
        "sentiment": _synth_sentiment(mom_5d, mom_20d, today_pct),
    }


def _chunk_download(tickers, start, end, chunk=3, delay=30):
    """Resilient downloader: saves progress to disk after each ticker.
    Rate-limit-aware — uses browser session, long delays, single-ticker requests.
    """
    import requests
    from pathlib import Path

    cache = Path("/tmp/backtest_prices.parquet")
    if cache.exists():
        df = pd.read_parquet(cache)
        print(f"  Loaded {len(df)} rows × {len(df.columns)} tickers from disk cache")
        # Only download what's missing
        missing = [t for t in tickers if t not in df.columns]
        if not missing:
            print(f"  All {len(tickers)} tickers already cached, skipping download")
            return df
        print(f"  Need to download {len(missing)} missing tickers: {missing}")
        tickers = missing
    else:
        df = None

    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    })

    new_data = {}
    for i, t in enumerate(tickers):
        for attempt in range(5):
            try:
                tick = yf.Ticker(t, session=session)
                h = tick.history(start=start, end=end, auto_adjust=True)
                if not h.empty:
                    new_data[t] = h["Close"]
                    print(f"  [{i+1}/{len(tickers)}] ✓ {t} ({len(h)} days)")
                    # Save incrementally
                    combined = df.copy() if df is not None else pd.DataFrame()
                    for tt, ss in new_data.items():
                        combined[tt] = ss
                    combined.to_parquet(cache)
                    break
                else:
                    print(f"  [{i+1}/{len(tickers)}] ⚠ {t} empty")
                    break
            except Exception as e:
                wait = delay * (2 ** attempt)
                print(f"  [{i+1}/{len(tickers)}] {t} attempt {attempt+1}/5 failed, waiting {wait}s…")
                time.sleep(wait)
        time.sleep(delay)   # delay between tickers regardless

    # Final merge
    if df is None:
        return pd.DataFrame(new_data)
    for t, s in new_data.items():
        df[t] = s
    return df


def main():
    all_tickers = list(set(ASSETS + HISTORICAL_WATCHLIST + ["SPY", "TLT"]))
    print(f"Downloading {len(all_tickers)} tickers Jan 2018 → Dec 2024 (this takes a few min)…")
    prices = _chunk_download(
        all_tickers,
        start=HIST_START.strftime("%Y-%m-%d"),
        end=(END_DATE + timedelta(days=2)).strftime("%Y-%m-%d"),
    )
    if prices.empty:
        print("Download failed completely.")
        return
    prices = prices.ffill().dropna(how="all")
    # Strip timezone from index for clean date comparisons
    if prices.index.tz is not None:
        prices.index = prices.index.tz_localize(None)
    print(f"  Got {len(prices)} trading days for {len(prices.columns)} tickers\n")

    test_days = prices.loc[START_DATE:END_DATE].index.tolist()
    print(f"Running backtest over {len(test_days)} trading days…\n")

    pv = 1000.0
    spy_v = 1000.0
    ath = 1000.0
    prev_weights = {}   # last rebalance state — used if drawdown breaker triggers
    daily = []
    pick_hist = {}
    breaker_days = 0

    for i, day in enumerate(test_days):
        prior = prices.loc[:day - pd.Timedelta(days=1)]
        if len(prior) < 60: continue
        prev_d = prior.index[-1]

        # Strict filter: ticker must have valid data throughout the full 252-day lookback
        asset_cols = []
        for a in ASSETS:
            if a not in prior.columns: continue
            recent = prior[a].tail(252)
            valid = recent.dropna()
            if len(valid) >= 200 and (valid > 0).all():  # at least 200 valid days
                asset_cols.append(a)
        if len(asset_cols) < 4:   # need a minimum universe
            continue
        returns = prior[asset_cols].pct_change().dropna().tail(252)
        if len(returns) < 60: continue

        regime_slice = prior[[c for c in ["SPY", "TLT"] if c in prior.columns]].tail(252)
        regime = _detect_regime(regime_slice)
        strategy = select_strategy(regime, returns=returns)

        # Drawdown breaker check — pauses REBALANCING, doesn't freeze positions
        breaker_active = (pv / ath - 1) < -DRAWDOWN_CIRCUIT_BREAKER

        if breaker_active and prev_weights:
            # Keep existing positions, no new rebalance
            combined = prev_weights
            breaker_days += 1
        else:
            try:
                etf_w = optimize(strategy=strategy, returns=returns, regime=regime)["weights"]
            except Exception:
                etf_w = {t: 1.0/len(asset_cols) for t in asset_cols}

            # Alpha sleeve (synthetic sentiment)
            wl_data = []
            for stock in HISTORICAL_WATCHLIST:
                if stock not in prices.columns: continue
                feats = _stock_features(prices[stock], day)
                if feats is None: continue
                wl_data.append({"ticker": stock, **feats})
            sleeve = _alpha_picks(wl_data)
            for t in sleeve: pick_hist[t] = pick_hist.get(t, 0) + 1

            # Merge ETFs + sleeve
            combined = {t: w * (1 - ALPHA_SLEEVE_PCT) for t, w in etf_w.items()}
            for s, sw in sleeve.items():
                combined[s] = combined.get(s, 0) + sw * ALPHA_SLEEVE_PCT
            prev_weights = combined

        # Apply day's returns — positions still move regardless of breaker
        port_ret = 0.0
        for t, w in combined.items():
            if pd.isna(w) or w == 0: continue
            if t not in prices.columns or day not in prices.index: continue
            pp = prices.loc[prev_d, t]
            cp = prices.loc[day, t]
            if pd.notna(pp) and pd.notna(cp) and pp > 0 and cp > 0:
                day_ret = cp/pp - 1
                if pd.notna(day_ret) and abs(day_ret) < 0.5:   # sanity cap: no |50%+| moves
                    port_ret += w * day_ret

        # NaN guard
        if pd.isna(port_ret) or abs(port_ret) > 0.5:
            port_ret = 0.0

        pv *= (1 + port_ret)
        ath = max(ath, pv)

        spy_ret = prices.loc[day, "SPY"]/prices.loc[prev_d, "SPY"] - 1
        spy_v *= (1 + spy_ret)

        daily.append({
            "date": day, "regime": regime, "strategy": strategy,
            "port_ret": port_ret, "spy_ret": spy_ret,
            "port_val": pv, "spy_val": spy_v,
            "picks": list(combined.keys())[:5] if not breaker_active else ["FROZEN"],
        })

        if i % 250 == 0 and i > 0:
            print(f"  ~{day.date()}: portfolio=${pv:,.0f}  SPY=${spy_v:,.0f}  (breaker active {breaker_days} days)")

    # ── Annual summary ──
    df = pd.DataFrame(daily)
    df["date"] = pd.to_datetime(df["date"])
    df["year"] = df["date"].dt.year

    yearly = df.groupby("year").agg(
        port_start=("port_val", "first"),
        port_end=("port_val", "last"),
        spy_start=("spy_val", "first"),
        spy_end=("spy_val", "last"),
        days=("date", "count"),
    )
    yearly["bot"] = yearly["port_end"]/yearly["port_start"] - 1
    yearly["spy"] = yearly["spy_end"]/yearly["spy_start"] - 1
    yearly["diff"] = yearly["bot"] - yearly["spy"]

    print(f"\n{'='*68}")
    print(f"  5-YEAR BACKTEST RESULTS · 2020-2024")
    print(f"{'='*68}\n")
    print(f"  {'Year':<6} {'Days':>5} {'Bot':>10} {'SPY':>10} {'Diff':>10}")
    print(f"  {'-'*46}")
    for y, row in yearly.iterrows():
        mark = "✓" if row["diff"] > 0 else "✗"
        print(f"  {y:<6} {int(row['days']):>5} {row['bot']*100:>+9.1f}% {row['spy']*100:>+9.1f}% {row['diff']*100:>+9.1f}% {mark}")
    print(f"  {'-'*46}")

    # Total
    pt = pv/1000 - 1
    st = spy_v/1000 - 1
    print(f"  {'TOTAL':<6} {len(df):>5} {pt*100:>+9.1f}% {st*100:>+9.1f}% {(pt-st)*100:>+9.1f}%")

    # Stats
    bot_ret = df["port_ret"]
    spy_ret = df["spy_ret"]
    bot_vol = bot_ret.std() * np.sqrt(252)
    spy_vol = spy_ret.std() * np.sqrt(252)
    bot_sharpe = (bot_ret.mean()*252)/(bot_ret.std()*np.sqrt(252)) if bot_ret.std() > 0 else 0
    spy_sharpe = (spy_ret.mean()*252)/(spy_ret.std()*np.sqrt(252)) if spy_ret.std() > 0 else 0
    yrs = len(df)/252
    bot_cagr = (pv/1000)**(1/yrs) - 1
    spy_cagr = (spy_v/1000)**(1/yrs) - 1

    cum = (1 + bot_ret).cumprod()
    dd = (cum - cum.cummax())/cum.cummax()
    spy_cum = (1 + spy_ret).cumprod()
    spy_dd = (spy_cum - spy_cum.cummax())/spy_cum.cummax()

    print(f"\n{'  '+'─'*60}")
    print(f"  KEY STATS")
    print(f"  {'─'*60}")
    print(f"  Starting:        $1,000")
    print(f"  Bot final:       ${pv:,.2f}  (+{pt*100:.1f}%)")
    print(f"  SPY final:       ${spy_v:,.2f}  (+{st*100:.1f}%)")
    print(f"  Outperformance:  ${pv - spy_v:+,.2f}  ({(pt-st)*100:+.1f} pp)")
    print()
    print(f"  CAGR:            bot {bot_cagr*100:.1f}%   SPY {spy_cagr*100:.1f}%")
    print(f"  Sharpe:          bot {bot_sharpe:.2f}     SPY {spy_sharpe:.2f}")
    print(f"  Ann. volatility: bot {bot_vol*100:.1f}%    SPY {spy_vol*100:.1f}%")
    print(f"  Max drawdown:    bot {dd.min()*100:.1f}%   SPY {spy_dd.min()*100:.1f}%")
    print(f"  Best day:        bot {bot_ret.max()*100:+.2f}%   SPY {spy_ret.max()*100:+.2f}%")
    print(f"  Worst day:       bot {bot_ret.min()*100:+.2f}%   SPY {spy_ret.min()*100:+.2f}%")
    print(f"  Daily win rate:  {(bot_ret > spy_ret).mean()*100:.0f}% of {len(df)} days")

    # Top picks
    print(f"\n  TOP 15 MOST-PICKED STOCKS (alpha sleeve):")
    for t, days in sorted(pick_hist.items(), key=lambda x: -x[1])[:15]:
        print(f"    {t:6} {days:4d} days ({days/len(df)*100:.0f}% of period)")


if __name__ == "__main__":
    main()
