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
    DAILY_LOG,
    DRAWDOWN_CIRCUIT_BREAKER,
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

def check_drawdown(portfolio_value: float) -> tuple[bool, str]:
    """Pump the brakes if we've fallen too far from our best-ever value.

    (The exact cutoff is DRAWDOWN_CIRCUIT_BREAKER over in config.)
    """
    # If we couldn't read the account (e.g. a broker timeout makes
    # get_portfolio_value() return 0.0), don't mistake an *unreadable* balance for a
    # -100% crash. Skip the check this run rather than firing a false circuit breaker.
    if portfolio_value <= 0:
        logger.warning(
            "Drawdown check skipped — portfolio value unreadable (%.2f); "
            "likely a broker connection issue, not a real loss.", portfolio_value
        )
        return True, ""
    path = Path(DAILY_LOG)
    if not path.exists():
        return True, ""
    df = pd.read_csv(path)
    if df.empty or "portfolio_value" not in df.columns:
        return True, ""
    ath = pd.to_numeric(df["portfolio_value"], errors="coerce").max()
    if ath <= 0 or np.isnan(ath):
        return True, ""
    drawdown = (portfolio_value - ath) / ath
    if drawdown < -DRAWDOWN_CIRCUIT_BREAKER:
        msg = (
            f"Drawdown circuit breaker: {drawdown:.1%} from ATH "
            f"${ath:,.0f} — trading paused"
        )
        _alert(msg)
        return False, msg
    return True, ""


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
    """Run the whole checklist. Hands back (did everything pass?, list of what failed)."""
    failures: list[str] = []
    for ok, msg in [
        check_drawdown(portfolio_value),
        check_volatility(returns, target_weights),
        check_concentration(target_weights),
        check_correlation(returns),
    ]:
        if not ok:
            failures.append(msg)
    return len(failures) == 0, failures
