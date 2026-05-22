"""Risk management checks — all must pass before rebalancing."""

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
    """Fail if portfolio is down >15% from its all-time high."""
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
    """Fail if 20-day realized portfolio vol exceeds MAX_PORTFOLIO_VOL."""
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
    """Fail if any single asset exceeds MAX_SINGLE_WEIGHT."""
    for ticker, w in weights.items():
        if w > MAX_SINGLE_WEIGHT + 1e-6:
            msg = f"Concentration breach: {ticker} at {w:.1%} > {MAX_SINGLE_WEIGHT:.1%}"
            _alert(msg)
            return False, msg
    return True, ""


def check_correlation(returns: pd.DataFrame) -> tuple[bool, str]:
    """Fail if average pairwise correlation of recent returns exceeds 0.85."""
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
    """Return True if any position drifted beyond REBALANCE_DRIFT_THRESHOLD."""
    all_tickers = set(current_weights) | set(target_weights)
    if not all_tickers:
        return False  # nothing to compare
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
    """Run all safety checks. Returns (all_passed, list_of_failure_messages)."""
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
