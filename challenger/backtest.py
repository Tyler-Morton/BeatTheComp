"""Challenger backtest: the 4-sleeve diversified book vs SPY and the champion proxy.

RESEARCH ONLY — trades nothing. Pulls clean history from Tiingo, then tests the
exact sleeve logic (sleeves.py) and the exact live vol-targeting code
(risk_overlay.vol_target_scaler) that the live challenger pipeline uses.

The law: the challenger only gets to trade if it beats the simpler alternatives
out-of-sample here, and the Deflated Sharpe Ratio says the edge isn't luck.

Run:  python3 challenger/backtest.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from risk_overlay import vol_target_scaler          # the LIVE overlay code
import sleeves
from sleeves import combined_weights, SLEEVE_BUDGETS, CASH

TD = 252
RF = 0.045                  # Sharpe hurdle (matches the lab's convention)
CASH_YIELD = 0.02           # conservative flat yield credited to the cash sleeve
TCOST = 0.0010              # 10 bps per unit turnover
DRIFT = 0.02                # only "trade" when an asset drifts >2% (mirrors live)
CACHE = HERE / "prices_cache.parquet"

CHAMPION_3X = ["TQQQ", "SOXL", "TECL"]
ALL_TICKERS = sorted(set(sleeves.ALL_TICKERS + CHAMPION_3X))


# ── Data ──────────────────────────────────────────────────────────────────────

def load_data() -> pd.DataFrame:
    if CACHE.exists():
        px = pd.read_parquet(CACHE)
        if all(t in px.columns for t in ALL_TICKERS):
            return px
    import requests
    tok = os.getenv("TIINGO_API_KEY")
    frames = []
    for t in ALL_TICKERS:
        r = requests.get(f"https://api.tiingo.com/tiingo/daily/{t}/prices",
                         params={"startDate": "2005-01-01", "token": tok,
                                 "format": "json", "resampleFreq": "daily"}, timeout=30)
        j = r.json()
        if isinstance(j, list) and j:
            df = pd.DataFrame(j)
            df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None)
            frames.append(df.set_index("date")["adjClose"].rename(t))
            print(f"  {t}: {len(df)} rows {df['date'].iloc[0].date()} -> {df['date'].iloc[-1].date()}")
        else:
            print(f"  {t}: FAILED ({str(j)[:80]})")
    px = pd.concat(frames, axis=1).sort_index().ffill()
    px.to_parquet(CACHE)
    return px


# ── Engine: monthly sleeve rebalance + DAILY vol-target scaling ───────────────

def run_book(px: pd.DataFrame, budgets: dict, target_vol: float,
             start: str | None = None) -> pd.Series:
    """Daily returns of a sleeve book under the live vol-targeting overlay."""
    idx = px.index
    dr = px.pct_change(fill_method=None)
    rebal = set(pd.date_range(idx[0], idx[-1], freq="BME"))
    out = pd.Series(0.0, index=idx)

    base: dict = {}
    held: dict = {}
    for i in range(260, len(idx)):
        d = idx[i]
        if d in rebal or not base:
            base = combined_weights(px.iloc[:i + 1], budgets)

        # split the cash slice out; vol-scale only the risky part (live behavior)
        risky = {t: v for t, v in base.items() if t != CASH}
        s = vol_target_scaler(dr.iloc[max(0, i - 79):i + 1], risky, target_vol)
        desired = {t: v * s for t, v in risky.items()}
        desired[CASH] = base.get(CASH, 0.0) + (1.0 - s) * sum(risky.values())

        if not held or max(abs(desired.get(t, 0) - held.get(t, 0))
                           for t in set(desired) | set(held)) > DRIFT:
            turn = sum(abs(desired.get(t, 0) - held.get(t, 0))
                       for t in set(desired) | set(held))
            out.iloc[i] -= TCOST * turn
            held = dict(desired)

        ret = 0.0
        for t, w in held.items():
            if t == CASH:
                ret += w * (CASH_YIELD / TD)
            else:
                r = dr.iloc[i].get(t, np.nan)
                ret += w * (r if np.isfinite(r) else 0.0)
        out.iloc[i] += ret

    if start:
        out = out[out.index >= pd.Timestamp(start)]
    return out


def run_champion_proxy(px: pd.DataFrame, target_vol: float = 0.20) -> pd.Series:
    """Approximation of the live bot: 3x tech basket when risk-on, defensive when
    not, vol-targeted at 20%. Only valid from 2011 (3x ETF inception)."""
    idx = px.index
    dr = px.pct_change(fill_method=None)
    rebal = set(pd.date_range(idx[0], idx[-1], freq="BME"))
    out = pd.Series(0.0, index=idx)
    base, held = {}, {}
    for i in range(260, len(idx)):
        d = idx[i]
        if d < pd.Timestamp("2011-01-01"):
            continue
        if d in rebal or not base:
            hist = px.iloc[:i + 1]
            spy = hist["SPY"]
            if spy.iloc[-1] > spy.rolling(200).mean().iloc[-1]:
                tech = [c for c in CHAMPION_3X if c in hist.columns]
                vol = hist[tech].pct_change(fill_method=None).tail(60).std()
                inv = (1.0 / vol.replace(0, np.nan)).fillna(0.0)
                base = (inv / inv.sum()).to_dict() if inv.sum() > 0 else {}
            else:
                base = {"TLT": 0.4, "GLD": 0.3, "IEF": 0.3}
        s = vol_target_scaler(dr.iloc[max(0, i - 79):i + 1], base, target_vol)
        desired = {t: v * s for t, v in base.items()}
        desired[CASH] = (1.0 - s) * sum(base.values())
        if not held or max(abs(desired.get(t, 0) - held.get(t, 0))
                           for t in set(desired) | set(held)) > DRIFT:
            turn = sum(abs(desired.get(t, 0) - held.get(t, 0))
                       for t in set(desired) | set(held))
            out.iloc[i] -= TCOST * turn
            held = dict(desired)
        ret = 0.0
        for t, w in held.items():
            if t == CASH:
                ret += w * (CASH_YIELD / TD)
            else:
                r = dr.iloc[i].get(t, np.nan)
                ret += w * (r if np.isfinite(r) else 0.0)
        out.iloc[i] += ret
    return out[out.index >= pd.Timestamp("2011-07-01")]


# ── Metrics, DSR ──────────────────────────────────────────────────────────────

def metrics(ret: pd.Series) -> dict:
    ret = ret.dropna()
    if not len(ret):
        return {k: float("nan") for k in ["cagr", "vol", "sharpe", "maxdd", "worst", "tot"]}
    eq = (1 + ret.fillna(0)).cumprod()
    yrs = (eq.index[-1] - eq.index[0]).days / 365.25
    return {
        "cagr": (eq.iloc[-1]) ** (1 / yrs) - 1 if yrs > 0 else 0,
        "vol": ret.std() * np.sqrt(TD),
        "sharpe": (ret.mean() - RF / TD) / ret.std() * np.sqrt(TD) if ret.std() > 0 else 0,
        "maxdd": ((eq - eq.cummax()) / eq.cummax()).min(),
        "worst": ret.min(),
        "tot": eq.iloc[-1] - 1,
    }


def deflated_sharpe(ret: pd.Series, n_trials: int) -> float:
    """Bailey & Lopez de Prado: P(true Sharpe > 0 | we picked the best of K tries)."""
    from scipy.stats import norm, skew, kurtosis
    r = ret.dropna().values
    T = len(r)
    sr = r.mean() / r.std()                      # daily (non-annualized) Sharpe
    sk = skew(r)
    ku = kurtosis(r, fisher=False)
    g = 0.5772156649
    sr0 = np.sqrt(1.0 / (T - 1)) * ((1 - g) * norm.ppf(1 - 1.0 / n_trials)
                                    + g * norm.ppf(1 - 1.0 / (n_trials * np.e)))
    num = (sr - sr0) * np.sqrt(T - 1)
    den = np.sqrt(max(1 - sk * sr + (ku - 1) / 4.0 * sr ** 2, 1e-12))
    return float(norm.cdf(num / den))


def show(title: str, rows: dict[str, pd.Series], windows: list[str]):
    for win in windows:
        print(f"-- since {win} " + "-" * 44)
        print(f"  {'book':<22}{'CAGR':>8}{'Vol':>7}{'Sharpe':>8}{'MaxDD':>8}{'Worst d':>9}")
        for name, r in rows.items():
            rs = r[r.index >= pd.Timestamp(win)]
            m = metrics(rs)
            print(f"  {name:<22}{m['cagr']:>7.1%}{m['vol']:>7.1%}{m['sharpe']:>8.2f}"
                  f"{m['maxdd']:>8.1%}{m['worst']:>9.1%}")
        print()


def main():
    print("Loading Tiingo history...")
    px = load_data()
    print(f"Range {px.index[0].date()} -> {px.index[-1].date()}\n")

    spy = px["SPY"].pct_change(fill_method=None)

    print("Running books (monthly sleeve rebal, daily vol scaling)...")
    # The 4 configs we are honestly trying (K=4 for the DSR penalty):
    no_trend = {"core": 0.45, "lowvol": 0.28, "ballast": 0.27}
    books = {
        "SPY (buy&hold)": spy,
        "Champion proxy 3x+VT20": run_champion_proxy(px),
        "A: 4-sleeve VT16": run_book(px, SLEEVE_BUDGETS, 0.16),
        "B: 4-sleeve VT20": run_book(px, SLEEVE_BUDGETS, 0.20),
        "C: no-trend VT16": run_book(px, no_trend, 0.16),
        "D: core-only VT16": run_book(px, {"core": 1.0}, 0.16),
    }

    show("scorecard", books, ["2007-07-01", "2011-07-01", "2018-01-01", "2022-01-01"])

    print("=" * 60)
    print("DEFLATED SHARPE (K=4 configs tried, full window)")
    for name in ["A: 4-sleeve VT16", "B: 4-sleeve VT20", "C: no-trend VT16", "D: core-only VT16"]:
        d = deflated_sharpe(books[name], 4)
        print(f"  {name:<22} DSR = {d:.1%}")

    print()
    print("CORRELATION of daily returns (2011+, the diversification proof):")
    a = books["A: 4-sleeve VT16"]
    cmp_keys = ["SPY (buy&hold)", "Champion proxy 3x+VT20"]
    for k in cmp_keys:
        joint = pd.concat([a, books[k]], axis=1).dropna()
        joint = joint[joint.index >= pd.Timestamp("2011-07-01")]
        print(f"  A vs {k:<24} corr = {joint.iloc[:, 0].corr(joint.iloc[:, 1]):.2f}")


if __name__ == "__main__":
    main()
