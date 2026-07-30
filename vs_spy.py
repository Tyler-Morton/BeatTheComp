"""vs_spy.py — the live scoreboard: every book vs SPY since its own launch.

Pulls each account's REAL equity curve from Alpaca (portfolio-history API, so it
doesn't depend on our CSV logs), grabs SPY from Tiingo over the same windows, and
prints each book's return vs SPY-over-the-identical-period, plus the combined
"household" view (all three books together vs parking the same dollars in SPY).

Run: python3 vs_spy.py          (saves vs_spy.png alongside the table)
"""
import os
import warnings
from datetime import datetime

warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import requests
from dotenv import load_dotenv

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

load_dotenv()

# book -> (env prefix, inception date = first day capital was live)
BOOKS = {
    "Champion":   ("ALPACA",            "2026-05-22"),
    "Challenger": ("CHALLENGER_ALPACA", "2026-06-10"),
    "VolBot":     ("VOLBOT_ALPACA",     "2026-06-24"),
}


def alpaca_equity(prefix: str) -> pd.Series:
    """Daily equity curve for one account, straight from Alpaca."""
    from alpaca.trading.client import TradingClient
    from alpaca.trading.requests import GetPortfolioHistoryRequest
    tc = TradingClient(os.getenv(f"{prefix}_API_KEY"),
                       os.getenv(f"{prefix}_SECRET_KEY"), paper=True)
    hist = tc.get_portfolio_history(GetPortfolioHistoryRequest(period="4M",
                                                               timeframe="1D"))
    s = pd.Series(hist.equity,
                  index=pd.to_datetime(hist.timestamp, unit="s").normalize(),
                  dtype=float, name="equity")
    return s[s > 0]          # drop days the API returned a bogus 0


def spy_series() -> pd.Series:
    r = requests.get("https://api.tiingo.com/tiingo/daily/SPY/prices",
                     params={"startDate": "2026-05-01",
                             "token": os.getenv("TIINGO_API_KEY"),
                             "format": "json"}, timeout=30)
    df = pd.DataFrame(r.json())
    df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None).dt.normalize()
    return df.set_index("date")["adjClose"].sort_index()


def main() -> None:
    spy = spy_series()
    print(f"SPY data through {spy.index[-1].date()}\n")

    rows, curves = [], {}
    total_now = total_spy_counterfactual = 0.0

    for name, (prefix, inception) in BOOKS.items():
        eq = alpaca_equity(prefix)
        eq = eq[eq.index >= inception]
        if eq.empty:
            print(f"{name}: no equity history returned — skipped")
            continue
        start, now = eq.iloc[0], eq.iloc[-1]

        spy_win = spy[spy.index >= eq.index[0]]
        spy_ret = spy_win.iloc[-1] / spy_win.iloc[0] - 1.0
        book_ret = now / start - 1.0

        rows.append((name, eq.index[0].date(), start, now,
                     book_ret, spy_ret, book_ret - spy_ret))
        total_now += now
        total_spy_counterfactual += start * (1.0 + spy_ret)
        curves[name] = (eq / start - 1.0) * 100

    hdr = (f"{'Book':<12}{'Since':<12}{'Start $':>10}{'Now $':>12}"
           f"{'Book':>9}{'SPY':>9}{'vs SPY':>9}")
    print(hdr)
    print("-" * len(hdr))
    for name, since, start, now, br, sr, d in rows:
        print(f"{name:<12}{str(since):<12}{start:>10,.0f}{now:>12,.2f}"
              f"{br:>8.2%}{sr:>9.2%}{d:>+9.2%}")
    print("-" * len(hdr))
    total_start = sum(r[2] for r in rows)
    comb = total_now / total_start - 1.0
    comb_spy = total_spy_counterfactual / total_start - 1.0
    print(f"{'COMBINED':<12}{'':<12}{total_start:>10,.0f}{total_now:>12,.2f}"
          f"{comb:>8.2%}{comb_spy:>9.2%}{comb - comb_spy:>+9.2%}")
    print("\n(SPY column = SPY's return over that book's exact window. "
          "COMBINED = all books vs the same dollars parked in SPY.)")

    # chart: each book's cumulative % since its own launch, SPY from earliest
    fig, ax = plt.subplots(figsize=(10, 5))
    colors = {"Champion": "#C44E52", "Challenger": "#4C72B0", "VolBot": "#55A868"}
    for name, curve in curves.items():
        ax.plot(curve.index, curve.values, label=name,
                color=colors.get(name), lw=1.7)
    earliest = min(c.index[0] for c in curves.values())
    spy_win = spy[spy.index >= earliest]
    ax.plot(spy_win.index, (spy_win / spy_win.iloc[0] - 1) * 100,
            label="SPY (from May 22)", color="#888888", ls="--", lw=1.4)
    ax.axhline(0, color="black", lw=0.8)
    ax.set_title("Live books vs SPY — cumulative % since each launch",
                 fontweight="bold")
    ax.set_ylabel("Return since launch (%)")
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig("vs_spy.png", dpi=130)
    print("Chart saved -> vs_spy.png")


if __name__ == "__main__":
    main()
