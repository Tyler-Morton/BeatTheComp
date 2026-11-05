"""Safety checks that run before the bot can trade.

Every check has to pass before it places an order. If one trips, we skip trading that day and
send an alert.
"""

import logging
import os
import smtplib
from datetime import datetime
from email.mime.text import MIMEText
from pathlib import Path

import numpy as np
import pandas as pd

from config import (
    ALERTS_LOG,
    BREAKER_RESET_SESSIONS,
    BREAKER_STATE_FILE,
    DAILY_LOG,
    DRAWDOWN_CIRCUIT_BREAKER,
    IMPLAUSIBLE_VALUE_FRAC,
    MAX_PORTFOLIO_VOL,
    MAX_SINGLE_WEIGHT,
    REBALANCE_DRIFT_THRESHOLD,
)

try:
    from config import CASH_ASSET
except Exception:
    CASH_ASSET = "SHV"

logger = logging.getLogger(__name__)


def _alert(message: str) -> None:
    logger.warning("RISK ALERT: %s", message)
    with open(ALERTS_LOG, "a") as f:
        f.write(f"{datetime.now().isoformat()} | {message}\n")

    email_user = os.getenv("EMAIL_USER")
    email_pass = os.getenv("EMAIL_PASS")
    if email_user and email_pass:
        try:
            msg = MIMEText(message)
            msg["Subject"] = f"Portfolio Bot Alert: {message[:60]}"
            msg["From"] = email_user
            msg["To"] = email_user
            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
                smtp.login(email_user, email_pass)
                smtp.send_message(msg)
        except Exception as exc:
            logger.error("Email alert failed: %s", exc)


# Drawdown breaker. Drawdown is measured from the broker's high-water mark, saved in
# BREAKER_STATE_FILE. Once it trips, only risk-reducing trades go through and the
# proceeds go to CASH_ASSET. It clears when equity gets back to the trip level, or
# after BREAKER_RESET_SESSIONS sessions, when the high-water mark resets to current equity.
#
# The old version measured from daily_log.csv, which read low, and blocked every
# order with no way back in, so the book could freeze after a loss.
# backtest.py and perf_report.py still model the old rule.

_BREAKER_FIELDS = ["hwm", "in_breaker", "breaker_sessions", "last_session", "updated_at"]


def _load_breaker_state(path: Path) -> dict | None:
    try:
        if not path.exists():
            return None
        df = pd.read_csv(path)
        if df.empty:
            return None
        r = df.iloc[-1]
        hwm = float(r["hwm"])
        if not np.isfinite(hwm) or hwm <= 0:
            return None
        return {
            "hwm": hwm,
            "in_breaker": bool(int(r["in_breaker"])),
            "breaker_sessions": int(r["breaker_sessions"]),
            "last_session": "" if pd.isna(r["last_session"]) else str(r["last_session"]),
        }
    except Exception as exc:
        logger.error("Breaker state unreadable (%s) — re-seeding from history", exc)
        return None


def _save_breaker_state(state: dict, path: Path) -> None:
    """Write the state atomically: temp file in the same dir, then os.replace."""
    import tempfile
    path = Path(path)
    row = {k: state.get(k, "") for k in _BREAKER_FIELDS}
    row["in_breaker"] = int(bool(row["in_breaker"]))
    row["updated_at"] = datetime.now().isoformat(timespec="seconds")
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".breaker_state.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            pd.DataFrame([row], columns=_BREAKER_FIELDS).to_csv(f, index=False)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _seed_hwm(history_fn=None) -> float:
    """Best available peak: max(daily_log portfolio_value, broker equity history)."""
    candidates: list[float] = []
    try:
        path = Path(DAILY_LOG)
        if path.exists():
            df = pd.read_csv(path)
            if "portfolio_value" in df.columns:
                candidates.append(pd.to_numeric(df["portfolio_value"], errors="coerce").max())
    except Exception as exc:
        logger.warning("Breaker seed: daily_log unreadable (%s)", exc)
    if history_fn is not None:
        try:
            hist = pd.to_numeric(pd.Series(list(history_fn())), errors="coerce")
            candidates.append(hist[hist > 0].max())
        except Exception as exc:
            logger.warning("Breaker seed: broker equity history unavailable (%s)", exc)
    vals = [float(v) for v in candidates if v is not None and np.isfinite(v) and v > 0]
    return max(vals) if vals else 0.0


def update_breaker(
    equity: float,
    today: str | None = None,
    history_fn=None,
    state_path: Path | None = None,
) -> dict:
    """Advance the breaker one session on a broker equity read and save it.

    history_fn returns broker equity history. It's only called when there's no state file yet,
    to seed the high-water mark.

    Returns {"in_breaker", "hwm", "trip_level", "drawdown", "sessions", "event", "note"}, where
    event is one of: ok, tripped, derisk, recovered, reset, bad_read.
    """
    path = Path(state_path or BREAKER_STATE_FILE)
    today = today or str(datetime.today().date())
    state = _load_breaker_state(path)
    if state is None:
        seed = _seed_hwm(history_fn)
        state = {"hwm": seed, "in_breaker": False, "breaker_sessions": 0, "last_session": ""}
        logger.info("Breaker state seeded: high-water mark $%.2f", seed)

    def _out(event, note=""):
        hwm = state["hwm"]
        trip = (1 - DRAWDOWN_CIRCUIT_BREAKER) * hwm
        dd = (equity - hwm) / hwm if hwm > 0 and equity > 0 else float("nan")
        return {"in_breaker": state["in_breaker"], "hwm": hwm, "trip_level": trip,
                "drawdown": dd, "sessions": state["breaker_sessions"],
                "event": event, "note": note}

    # Bad-read guard. An unreadable (<= 0) or tiny (< 5% of the high-water mark) read is a broker
    # glitch, like the 2026-06-08 and 2026-07-07 reads. Change nothing: no trip, no release, no
    # session counted, high-water mark untouched. If we were already in breaker mode we stay there.
    hwm0 = state["hwm"]
    if (not np.isfinite(equity) or equity <= 0
            or (hwm0 > 0 and equity < IMPLAUSIBLE_VALUE_FRAC * hwm0)):
        logger.warning("Breaker update skipped — equity read $%.2f is unreadable or "
                       "implausible vs HWM $%.2f; treating as a bad broker read.",
                       equity, hwm0)
        return _out("bad_read")

    new_session = state["last_session"] != today
    event = "ok"
    if state["in_breaker"]:
        trip = (1 - DRAWDOWN_CIRCUIT_BREAKER) * state["hwm"]
        if equity >= trip:
            state["in_breaker"], state["breaker_sessions"] = False, 0
            event = "recovered"
            _alert(f"Drawdown breaker RELEASED: equity ${equity:,.2f} back above trip "
                   f"level ${trip:,.2f} (HWM ${state['hwm']:,.2f}) — normal trading resumes")
        elif new_session and state["breaker_sessions"] >= BREAKER_RESET_SESSIONS:
            old = state["hwm"]
            state["hwm"] = equity
            state["in_breaker"], state["breaker_sessions"] = False, 0
            event = "reset"
            _alert(f"Drawdown breaker RESET after {BREAKER_RESET_SESSIONS} sessions in "
                   f"de-risk mode: HWM re-based ${old:,.2f} -> ${equity:,.2f} — "
                   f"normal trading resumes")
        else:
            if new_session:
                state["breaker_sessions"] += 1
            event = "derisk"

    if not state["in_breaker"]:
        state["hwm"] = max(state["hwm"], equity)
        trip = (1 - DRAWDOWN_CIRCUIT_BREAKER) * state["hwm"]
        if equity < trip:
            state["in_breaker"], state["breaker_sessions"] = True, 1
            event = "tripped"

    state["last_session"] = today
    _save_breaker_state(state, path)
    out = _out(event)
    if out["in_breaker"]:
        out["note"] = (f"BREAKER de-risk only: {out['drawdown']:.1%} from HWM "
                       f"${out['hwm']:,.0f} (trip ${out['trip_level']:,.0f}), session "
                       f"{out['sessions']}/{BREAKER_RESET_SESSIONS}")
        if event == "tripped":
            _alert(f"Drawdown circuit breaker: {out['drawdown']:.1%} from HWM "
                   f"${out['hwm']:,.0f} — BREAKER mode, de-risk only (sells + "
                   f"{CASH_ASSET}; no risky buys)")
        else:
            _alert(out["note"])
    elif event in ("recovered", "reset"):
        out["note"] = f"breaker_{event}"
    return out


def derisk_targets(current_weights: dict, target_weights: dict,
                   cash_asset: str = CASH_ASSET) -> dict:
    """Clip the normal targets so the only trades reduce risk.

    Each risky position goes to min(current, target), so nothing is bought or increased and
    total risky exposure can only fall. Everything freed, plus any uninvested cash, goes to the
    cash asset.
    """
    out: dict[str, float] = {}
    for sym in set(current_weights) | set(target_weights):
        if sym == cash_asset:
            continue
        w = min(max(float(current_weights.get(sym, 0.0)), 0.0),
                max(float(target_weights.get(sym, 0.0)), 0.0))
        if w > 0:
            out[sym] = w
    out[cash_asset] = max(0.0, 1.0 - sum(out.values()))
    return out


def check_volatility(returns: pd.DataFrame, weights: dict) -> tuple[bool, str]:
    """Fail if the target mix's vol over the last 20 days is above MAX_PORTFOLIO_VOL."""
    tickers = [t for t in weights if t in returns.columns]
    if not tickers:
        return True, ""
    w = np.array([weights[t] for t in tickers])
    cov252 = returns[tickers].tail(20).cov().values * 252
    port_vol = float(np.sqrt(w @ cov252 @ w))
    if port_vol > MAX_PORTFOLIO_VOL:
        msg = f"Vol scaling: {port_vol:.1%} > limit {MAX_PORTFOLIO_VOL:.1%}"
        _alert(msg)
        return False, msg
    return True, ""


def check_concentration(weights: dict) -> tuple[bool, str]:
    """Fail if any position is bigger than MAX_SINGLE_WEIGHT.

    The cash asset (SHV) is exempt. The vol-target overlay parks a large slice there on purpose,
    and T-bills aren't a risky concentration.
    """
    for ticker, w in weights.items():
        if ticker == CASH_ASSET:
            continue
        if w > MAX_SINGLE_WEIGHT + 1e-6:
            msg = f"Concentration breach: {ticker} at {w:.1%} > {MAX_SINGLE_WEIGHT:.1%}"
            _alert(msg)
            return False, msg
    return True, ""


def check_correlation(returns: pd.DataFrame) -> tuple[bool, str]:
    """Fail if all of ASSETS is moving together (average pairwise correlation above 0.85).

    main.py passes returns for the whole universe, so this includes assets we don't hold.
    """
    if len(returns.columns) < 2:
        return True, ""
    corr = returns.tail(20).corr().values
    n = len(corr)
    mask = np.triu(np.ones((n, n), dtype=bool), k=1)
    avg_corr = float(corr[mask].mean())
    if avg_corr > 0.85:
        msg = f"Correlation spike: avg pairwise = {avg_corr:.2f} > 0.85"
        _alert(msg)
        return False, msg
    return True, ""


def should_rebalance(current_weights: dict, target_weights: dict) -> bool:
    """True if some position has drifted from target by REBALANCE_DRIFT_THRESHOLD or more.

    Trading costs money, so if we're already close we skip it.
    """
    all_tickers = set(current_weights) | set(target_weights)
    if not all_tickers:
        return False
    max_drift = max(
        abs(current_weights.get(t, 0.0) - target_weights.get(t, 0.0))
        for t in all_tickers
    )
    if max_drift < REBALANCE_DRIFT_THRESHOLD:
        logger.info("Max drift %.1f%% — below threshold, skipping.", max_drift * 100)
        return False
    return True


def run_all_checks(
    portfolio_value: float,
    returns: pd.DataFrame,
    target_weights: dict,
) -> tuple[bool, list[str]]:
    """Run every check. Returns (all passed, list of what failed).

    The drawdown breaker isn't part of this all-or-nothing gate. It puts the book in de-risk-only
    mode instead of blocking every order (see update_breaker). portfolio_value stays in the
    signature for callers.
    """
    failures: list[str] = []
    for ok, msg in [
        check_volatility(returns, target_weights),
        check_concentration(target_weights),
        check_correlation(returns),
    ]:
        if not ok:
            failures.append(msg)
    return len(failures) == 0, failures
