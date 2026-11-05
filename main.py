"""The daily run, start to finish.

Pulls prices, works out the market regime, builds the target portfolio, runs the safety checks and
places the trades. Trending discovery and Claude sentiment are wired in, but both are off in config.
"""

import concurrent.futures
import csv
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from config import ASSETS, CASH_ASSET, DAILY_LOG, TRENDING_DISCOVERY_ENABLED, WATCHLIST
from data import fetch_prices, get_returns
from optimizer import optimize, select_strategy
from regime import detect_regime
from risk import run_all_checks, should_rebalance

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def _log_daily(row: dict) -> None:
    path = Path(DAILY_LOG)
    # Don't save a portfolio value the account can't physically have. Two bad broker reads got
    # into this file, near zero on 2026-06-08 and 2026-07-07, and they poison every return
    # series computed from the column (a -99.97% day followed by a +303,000% one). risk.py
    # already refuses to act on a read like this, and this stops us recording it. Write a
    # blank instead of zero: we don't know the value, and a blank reads as NaN downstream.
    try:
        pv = float(row.get("portfolio_value"))
    except (TypeError, ValueError):
        pv = float("nan")
    if not (pv >= 50):                      # also catches NaN

        logger.warning("Refusing to log implausible portfolio_value %r for %s — "
                       "recording blank instead of a fake observation.",
                       row.get("portfolio_value"), row.get("date"))
        row = dict(row, portfolio_value="")
    write_header = not path.exists()
    with open(path, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(row.keys()))
        if write_header:
            w.writeheader()
        w.writerow(row)
    logger.info("Logged daily row for %s -> %s (now %d bytes)",
                row.get("date"), path.resolve(), path.stat().st_size)


def _already_ran_today() -> bool:
    """True if the last row of daily_log.csv is dated today.

    The bot is scheduled a few times each morning in case one firing misses.
    """
    path = Path(DAILY_LOG)
    if not path.exists():
        return False
    try:
        import pandas as pd
        df = pd.read_csv(path)
        if df.empty: return False
        today_str = str(datetime.today().date())
        # The date might have a time tacked on, so only compare the first 10 characters.
        recent = df.iloc[-1]
        last_date = str(recent.get("date", ""))[:10]
        return last_date == today_str
    except Exception:
        return False


def main() -> int | None:
    logger.info("═" * 60)
    logger.info("Portfolio Bot — %s", datetime.now().strftime("%Y-%m-%d %H:%M"))
    logger.info("═" * 60)

    if _already_ran_today():
        logger.info("Already ran today — exiting (duplicate cron firing).")
        sys.exit(0)

    from broker import is_market_open
    if not is_market_open():
        logger.info("Market is closed — exiting cleanly.")
        sys.exit(0)

    logger.info("Fetching price data…")
    all_tickers = list(dict.fromkeys(ASSETS + ["SPY", "TLT"]))
    prices = fetch_prices(all_tickers, lookback_days=252)
    returns = get_returns(prices)
    asset_returns = returns[[c for c in ASSETS if c in returns.columns]]

    # Save the prices so the dashboard can read them without hammering yfinance.
    from data import save_price_cache
    save_price_cache(prices)

    # Ask Claude what's trending today, if discovery is on. It's off in config.
    extra_tickers: list[str] = []
    if TRENDING_DISCOVERY_ENABLED:
        from trending import discover_trending
        trending = discover_trending()
        extra_tickers = [t["ticker"] for t in trending]

    # Always-on watchlist plus any trending names, no dupes.
    full_watchlist = list(dict.fromkeys(WATCHLIST + extra_tickers))
    logger.info("Total watchlist for today: %d stocks (%d static + %d trending)",
                len(full_watchlist), len(WATCHLIST), len(extra_tickers))

    # Sentiment and the watchlist scan don't depend on each other and both can wait on slow API
    # calls, so run them together.
    logger.info("Starting sentiment analysis and watchlist scan (parallel)…")
    from sentiment import run_sentiment_analysis
    from watchlist import scan_watchlist

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        sentiment_future = pool.submit(run_sentiment_analysis, [a for a in ASSETS if a in prices.columns])
        watchlist_future = pool.submit(scan_watchlist, full_watchlist)
        sentiment_results = sentiment_future.result()
        watchlist_data = watchlist_future.result()   # the full scan, which the alpha sleeve picks from

    logger.info("Detecting market regime…")
    spy_prices = prices.get("SPY", None)
    tlt_prices = prices.get("TLT", None)
    regime = detect_regime(spy_prices, tlt_prices)

    # The strategy comes from the market regime plus how each one has performed lately.
    # The optimizer then turns it into weights.
    strategy = select_strategy(regime, returns=asset_returns)
    logger.info("Running optimizer: %s (regime=%s)…", strategy, regime)
    result = optimize(
        strategy=strategy,
        returns=asset_returns,
        sentiment_modifiers=sentiment_results,
        regime=regime,
    )
    etf_target_weights: dict[str, float] = result["weights"]
    logger.info(
        "Optimizer result — Sharpe: %.2f  Vol: %.1f%%  Ret: %.1f%%",
        result["sharpe_ratio"], result["annual_volatility"] * 100, result["expected_annual_return"] * 100,
    )

    # Alpha sleeve. It's off in config, so this hands back the ETF weights unchanged.
    from alpha_sleeve import merge_with_etf_weights
    target_weights = merge_with_etf_weights(etf_target_weights, watchlist_data)

    # Risk overlay: scale exposure toward a target vol and park the rest in cash. The underlying
    # strategy stays the same.
    from config import (RISK_OVERLAY_ENABLED, OVERLAY_TARGET_VOL,
                        OVERLAY_ML_ENABLED, OVERLAY_ML_SHADOW, CASH_ASSET)
    ml_note = ""
    if RISK_OVERLAY_ENABLED:
        from risk_overlay import apply_overlay
        target_weights, overlay_info = apply_overlay(
            target_weights, asset_returns,
            target_vol=OVERLAY_TARGET_VOL, use_ml=OVERLAY_ML_ENABLED,
            shadow_ml=OVERLAY_ML_SHADOW and not OVERLAY_ML_ENABLED,
            cash_asset=CASH_ASSET,
        )
        logger.info("Risk overlay: est_vol=%.0f%% → scaler=%.2f (vol=%.2f, ml=%.2f), "
                    "parked %.0f%% in %s",
                    overlay_info["est_portfolio_vol"] * 100, overlay_info["combined_scaler"],
                    overlay_info["vol_scaler"], overlay_info["ml_scaler"],
                    overlay_info["cash_parked"] * 100, CASH_ASSET)
        # Shadow record for the crash model: what it would have done today. Not applied.
        if overlay_info.get("crash_prob") is not None and overlay_info.get("ml_shadow_mult") is not None:
            ml_note = (f"ml_shadow p={overlay_info['crash_prob']:.2f} "
                       f"would_mult={overlay_info['ml_shadow_mult']:.2f}")
            logger.info("ML crash-throttle (SHADOW, not applied): %s", ml_note)

    # No targets under 0.5%. HRP_MOMENTUM leaves 0.2-0.3% crumbs in names it's rotating out of.
    # On a small book that's a few dollars, which is just a future dust lot and an extra order.
    # Fold them into the cash asset, the same MIN_WEIGHT rule the challenger uses.
    MIN_TARGET_WEIGHT = 0.005
    crumbs = {t: w for t, w in target_weights.items()
              if t != CASH_ASSET and 0 < w < MIN_TARGET_WEIGHT}
    if crumbs:
        target_weights = {t: w for t, w in target_weights.items() if t not in crumbs}
        target_weights[CASH_ASSET] = target_weights.get(CASH_ASSET, 0.0) + sum(crumbs.values())
        logger.info("Folded %d sub-%.1f%% targets into %s: %s", len(crumbs),
                    MIN_TARGET_WEIGHT * 100, CASH_ASSET, sorted(crumbs))

    logger.info("Final target weights:")
    for ticker, w in sorted(target_weights.items(), key=lambda x: -x[1]):
        if w > 0.001:
            logger.info("  %-6s  %.1f%%", ticker, w * 100)

    # Safety checks
    from broker import get_portfolio_value, get_current_positions
    portfolio_value = get_portfolio_value()
    if portfolio_value <= 0:
        # A failed API call returns 0.0, so never log or trade against it. This is what wrote
        # the phantom $0 equity row on 2026-06-08.
        logger.error("Portfolio value unavailable (got %.2f) — aborting run, logging nothing",
                     portfolio_value)
        sys.exit(2)
    current_weights = get_current_positions()

    # Drawdown breaker: update the saved broker-equity high-water mark. When tripped, the book
    # goes de-risk only (sells, exits and SHV) instead of freezing.
    from risk import update_breaker, derisk_targets
    from broker import get_account_history
    breaker = update_breaker(
        portfolio_value, today=str(datetime.today().date()),
        history_fn=lambda: get_account_history(365)["equity"],
    )
    breaker_notes = [breaker["note"]] if breaker["note"] else []

    all_passed, failures = run_all_checks(portfolio_value, asset_returns, target_weights)
    if not all_passed:
        for msg in failures:
            logger.error("RISK BLOCK: %s", msg)
        _log_daily({
            "date": datetime.today().date(),
            "strategy": strategy,
            "regime": regime,
            "portfolio_value": portfolio_value,
            "sharpe": result["sharpe_ratio"],
            "expected_return": result["expected_annual_return"],
            "annual_vol": result["annual_volatility"],
            "orders_placed": 0,
            "final_weights": json.dumps(target_weights),   # no trade, but the dashboard shows it
            "notes": "; ".join(failures + breaker_notes + ([ml_note] if ml_note else [])),
        })
        logger.warning("Pipeline aborted — risk checks failed.")
        # Fail the run so the block shows up as a failed GitHub Actions run. risk._alert only emails
        # when EMAIL_USER and EMAIL_PASS are set. The log-commit step runs `if: always()`.
        sys.exit(2)

    # Breaker mode: only risk-reducing trades
    buy_only = None
    if breaker["in_breaker"] and not current_weights:
        # Positions unreadable, or an all-cash book: min(current, target) would mean "sell
        # everything". Don't act on a blind read. Only the idle-cash sweep runs.
        logger.warning("BREAKER mode but positions unreadable/empty — no rebalance today.")
        target_weights = {}
    elif breaker["in_breaker"]:
        target_weights = derisk_targets(current_weights, target_weights, CASH_ASSET)
        buy_only = {CASH_ASSET}
        logger.warning("BREAKER (de-risk only) mode — %s. Sells toward target allowed, "
                       "proceeds to %s; risky buys blocked.", breaker["note"], CASH_ASSET)
        for ticker, w in sorted(target_weights.items(), key=lambda x: -x[1]):
            if w > 0.001:
                logger.warning("  de-risk target %-6s  %.1f%%", ticker, w * 100)
    # Breaker days still fail the Action (exit 2) after trading, so they show up as failed runs.
    # The log-commit step runs `if: always()`.
    exit_code = 2 if breaker["in_breaker"] else None

    if not should_rebalance(current_weights, target_weights):
        logger.info("No rebalance needed — drift below threshold.")
        from broker import sweep_idle_cash
        swept = sweep_idle_cash()          # even on no-trade days, idle cash goes to bills
        _log_daily({
            "date": datetime.today().date(),
            "strategy": strategy,
            "regime": regime,
            "portfolio_value": portfolio_value,
            "sharpe": result["sharpe_ratio"],
            "expected_return": result["expected_annual_return"],
            "annual_vol": result["annual_volatility"],
            "orders_placed": 1 if swept else 0,
            "final_weights": json.dumps(current_weights),
            "notes": "; ".join(["no_rebalance"] + breaker_notes + ([ml_note] if ml_note else [])
                               + (["cash_swept"] if swept else [])),
        })
        return exit_code

    logger.info("Rebalancing…")
    from broker import rebalance, sweep_idle_cash
    orders = rebalance(target_weights, buy_only=buy_only)
    logger.info("%d orders placed.", len(orders))
    if orders:
        import time as _time
        _time.sleep(10)                    # let fills settle before measuring idle cash
    swept = sweep_idle_cash()
    if swept:
        orders.append(swept)

    # Log positions read about 10 seconds after the orders (15 if cash got swept). Buys still
    # working by then don't show, so this can read below what ends up filled. Logging the target
    # instead claimed a fully invested book that didn't exist when buying power ran short.
    if swept:
        import time as _time
        _time.sleep(5)
    held_weights = get_current_positions() or target_weights
    shortfall = sum(max(0.0, w - held_weights.get(t, 0.0))
                    for t, w in target_weights.items() if t != CASH_ASSET)
    _log_daily({
        "date": datetime.today().date(),
        "strategy": strategy,
        "regime": regime,
        "portfolio_value": portfolio_value,
        "sharpe": result["sharpe_ratio"],
        "expected_return": result["expected_annual_return"],
        "annual_vol": result["annual_volatility"],
        "orders_placed": len(orders),
        "final_weights": json.dumps(held_weights),
        "notes": "; ".join(breaker_notes + ([ml_note] if ml_note else [])
                           + (["cash_swept"] if swept else [])
                           + ([f"unfilled={shortfall:.1%}"] if shortfall > 0.02 else [])),
    })

    logger.info("Pipeline complete.")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
