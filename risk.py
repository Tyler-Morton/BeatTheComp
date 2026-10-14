"""The safety checks that run before we're allowed to trade.

Think of this as the bouncer at the door. Every check has to pass before the bot
places a single order — if any one of them trips, we skip trading that day and
fire off an alert. Better to sit on our hands than do something dumb.
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


# ── Alert dispatch ─────────────────────────────────────────────────────────────

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


# ── Individual checks ──────────────────────────────────────────────────────────

# ── Drawdown circuit breaker (de-risk only) ───────────────────────────────────
#
# Rewritten 2026-10-13 (approved by Tyler). The old breaker measured drawdown from
# the max of daily_log.csv (OPEN snapshots: $1,118.13 vs the true broker peak
# $1,147.80) and, once tripped, blocked EVERY order — de-risking included — with no
# re-entry rule, so the book could freeze in its post-loss composition forever
# (the EXP-024 replica froze 136 sessions). Now:
#   1. Reference = high-water mark of broker-reported equity, persisted in
#      BREAKER_STATE_FILE and seeded from max(daily_log equity, broker history).
#   2. Tripped (equity < (1 - DRAWDOWN_CIRCUIT_BREAKER) * HWM) => BREAKER mode:
#      only risk-reducing trades (see derisk_targets); proceeds park in CASH_ASSET.
#   3. Leaves BREAKER when equity is back at/above the trip level, or after
#      BREAKER_RESET_SESSIONS sessions in BREAKER the HWM re-bases to current equity.
# NOTE: backtest.py / perf_report.py / EXP-024 still model the OLD rule.

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
    """Advance the breaker one session on a broker equity read and persist it.

    history_fn: zero-arg callable returning broker equity history values; called
    only when there is no state file yet (to seed the high-water mark).

    Returns {"in_breaker", "hwm", "trip_level", "drawdown", "sessions", "event", "note"}
    where event is one of: ok, tripped, derisk, recovered, reset, bad_read.
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

    # Bad-read guard: an unreadable (<= 0) or implausibly small (< 5% of HWM) read
    # is a broker glitch, not a loss (the 2026-06-08 $0 and 2026-07-07 $0.30 reads).
    # Change nothing: no trip, no release, no session counted, HWM untouched. If we
    # were already in BREAKER we stay there.
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
    """Clip the normal targets so the only trades are risk-reducing.

    Each risky position goes to min(current, target): reductions toward target and
    full exits happen, but nothing is bought or increased. Everything freed (plus
    any uninvested cash) is assigned to the cash asset. Total risky exposure can
    therefore only fall.
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
    """Block the trade if the target portfolio would be too wild to stomach.

    We estimate how bouncy this mix has been over the last 20 days and stop if
    it's above MAX_PORTFOLIO_VOL.
    """
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
    """Don't let any one position get bigger than MAX_SINGLE_WEIGHT — no all-in bets.

    The cash asset (SHV) is exempt: when the vol-target overlay de-risks, it parks a
    large slice in cash on purpose, and parking in T-bills is not a risky concentration.
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
    """Make sure we're actually diversified, not just holding the same bet five times.

    If everything we own is moving together (average correlation above 0.85),
    that "diversification" is fake and we treat it as a red flag.
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
    """Is it actually worth trading today?

    Trading costs money, so we only bother if some position has drifted from its
    target by more than REBALANCE_DRIFT_THRESHOLD. If we're already close, sit tight.
    """
    all_tickers = set(current_weights) | set(target_weights)
    if not all_tickers:
        return False  # nothing on either side to compare, so nothing to do
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
    """Run the whole checklist. Hands back (did everything pass?, list of what failed).

    The drawdown breaker is no longer part of this all-or-nothing gate: it puts the
    book in de-risk-only mode instead of blocking every order (see update_breaker).
    portfolio_value is kept in the signature for callers.
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
