"""One-command performance tracker: every bot vs SPY since its own launch.

Run: python3 tracker.py
Prints the comparison table and saves tracker.png (cumulative curves, common window).
Read-only — talks to the accounts but changes nothing.
"""
import os
import warnings

import numpy as np
import pandas as pd
import requests

warnings.filterwarnings("ignore")
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from dotenv import load_dotenv

load_dotenv()

ACCOUNTS = {
    "CHAMP": ("ALPACA_API_KEY", "ALPACA_SECRET_KEY"),
    "CHALL": ("CHALLENGER_ALPACA_API_KEY", "CHALLENGER_ALPACA_SECRET_KEY"),
    "VOLBOT": ("VOLBOT_ALPACA_API_KEY", "VOLBOT_ALPACA_SECRET_KEY"),
}


def equity_curve(kenv: str, senv: str) -> pd.Series:
    h = {"APCA-API-KEY-ID": os.getenv(kenv), "APCA-API-SECRET-KEY": os.getenv(senv)}
    r = requests.get("https://paper-api.alpaca.markets/v2/account/portfolio/history",
                     headers=h, params={"period": "1A", "timeframe": "1D"}, timeout=30).json()
    s = pd.Series(r["equity"], index=pd.to_datetime(r["timestamp"], unit="s")).astype(float)
    s.index = s.index.normalize()
    return s[s > 0].dropna()


def spy_series() -> pd.Series:
    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.data.requests import StockBarsRequest
    from alpaca.data.timeframe import TimeFrame
    from alpaca.data.enums import DataFeed
    cl = StockHistoricalDataClient(os.getenv("ALPACA_API_KEY"), os.getenv("ALPACA_SECRET_KEY"))
    sb = cl.get_stock_bars(StockBarsRequest(symbol_or_symbols="SPY", timeframe=TimeFrame.Day,
                                            start=pd.Timestamp.now() - pd.Timedelta(days=400),
                                            feed=DataFeed.IEX)).df
    spy = sb.xs("SPY", level=0)["close"]
    spy.index = pd.to_datetime(spy.index).tz_localize(None).normalize()
    return spy


def main() -> None:
    spy = spy_series()
    curves = {}
    print(f"{'bot':8}{'launch':>12}{'days':>6}{'start$':>11}{'now$':>11}"
          f"{'bot%':>8}{'SPY%':>8}{'vs SPY':>9}")
    for name, (k, s) in ACCOUNTS.items():
        try:
            eq = equity_curve(k, s)
        except Exception as exc:
            print(f"{name:8} error: {str(exc)[:50]}")
            continue
        curves[name] = eq
        d0, d1 = eq.index[0], eq.index[-1]
        bot_ret = eq.iloc[-1] / eq.iloc[0] - 1
        w = spy[(spy.index >= d0) & (spy.index <= d1)]
        spy_ret = w.iloc[-1] / w.iloc[0] - 1 if len(w) > 1 else 0.0
        print(f"{name:8}{str(d0.date()):>12}{len(eq):>6}{eq.iloc[0]:>11,.0f}{eq.iloc[-1]:>11,.0f}"
              f"{bot_ret*100:>+7.1f}%{spy_ret*100:>+7.1f}%{(bot_ret-spy_ret)*100:>+8.1f}%")
    print("\nnotes: short windows are noise, not signal — judge over months, not weeks.")
    print("       VOLBOT is market-neutral premium-selling; 'vs SPY' is not its benchmark")
    print("       (judge it on income vs risk and correlation once it has trades).")

    # chart: common window, all curves + SPY rebased to 100
    if curves:
        start = max(c.index[0] for c in curves.values())
        fig, ax = plt.subplots(figsize=(10, 5))
        for name, c in curves.items():
            cc = c[c.index >= start]
            ax.plot(cc.index, cc / cc.iloc[0] * 100, label=name, lw=1.6)
        sp = spy[spy.index >= start]
        ax.plot(sp.index, sp / sp.iloc[0] * 100, label="SPY", color="#888", lw=1.4, ls="--")
        ax.set_title("Bots vs SPY (rebased = 100 at common start)", fontweight="bold")
        ax.legend(); ax.grid(True, alpha=0.3)
        fig.tight_layout()
        fig.savefig("tracker.png", dpi=130)
        print("\nchart saved -> tracker.png")


if __name__ == "__main__":
    main()
