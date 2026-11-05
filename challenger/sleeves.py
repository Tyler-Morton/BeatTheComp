"""Challenger strategy: a diversified book of three active sleeves under one vol budget.

No broker imports and no trading. The backtest and live pipeline call these same functions, so what
we test is what we trade. Budgets before vol targeting: core 45%, low-vol 28%, ballast 27%, trend 0%.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

TD = 252
MA_LONG = 200          # core engine trend filter
MA_TSMOM = 210         # about 10 months, the classic time-series momentum filter
BASE_LEV = 1.5         # core engine max effective leverage
RAMP_BAND = 0.10       # core ramps from 0 to full as QQQ goes from -10% to +10% vs its MA

# After combining, challenger/main.py scales the book toward TARGET_VOL with
# risk_overlay.vol_target_scaler, the scaler the champion's overlay uses, and its target_weights
# parks the rest in SHV.
TARGET_VOL = 0.16      # whole-book vol budget, annualized
# Pinned because vol_target_scaler otherwise reads the champion's config.OVERLAY_VOL_MODEL,
# so a champion estimator change would leak into the A/B.
VOL_MODEL = "trailing"
CASH = "SHV"

# The trend sleeve is benched: its budget is 0 and the book runs on three sleeves. It was benched
# after a simpler-beats-it backtest, which challenger/backtest.py can't re-run as written, because
# with trend at 0 its A and C books are the same. The code stays so a better version can be
# re-tested.
SLEEVE_BUDGETS = {"core": 0.45, "trend": 0.0, "lowvol": 0.28, "ballast": 0.27}

CORE_ASSETS = ["QQQ", "QLD", "IEF"]
TREND_ASSETS = ["SPY", "EFA", "TLT", "GLD", "DBC"]
LOWVOL_ASSETS = ["XLP", "XLU", "XLV"]
BALLAST_ASSETS = ["TLT", "GLD"]

ALL_TICKERS = sorted(set(CORE_ASSETS + TREND_ASSETS + LOWVOL_ASSETS
                         + BALLAST_ASSETS + [CASH]))


# Sleeve builders. Each returns weights summing to its budget.

def core_sleeve(px: pd.DataFrame, budget: float) -> dict[str, float]:
    """Trend-ramped leveraged tech, the validated "Gradual" engine from the strategy lab.

    Effective exposure ramps from 0 to BASE_LEV with QQQ's distance from its 200-day average,
    instead of flipping all-or-nothing. IEF is the cushion.
    """
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
    """Cross-asset time-series momentum, meant as the crisis-alpha sleeve.

    Each asset above its 10-month average gets an equal slice. The rest parks in cash.
    """
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
    """Defensive equity, equal-weight and always on. Low-vol anomaly: similar return, lower risk."""
    cols = [t for t in LOWVOL_ASSETS if t in px.columns]
    if not cols:
        return {CASH: budget}
    each = budget / len(cols)
    return {t: each for t in cols}


def ballast_sleeve(px: pd.DataFrame, budget: float) -> dict[str, float]:
    """TLT and GLD, inverse-vol weighted. Meant to hold up when stocks fall."""
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
    """Merge the sleeves into one weights dict. Sums to about 1.0, including cash."""
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
