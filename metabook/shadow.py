"""Meta-book SHADOW allocator — measurement + intended ERC weights. TRADES NOTHING.

Daily(ish) run:
  1. Pull all three sleeves' live equity curves (champion / challenger / volbot accounts).
  2. Per sleeve: realized vol, Sharpe, max drawdown; pairwise correlations.
  3. Compute the ERC (equal-risk-contribution) weights the allocator WOULD set,
     bounded [10%, 70%] per sleeve (validated in research/metabook_backtest.py:
     ERC beat equal-weight 0.82 vs 0.65 Sharpe with smaller drawdown).
  4. Append everything to metabook/shadow_log.csv — the live shadow record.

This is Layer 1+2 of research/metabook_spec.md. It only WRITES A LOG. The dials
(each sleeve's risk knob) stay untouched until the shadow record proves value.
"""
import os
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import requests
from dotenv import load_dotenv
from scipy.optimize import minimize

BASE = Path(__file__).parent
load_dotenv(BASE.parent / ".env")

TRADING_DAYS = 252
RF_D = 0.045 / TRADING_DAYS
W_LO, W_HI = 0.10, 0.70
COV_WIN, MIN_ROWS = 90, 20
LOG = BASE / "shadow_log.csv"

ACCOUNTS = {
    "CHAMP": ("ALPACA_API_KEY", "ALPACA_SECRET_KEY"),
    "CHALL": ("CHALLENGER_ALPACA_API_KEY", "CHALLENGER_ALPACA_SECRET_KEY"),
    "VOLBOT": ("VOLBOT_ALPACA_API_KEY", "VOLBOT_ALPACA_SECRET_KEY"),
}


def equity_curve(key_env, sec_env) -> pd.Series:
    h = {"APCA-API-KEY-ID": os.getenv(key_env), "APCA-API-SECRET-KEY": os.getenv(sec_env)}
    r = requests.get("https://paper-api.alpaca.markets/v2/account/portfolio/history",
                     headers=h, params={"period": "1A", "timeframe": "1D"}, timeout=30).json()
    s = pd.Series(r["equity"], index=pd.to_datetime(r["timestamp"], unit="s")).astype(float)
    s.index = s.index.normalize()
    return s[s > 0].dropna()


def erc_weights(cov: np.ndarray) -> np.ndarray:
    n = cov.shape[0]

    def obj(w):
        pv = float(w @ cov @ w)
        if pv <= 0:
            return 1e9
        rc = w * (cov @ w) / pv
        return float(((rc[:, None] - rc[None, :]) ** 2).sum())

    res = minimize(obj, np.full(n, 1 / n), method="SLSQP", bounds=[(W_LO, W_HI)] * n,
                   constraints=[{"type": "eq", "fun": lambda w: w.sum() - 1}],
                   options={"maxiter": 500, "ftol": 1e-12})
    w = np.clip(res.x if res.success else np.full(n, 1 / n), W_LO, W_HI)
    return w / w.sum()


def stats(r: pd.Series) -> dict:
    r = r.dropna()
    if len(r) < 5 or r.std() == 0:
        return dict(vol=np.nan, sharpe=np.nan, maxdd=np.nan)
    eq = (1 + r).cumprod()
    return dict(vol=r.std() * np.sqrt(TRADING_DAYS),
                sharpe=(r.mean() - RF_D) / r.std() * np.sqrt(TRADING_DAYS),
                maxdd=float((eq / eq.cummax() - 1).min()))


def main():
    rets, eqs = {}, {}
    for name, (k, s) in ACCOUNTS.items():
        eq = equity_curve(k, s)
        eqs[name] = float(eq.iloc[-1])
        rets[name] = eq.pct_change().dropna().rename(name)
    R = pd.concat(rets.values(), axis=1).dropna()

    names = list(ACCOUNTS)
    row = {"date": str(date.today()), "obs_days": len(R)}
    for n in names:
        st = stats(rets[n])
        row.update({f"{n}_equity": eqs[n], f"{n}_vol": round(st["vol"], 4) if st["vol"] == st["vol"] else None,
                    f"{n}_sharpe": round(st["sharpe"], 2) if st["sharpe"] == st["sharpe"] else None})
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            c = R[a].corr(R[b]) if len(R) >= 10 else np.nan
            row[f"corr_{a}_{b}"] = round(c, 2) if c == c else None

    if len(R) >= MIN_ROWS:
        w = erc_weights(R.tail(COV_WIN).cov().values * TRADING_DAYS)
        note = "ERC"
    else:
        w = np.full(len(names), 1 / len(names))
        note = f"equal-weight fallback (only {len(R)} common days < {MIN_ROWS})"
    for n, wi in zip(names, w):
        row[f"w_{n}"] = round(float(wi), 3)
    row["note"] = note

    pd.DataFrame([row]).to_csv(LOG, mode="a", header=not LOG.exists(), index=False)
    print(f"{row['date']}  shadow weights ({note}): " +
          " ".join(f"{n}={row[f'w_{n}']:.0%}" for n in names) +
          f" | common days {len(R)}")
    for n in names:
        print(f"  {n:7} eq ${eqs[n]:>10,.0f}  vol {row.get(f'{n}_vol')}  sharpe {row.get(f'{n}_sharpe')}")
    corr_bits = [f"{a}/{b} {row[f'corr_{a}_{b}']}" for i, a in enumerate(names) for b in names[i+1:]]
    print("  corr: " + " | ".join(corr_bits))


if __name__ == "__main__":
    main()
