"""Performance report — the DEPLOYED (vol-targeted) bot vs SPY, full metric suite.

Computes the same metrics a Bloomberg equity backtest reports (alpha, beta, vol,
Sharpe, Treynor, max drawdown, information ratio, idiosyncratic risk) so the bot
can be compared apples-to-apples against a SIF-style pitch deck (e.g. ProfitProphets).

Faithful to the LIVE bot:
  - regime picks the strategy (STRATEGY_BY_REGIME), same as AUTO_SELECT
  - the vol-targeting overlay scales the book to OVERLAY_TARGET_VOL, rest to cash
  - ML throttle OFF (matches the validated config) and no alpha sleeve
    (sentiment/trending can't be replayed historically)

Run: python3 perf_report.py
"""
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from config import (ASSETS, RISK_FREE_RATE, DRAWDOWN_CIRCUIT_BREAKER,
                    STRATEGY_BY_REGIME, OVERLAY_TARGET_VOL)
from backtest import _detect_regime_from_prices, _compute_weights
from optimizer import select_strategy
from risk_overlay import vol_target_scaler

TRADING_DAYS = 252
RF_DAILY = RISK_FREE_RATE / TRADING_DAYS


def _load_tiingo(tickers: list[str], start: str = "2019-01-01") -> pd.DataFrame:
    """Clean daily adjusted-close history from Tiingo (reliable, no rate-limit games)."""
    import os
    import requests
    from dotenv import load_dotenv
    load_dotenv("/Users/tylermorton/Documents/IWillBeatS&P/.env")
    tok = os.getenv("TIINGO_API_KEY")
    frames = []
    for t in tickers:
        r = requests.get(f"https://api.tiingo.com/tiingo/daily/{t}/prices",
                         params={"startDate": start, "token": tok,
                                 "format": "json", "resampleFreq": "daily"}, timeout=30)
        j = r.json()
        if isinstance(j, list) and j:
            df = pd.DataFrame(j)
            df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None)
            frames.append(df.set_index("date")["adjClose"].rename(t))
            print(f"  {t}: {len(df)} rows")
        else:
            print(f"  {t}: FAILED ({str(j)[:80]})")
    # ffill only (NOT bfill) so pre-launch dates stay NaN, not a flat constant.
    return pd.concat(frames, axis=1).sort_index().ffill()


def simulate_deployed(prices: pd.DataFrame) -> pd.Series:
    """Daily equity curve of the regime-selected strategy WITH the vol overlay."""
    asset_cols = [c for c in ASSETS if c in prices.columns]
    returns = prices[asset_cols].pct_change()
    rebal_dates = pd.date_range(prices.index[0], prices.index[-1], freq="BME")

    equity = pd.Series(index=prices.index, dtype=float)
    equity.iloc[0] = 1.0
    weights: dict[str, float] = {}
    ath = 1.0

    for i in range(1, len(prices)):
        date = prices.index[i]
        if date in rebal_dates or i == 1:
            hist_start = max(0, i - 252)
            # Use only assets with full, real history in this window. Tiingo leaves
            # pre-launch dates as NaN (e.g. BITO starts 2021); NaN or flat columns
            # produce NaN correlations that crash HRP, so filter them out per-window.
            hist = returns.iloc[hist_start:i][asset_cols].dropna(how="all")
            hist = hist.loc[:, hist.notna().all()]
            hist = hist.loc[:, hist.std(skipna=True) > 1e-9]
            if not hist.empty and len(hist) >= 20:
                regime = _detect_regime_from_prices(prices.iloc[hist_start:i])
                strat = select_strategy(regime, hist)   # faithful to live: adaptive selector
                weights = _compute_weights(strat, hist, regime)
            elif asset_cols:
                weights = {t: 1.0 / len(asset_cols) for t in asset_cols}

        # Vol overlay: scale the book toward target vol, park the rest in cash.
        scaler = vol_target_scaler(returns.iloc[:i], weights,
                                   target_vol=OVERLAY_TARGET_VOL, window=40)
        asset_ret = sum(weights.get(t, 0.0) * returns.loc[date, t]
                        for t in weights
                        if t in returns.columns and not np.isnan(returns.loc[date, t]))
        day_ret = scaler * asset_ret + (1.0 - scaler) * RF_DAILY

        prev = equity.iloc[i - 1]
        new = prev * (1.0 + day_ret)
        ath = max(ath, new)
        if (new / ath - 1.0) < -DRAWDOWN_CIRCUIT_BREAKER:
            new = prev  # circuit breaker: freeze
        equity.iloc[i] = new
    return equity.dropna()


def _cagr(eq: pd.Series) -> float:
    years = (eq.index[-1] - eq.index[0]).days / 365.25
    return (eq.iloc[-1] / eq.iloc[0]) ** (1.0 / years) - 1.0 if years > 0 else 0.0


def metrics(eq: pd.Series, bench: pd.Series, is_bench: bool = False) -> dict:
    r = eq.pct_change().dropna()
    b = bench.pct_change().dropna()
    idx = r.index.intersection(b.index)
    r, b = r.loc[idx], b.loc[idx]

    cagr = _cagr(eq)
    vol = r.std() * np.sqrt(TRADING_DAYS)
    sharpe = (r.mean() - RF_DAILY) / r.std() * np.sqrt(TRADING_DAYS) if r.std() > 0 else 0.0
    maxdd = ((eq - eq.cummax()) / eq.cummax()).min()

    if is_bench:
        return dict(ret=cagr, alpha=np.nan, beta=1.0, vol=vol, sharpe=sharpe,
                    treynor=(cagr - RISK_FREE_RATE) / 1.0, maxdd=maxdd,
                    info=np.nan, idio=np.nan)

    # CAPM regression: excess_strat = alpha + beta * excess_bench + resid
    re, be = r - RF_DAILY, b - RF_DAILY
    beta = np.cov(re, be, ddof=1)[0, 1] / np.var(be, ddof=1)
    alpha_daily = re.mean() - beta * be.mean()
    alpha = alpha_daily * TRADING_DAYS
    resid = re - (alpha_daily + beta * be)
    idio = resid.std(ddof=1) * np.sqrt(TRADING_DAYS)
    treynor = (cagr - RISK_FREE_RATE) / beta if abs(beta) > 1e-9 else np.nan

    active = r - b
    info = active.mean() / active.std() * np.sqrt(TRADING_DAYS) if active.std() > 0 else np.nan

    return dict(ret=cagr, alpha=alpha, beta=beta, vol=vol, sharpe=sharpe,
                treynor=treynor, maxdd=maxdd, info=info, idio=idio)


def _fmt(m: dict) -> str:
    def g(k, pct=False, dec=2):
        v = m[k]
        if v is None or (isinstance(v, float) and np.isnan(v)):
            return "  --  "
        return f"{v*100:.2f}%" if pct else f"{v:.{dec}f}"
    return (f"{g('ret', pct=True):>9} {g('alpha', pct=True):>7} {g('beta'):>6} "
            f"{g('vol', pct=True):>9} {g('sharpe'):>7} {g('treynor'):>8} "
            f"{g('maxdd', pct=True):>9} {g('info'):>7} {g('idio', pct=True):>9}")


def main() -> None:
    import os
    cache = "perf_prices.parquet"
    if os.path.exists(cache):
        prices = pd.read_parquet(cache)
    else:
        tickers = list(dict.fromkeys(ASSETS + ["SPY"]))
        prices = _load_tiingo(tickers)
        prices.to_parquet(cache)
    prices = prices.dropna(subset=["SPY"])
    print(f"\nData window: {prices.index[0].date()} → {prices.index[-1].date()} "
          f"({(prices.index[-1]-prices.index[0]).days/365.25:.1f} years)\n")

    strat_eq = simulate_deployed(prices)
    spy_eq = (1.0 + prices["SPY"].pct_change().fillna(0)).cumprod()
    spy_eq = spy_eq.loc[strat_eq.index]

    # Full window + trailing 1-year, to mirror the ProfitProphets 10yr/1yr split.
    one_yr_start = strat_eq.index[-1] - pd.Timedelta(days=365)
    windows = {
        "FULL": (strat_eq, spy_eq),
        "1-YEAR": (strat_eq.loc[one_yr_start:], spy_eq.loc[one_yr_start:]),
    }

    hdr = (f"{'':<22}{'Return':>9} {'Alpha':>7} {'Beta':>6} {'Vol':>9} "
           f"{'Sharpe':>7} {'Treynor':>8} {'MaxDD':>9} {'Info':>7} {'Idio':>9}")
    print(hdr)
    print("-" * len(hdr))
    for label, (se, be) in windows.items():
        print(f"{'OUR BOT (' + label + ')':<22}{_fmt(metrics(se, be))}")
        print(f"{'SPY (' + label + ')':<22}{_fmt(metrics(be, be, is_bench=True))}")
    # ProfitProphets reported numbers (from their deck) for reference.
    print("-" * len(hdr))
    print(f"{'ProfitProphets 10yr':<22}{'15.87%':>9} {'4.07%':>7} {'0.98':>6} "
          f"{'25.58%':>9} {'0.68':>7} {'0.17':>8} {'-55.20%':>9} {'0.17':>7} {'20.93%':>9}")
    print(f"{'  their SPX 10yr':<22}{'14.15%':>9} {'--':>7} {'1.00':>6} "
          f"{'15.00%':>9} {'0.69':>7} {'0.06':>8} {'-33.90%':>9} {'--':>7} {'--':>9}")
    print(f"{'ProfitProphets 1yr':<22}{'28.42%':>9} {'14.11%':>7} {'0.90':>6} "
          f"{'24.02%':>9} {'1.18':>7} {'0.27':>8} {'-30.00%':>9} {'0.59':>7} {'17.73%':>9}")

    # Chart: cumulative return % vs SPY (like the deck).
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(strat_eq.index, (strat_eq / strat_eq.iloc[0] - 1) * 100,
            label="Our Bot", color="#C44E52", lw=1.8)
    ax.plot(spy_eq.index, (spy_eq / spy_eq.iloc[0] - 1) * 100,
            label="SPY", color="#888888", lw=1.5)
    ax.axhline(0, color="black", ls="--", lw=0.8)
    ax.set_title("Cumulative Return (%) — Our Bot vs SPY", fontweight="bold")
    ax.set_ylabel("Cumulative Return (%)")
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig("perf_report.png", dpi=130)
    print("\nChart saved → perf_report.png")


if __name__ == "__main__":
    main()
