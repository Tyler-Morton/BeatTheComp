"""V3 paper shadow: a read-only daily logger that runs beside the champion (EXP-024, EXP-027).

Run: python shadow_v3.py. The workflow runs it after the champion with continue-on-error,
so a shadow failure can't block or change the champion.
"""

# V3 is the champion's logic with two changes, frozen in the EXP-024 spec and passed on the
# held-out 2011-2018 window in EXP-027:
# 1. Regime, strategy and optimizer only run on the first session of each month, using closes
#    through the prior month's last session. The overlay, risk checks and 2% drift rule still
#    run every day, like live.
# 2. After the overlay, total TQQQ+UPRO+SOXL+TECL target weight is capped at 30% and the excess
#    goes to SHV. Held weights can drift above the cap between trades, same as the EXP-024 engine.
#
# It's read-only on purpose and the tests enforce that. It never imports broker or an Alpaca
# trading client. It skips regime.detect_regime and risk.run_all_checks because they have side
# effects (log writes, email), so their math is redone here on the shadow's own equity. Prices come
# from prices_cache.parquet, the table the champion saved that morning, and champion equity comes
# from daily_log.csv. It only writes shadow_v3_state.json and shadow_v3_log.csv.
#
# Timing matches the EXP-024 engine and live. The run on session D decides from closes through D-1.
# Those weights earn close(D-1) to close(D), which gets booked on the next run. Cost is 5 bp per
# dollar traded, SHV legs included, and comes off that same day's return. SHV earns its actual price
# return. The shadow starts at the champion's equity on its first day, 100% in SHV like the engine,
# so day one shows a full trade-in.

from __future__ import annotations

import csv
import json
import logging
import os
import tempfile
from datetime import date, datetime
from pathlib import Path

import numpy as np
import pandas as pd

import config
from config import ASSETS, CASH_ASSET

logger = logging.getLogger("shadow_v3")

# Frozen V3 parameters from the EXP-024 spec. Don't tune these.
VARIANT = "V3"
LEV = ("TQQQ", "UPRO", "SOXL", "TECL")
CAP_3X = 0.30
COST_PER_DOLLAR = 0.0005           # 5 bp per dollar traded, the primary cost in EXP-024 and EXP-027
MIN_TARGET_WEIGHT = 0.005          # same crumb fold as main.py
STATE_VERSION = 1

BASE_DIR = Path(__file__).resolve().parent
STATE_PATH = BASE_DIR / "shadow_v3_state.json"
LOG_PATH = BASE_DIR / "shadow_v3_log.csv"
PRICE_CACHE_PATH = BASE_DIR / "prices_cache.parquet"
DAILY_LOG_PATH = Path(config.DAILY_LOG)

LOG_FIELDS = [
    "date",               # run date, the session the target is for
    "marked_through",     # last close the shadow equity is marked to (D-1)
    "regime",             # incumbent regime, decided on `decided_on`
    "strategy",           # incumbent strategy
    "decided_on",         # session the incumbent was decided
    "redecided",          # 1 if regime, strategy and optimizer ran today
    "scaler",             # vol overlay scaler, recomputed daily
    "w3x_pre_cap",        # total 3x target weight after the overlay, before the cap
    "w3x_post_cap",       # total 3x target weight after the cap and crumb fold
    "target_weights",     # JSON, final V3 target
    "held_weights",       # JSON, shadow book after today's hypothetical trade
    "traded",             # 1 if the shadow traded today
    "turnover",           # sum of |T - H| traded today, as a fraction of equity, both legs
    "blocked",            # risk-check reasons joined with ';', empty if none
    "shadow_equity",      # dollars marked through `marked_through`, before today's cost
    "champion_equity",    # champion portfolio_value logged today
    "notes",
]


# Pure functions, no I/O

def regime_from_prices(prices: pd.DataFrame) -> str:
    """Same math as regime.detect_regime, without its regime_log.csv write."""
    from regime import _flight_signal, _majority_vote, _trend_signal, _vol_signal
    spy = prices.get("SPY", None)
    tlt = prices.get("TLT", None)
    if spy is None or tlt is None:
        raise RuntimeError("price cache lacks SPY/TLT; cannot compute the regime")
    spy_returns = spy.pct_change().dropna()
    return _majority_vote([_vol_signal(spy_returns), _trend_signal(spy), _flight_signal(spy, tlt)])


def asset_returns_from_prices(prices: pd.DataFrame) -> pd.DataFrame:
    """Same as main.py: get_returns(prices), limited to ASSETS."""
    from data import get_returns
    returns = get_returns(prices)
    return returns[[c for c in ASSETS if c in returns.columns]]


def base_decision(prices: pd.DataFrame) -> tuple[str, str, dict[str, float]]:
    """Runs regime, select_strategy and optimize, same as main.py.

    SENTIMENT_ENABLED=False makes the champion's sentiment modifiers no-ops and the alpha sleeve
    is off, so the champion's base target is just the optimizer's weights.
    """
    from optimizer import optimize, select_strategy
    asset_returns = asset_returns_from_prices(prices)
    regime = regime_from_prices(prices)
    strategy = select_strategy(regime, returns=asset_returns)
    result = optimize(strategy=strategy, returns=asset_returns,
                      sentiment_modifiers={}, regime=regime)
    return regime, strategy, {t: float(w) for t, w in result["weights"].items()}


def final_target(B: dict[str, float], asset_returns: pd.DataFrame
                 ) -> tuple[float, float, float, dict[str, float]]:
    """Applies the overlay, 3x cap and crumb fold. Returns (scaler, w3x_pre_cap, w3x_post_cap, T)."""
    if config.RISK_OVERLAY_ENABLED:
        from risk_overlay import apply_overlay, vol_target_scaler
        # The ML throttle is off in the champion and isn't in V3's spec (the engine runs the
        # overlay with use_ml=False). shadow_ml only logs and never moves weights.
        T, _ = apply_overlay(dict(B), asset_returns, target_vol=config.OVERLAY_TARGET_VOL,
                             use_ml=False, shadow_ml=False, cash_asset=CASH_ASSET)
        # Same call apply_overlay makes. Its info dict only has a copy rounded to 3 places.
        s = float(np.clip(vol_target_scaler(asset_returns, B, config.OVERLAY_TARGET_VOL),
                          0.0, 1.0))
    else:
        T, s = dict(B), 1.0
    pre = sum(T.get(k, 0.0) for k in LEV)
    if pre > CAP_3X:
        f = CAP_3X / pre
        removed = 0.0
        for k in LEV:
            if k in T:
                removed += T[k] * (1 - f)
                T[k] *= f
        T[CASH_ASSET] = T.get(CASH_ASSET, 0.0) + removed
    crumbs = {t: w for t, w in T.items() if t != CASH_ASSET and 0 < w < MIN_TARGET_WEIGHT}
    if crumbs:
        T = {t: w for t, w in T.items() if t not in crumbs}
        T[CASH_ASSET] = T.get(CASH_ASSET, 0.0) + sum(crumbs.values())
    post = sum(T.get(k, 0.0) for k in LEV)
    return s, pre, post, T


def risk_gate(T: dict[str, float], asset_returns: pd.DataFrame,
              equity: float, ath: float) -> list[str]:
    """Same math as risk.run_all_checks with no side effects, on the shadow's equity and ATH.

    It also blocks on drawdown, which run_all_checks doesn't check any more. The champion's breaker
    only de-risks now, so in a drawdown the shadow holds while the champion can sell toward cash.
    """
    reasons = []
    if ath > 0 and equity / ath - 1.0 < -config.DRAWDOWN_CIRCUIT_BREAKER:
        reasons.append("drawdown")
    tick = [t for t in T if t in asset_returns.columns]
    if tick:
        w = np.array([T[t] for t in tick])
        cov = asset_returns[tick].tail(20).cov().values * 252
        if float(np.sqrt(w @ cov @ w)) > config.MAX_PORTFOLIO_VOL:
            reasons.append("vol")
    if any(t != CASH_ASSET and w > config.MAX_SINGLE_WEIGHT + 1e-6 for t, w in T.items()):
        reasons.append("concentration")
    if len(asset_returns.columns) >= 2:
        corr = asset_returns.tail(20).corr().values
        m = np.triu(np.ones(corr.shape, dtype=bool), k=1)
        if float(corr[m].mean()) > 0.85:
            reasons.append("correlation")
    return reasons


def _round(d: dict[str, float]) -> dict[str, float]:
    return {k: round(float(v), 6) for k, v in sorted(d.items()) if abs(v) > 1e-9}


def step(state: dict | None, prices: pd.DataFrame, today: date,
         champion_equity: float) -> tuple[dict, dict]:
    """Advances the shadow one session. Pure, returns (new_state, log_row).

    `prices` must only have closes through the session before `today`.
    """
    notes: list[str] = []
    prices = prices.sort_index()
    if len(prices) and prices.index[-1].date() >= today:
        raise ValueError("prices must end before `today` (decision uses closes through D−1)")
    last_close = prices.index[-1]

    # Start the shadow, or mark the held book to the newest close.
    if state is None:
        if not (champion_equity > 0):
            raise ValueError("cannot start the shadow without a champion equity reading")
        state = {
            "version": STATE_VERSION, "variant": VARIANT, "started": str(today),
            "equity": float(champion_equity), "ath": float(champion_equity),
            "held": {CASH_ASSET: 1.0}, "pending_cost": 0.0,
            "marked_through": str(last_close.date()), "incumbent": None,
            "last_run_date": None,
        }
        notes.append("shadow_start")
    else:
        state = json.loads(json.dumps(state))            # never mutate the caller's copy
        mark = pd.Timestamp(state["marked_through"])
        if mark not in prices.index:
            notes.append("mark_date_not_in_cache")
        R = prices.pct_change(fill_method=None)
        new_days = R.index[R.index > mark]
        H = state["held"]
        E = state["equity"]
        nan_held = 0
        for t in new_days:
            r = R.loc[t]
            g = 0.0
            newH = {}
            for k, w in H.items():
                rk = r.get(k, np.nan)
                if not np.isfinite(rk):
                    nan_held += 1 if w > 1e-12 else 0
                    rk = 0.0
                g += w * rk
                newH[k] = w * (1 + rk)
            E *= 1 + g - state["pending_cost"]
            state["pending_cost"] = 0.0
            H = {k: v / (1 + g) for k, v in newH.items()}
            state["ath"] = max(state["ath"], E)
        if nan_held:
            notes.append(f"nan_return_on_held={nan_held}")
        if len(new_days) == 0:
            notes.append("no_new_close")
        state["held"], state["equity"] = H, E
        state["marked_through"] = str(last_close.date())

    # Re-decide on the first session of each month, or on the first run.
    asset_returns = asset_returns_from_prices(prices)
    month = today.strftime("%Y-%m")
    redecided = False
    inc = state.get("incumbent")
    if inc is None or inc.get("month") != month:
        try:
            regime, strategy, B = base_decision(prices)
            state["incumbent"] = inc = {"regime": regime, "strategy": strategy, "B": B,
                                        "decided_on": str(today), "month": month}
            redecided = True
        except Exception as exc:          # live would crash; the shadow holds and says so
            logger.exception("V3 re-decision failed")
            notes.append(f"decision_error={type(exc).__name__}")

    # Daily overlay, cap, risk checks and 2% drift rule.
    s = pre = post = None
    T: dict[str, float] = {}
    blocked: list[str] = []
    traded, turnover = False, 0.0
    H = state["held"]
    if inc is not None:
        s, pre, post, T = final_target(inc["B"], asset_returns)
        blocked = risk_gate(T, asset_returns, state["equity"], state["ath"])
        if not blocked:
            keys = set(H) | set(T)
            drift = max(abs(H.get(k, 0.0) - T.get(k, 0.0)) for k in keys)
            if drift >= config.REBALANCE_DRIFT_THRESHOLD:
                turnover = float(sum(abs(T.get(k, 0.0) - H.get(k, 0.0)) for k in keys))
                traded = True
                state["held"] = {k: float(v) for k, v in T.items() if v != 0.0}
                state["pending_cost"] = COST_PER_DOLLAR * turnover
    else:
        notes.append("no_target_hold")

    if config.SENTIMENT_ENABLED or config.ALPHA_SLEEVE_ENABLED or config.OVERLAY_ML_ENABLED:
        # V3 was specified and tested without these. If the champion turns one on, the
        # comparison stops being like for like, so flag it on every row.
        notes.append("champion_config_beyond_V3_spec")

    state["last_run_date"] = str(today)
    row = {
        "date": str(today),
        "marked_through": state["marked_through"],
        "regime": inc["regime"] if inc else "",
        "strategy": inc["strategy"] if inc else "",
        "decided_on": inc["decided_on"] if inc else "",
        "redecided": int(redecided),
        "scaler": "" if s is None else round(s, 6),
        "w3x_pre_cap": "" if pre is None else round(pre, 6),
        "w3x_post_cap": "" if post is None else round(post, 6),
        "target_weights": json.dumps(_round(T)),
        "held_weights": json.dumps(_round(state["held"])),
        "traded": int(traded),
        "turnover": round(turnover, 6),
        "blocked": ";".join(blocked),
        "shadow_equity": round(state["equity"], 4),
        "champion_equity": "" if not (champion_equity == champion_equity) else round(champion_equity, 4),
        "notes": ";".join(notes),
    }
    return state, row


# I/O

def champion_equity_for(today: date, daily_log: Path) -> float | None:
    """Champion's portfolio_value from today's daily_log row.

    None if there's no row. NaN if the row exists but the value was blanked as implausible.
    """
    if not Path(daily_log).exists():
        return None
    df = pd.read_csv(daily_log)
    if df.empty or "date" not in df.columns:
        return None
    rows = df[df["date"].astype(str).str[:10] == str(today)]
    if rows.empty:
        return None
    v = pd.to_numeric(rows.iloc[-1].get("portfolio_value"), errors="coerce")
    return float(v) if pd.notna(v) else float("nan")


def load_state(path: Path) -> dict | None:
    path = Path(path)
    if not path.exists():
        return None
    with open(path) as f:
        state = json.load(f)
    if state.get("version") != STATE_VERSION or state.get("variant") != VARIANT:
        raise RuntimeError(f"unexpected shadow state format in {path}")
    return state


def save_state_atomic(state: dict, path: Path) -> None:
    path = Path(path)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(state, f, indent=1, sort_keys=True)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def _log_has_date(path: Path, today: date) -> bool:
    if not Path(path).exists():
        return False
    with open(path, newline="") as f:
        rows = list(csv.DictReader(f))
    return bool(rows) and rows[-1].get("date") == str(today)


def append_row(row: dict, path: Path) -> None:
    path = Path(path)
    new = not path.exists()
    with open(path, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=LOG_FIELDS)
        if new:
            w.writeheader()
        w.writerow(row)


def run(today: date | None = None, *, state_path: Path = STATE_PATH, log_path: Path = LOG_PATH,
        price_cache: Path = PRICE_CACHE_PATH, daily_log: Path = DAILY_LOG_PATH) -> str:
    """Runs one shadow session and returns a short status string. Never trades."""
    today = today or datetime.today().date()
    state = load_state(state_path)
    if state is not None and state.get("last_run_date") == str(today):
        logger.info("Shadow V3 already ran for %s — nothing to do.", today)
        return "already_ran"

    champ = champion_equity_for(today, daily_log)
    if champ is None:
        # No champion row today means the market was closed, a duplicate run exited early, or
        # the champion crashed before logging. In all of those the price cache isn't today's.
        logger.info("No champion daily_log row for %s — shadow skipped.", today)
        return "no_champion_row"
    if state is None and not (champ > 0):
        logger.warning("Champion equity unreadable today — shadow start deferred.")
        return "start_deferred"

    prices = pd.read_parquet(price_cache)
    prices.index = pd.to_datetime(prices.index)
    prices = prices[prices.index.date < today]          # closes through D-1 only
    if len(prices) < 2:
        raise RuntimeError("price cache has no usable history before today")

    new_state, row = step(state, prices, today, champ)
    if not _log_has_date(log_path, today):
        append_row(row, log_path)
    save_state_atomic(new_state, state_path)
    logger.info("Shadow V3 %s: regime=%s strategy=%s scaler=%s 3x %s→%s traded=%s "
                "turnover=%.3f equity=%.2f (champion %s)%s",
                row["date"], row["regime"], row["strategy"], row["scaler"],
                row["w3x_pre_cap"], row["w3x_post_cap"], row["traded"], row["turnover"],
                row["shadow_equity"], row["champion_equity"],
                f" [{row['notes']}]" if row["notes"] else "")
    return "logged"


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-8s  %(message)s",
                        datefmt="%H:%M:%S")
    print(run())
