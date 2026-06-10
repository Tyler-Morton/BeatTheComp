"""Challenger strategy: a 4-sleeve diversified book under one vol budget.

Pure logic — no broker imports, no trading. Both the backtest and the live
pipeline call these same functions, so what we test is what we trade.

Sleeves (budgets sum to 1.0 before vol targeting):
  CORE    35%  Trend-ramped leveraged tech (QQQ/QLD ramp, IEF cushion). This is
               the validated "Gradual" engine from the strategy lab: effective
               leverage ramps 0 -> 1.5x with QQQ's distance above/below its
               200-day average, instead of flipping all-or-nothing.
  TREND   25%  Cross-asset time-series momentum (SPY, EFA, TLT, GLD, DBC).
               Each asset above its 10-month average gets an equal slice;
               anything below parks its slice in cash. The crisis-alpha sleeve.
  LOWVOL  20%  Defensive equity (XLP/XLU/XLV equal-weight). The low-volatility
               anomaly: similar return, lower risk, always on.
  BALLAST 20%  TLT + GLD, inverse-vol weighted. The zig when stocks zag.

After the sleeves are combined, the live bot passes the result through the SAME
risk_overlay.apply_overlay() the champion uses, scaling the whole book toward
TARGET_VOL and parking the remainder in SHV.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

TD = 252
MA_LONG = 200          # core engine trend filter
MA_TSMOM = 210         # ~10 months, the classic time-series-momentum filter
BASE_LEV = 1.5         # core engine max effective leverage
RAMP_BAND = 0.10       # core ramps 0->full over QQQ being -10%..+10% vs its MA

TARGET_VOL = 0.16      # the whole-book vol budget (annualized)
CASH = "SHV"

# Backtest verdict (2026-06-09, challenger/backtest.py, 2007-2026 Tiingo data):
# the TSMOM trend sleeve FAILED the simpler-beats-it test (the no-trend book had
# higher Sharpe AND CAGR in nearly every window), so its budget is 0 and the
# book ships with three sleeves. Trend stays on the bench for a better
# implementation later; the code remains so it can be re-tested.
SLEEVE_BUDGETS = {"core": 0.45, "trend": 0.0, "lowvol": 0.28, "ballast": 0.27}

CORE_ASSETS = ["QQQ", "QLD", "IEF"]
TREND_ASSETS = ["SPY", "EFA", "TLT", "GLD", "DBC"]
LOWVOL_ASSETS = ["XLP", "XLU", "XLV"]
BALLAST_ASSETS = ["TLT", "GLD"]

ALL_TICKERS = sorted(set(CORE_ASSETS + TREND_ASSETS + LOWVOL_ASSETS
                         + BALLAST_ASSETS + [CASH]))


# ── Sleeve builders (each returns weights summing to its budget) ──────────────

def core_sleeve(px: pd.DataFrame, budget: float) -> dict[str, float]:
    """Gradual leverage ramp: effective QQQ exposure = BASE_LEV * ramp(z)."""
    qqq = px["QQQ"]
    ma = qqq.rolling(MA_LONG).mean().iloc[-1]
    if not np.isfinite(ma) or ma <= 0:
        return {"IEF": budget}
    z = (qqq.iloc[-1] - ma) / ma
    frac = float(np.clip((z + RAMP_BAND) / (2 * RAMP_BAND), 0.0, 1.0))
    eff = BASE_LEV * frac                     # desired QQQ-equivalent exposure (x budget)

    w: dict[str, float] = {}
    E = budget * eff
    if E <= 0:
        w["IEF"] = budget                     # fully de-risked: cushion in bonds
    elif E <= budget:
        w["QQQ"] = E                          # under-levered: QQQ + IEF cushion
        if budget - E > 1e-9:
            w["IEF"] = budget - E
    else:
        E = min(E, 2 * budget)                # levered: blend QQQ with 2x QLD
        w["QLD"] = E - budget
        w["QQQ"] = 2 * budget - E
    return w


def trend_sleeve(px: pd.DataFrame, budget: float) -> dict[str, float]:
    """Equal-weight the assets above their 10-month average; rest to cash."""
    winners = []
    for t in TREND_ASSETS:
        if t not in px.columns:
            continue
        ma = px[t].rolling(MA_TSMOM).mean().iloc[-1]
        if np.isfinite(ma) and px[t].iloc[-1] > ma:
            winners.append(t)
    w: dict[str, float] = {}
    slice_ = budget / len(TREND_ASSETS)
    for t in winners:
        w[t] = w.get(t, 0.0) + slice_
    parked = budget - slice_ * len(winners)
    if parked > 1e-9:
        w[CASH] = w.get(CASH, 0.0) + parked
    return w


def lowvol_sleeve(px: pd.DataFrame, budget: float) -> dict[str, float]:
    cols = [t for t in LOWVOL_ASSETS if t in px.columns]
    if not cols:
        return {CASH: budget}
    each = budget / len(cols)
    return {t: each for t in cols}


def ballast_sleeve(px: pd.DataFrame, budget: float) -> dict[str, float]:
    cols = [t for t in BALLAST_ASSETS if t in px.columns]
    if not cols:
        return {CASH: budget}
    rets = px[cols].pct_change(fill_method=None).tail(60)
    vol = rets.std()
    inv = (1.0 / vol.replace(0, np.nan)).fillna(0.0)
    if inv.sum() <= 0:
        each = budget / len(cols)
        return {t: each for t in cols}
    w = inv / inv.sum() * budget
    return {t: float(v) for t, v in w.items()}


def combined_weights(px: pd.DataFrame,
                     budgets: dict[str, float] | None = None) -> dict[str, float]:
    """All four sleeves merged into one weights dict (sums to ~1.0, incl. cash)."""
    b = budgets or SLEEVE_BUDGETS
    builders = {"core": core_sleeve, "trend": trend_sleeve,
                "lowvol": lowvol_sleeve, "ballast": ballast_sleeve}
    w: dict[str, float] = {}
    for name, budget in b.items():
        if budget <= 0:
            continue
        for t, v in builders[name](px, budget).items():
            w[t] = w.get(t, 0.0) + v
    return {t: v for t, v in w.items() if v > 1e-9}
