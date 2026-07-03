"""The daily run, start to finish.

This is the conductor. It calls every other module in order — pull prices, find
trending stocks, read sentiment, figure out the market, build the target portfolio,
run the safety checks, and finally place the trades. If you want to know what the
bot does each morning, read this file top to bottom.
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

from config import ASSETS, DAILY_LOG, TRENDING_DISCOVERY_ENABLED, WATCHLIST
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
    write_header = not path.exists()
    with open(path, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(row.keys()))
        if write_header:
            w.writeheader()
        w.writerow(row)


def _already_ran_today() -> bool:
    """Have we already done a real run today?

    We schedule the bot a few times each morning in case one firing misses, so we
    need a guard against doing the work twice. This just peeks at the bottom of
    daily_log.csv: if the last row is dated today, we've already run and bail out.
    """
    path = Path(DAILY_LOG)
    if not path.exists():
        return False
    try:
        import pandas as pd
        df = pd.read_csv(path)
        if df.empty: return False
        today_str = str(datetime.today().date())
        # The date might be stored as 'YYYY-MM-DD' or with a time tacked on, so
        # just compare the first 10 characters.
        recent = df.iloc[-1]
        last_date = str(recent.get("date", ""))[:10]
        return last_date == today_str
    except Exception:
        return False


def main() -> None:
    logger.info("═" * 60)
    logger.info("Portfolio Bot — %s", datetime.now().strftime("%Y-%m-%d %H:%M"))
    logger.info("═" * 60)

    # ── 0. Don't run twice — we're scheduled multiple times as a safety net ───
    if _already_ran_today():
        logger.info("Already ran today — exiting (duplicate cron firing).")
        sys.exit(0)

    # ── 1. Is the market even open? If not, there's nothing to do ─────────────
    from broker import is_market_open
    if not is_market_open():
        logger.info("Market is closed — exiting cleanly.")
        sys.exit(0)

    # ── 2. Grab recent prices for everything we care about ────────────────────
    logger.info("Fetching price data…")
    all_tickers = list(dict.fromkeys(ASSETS + ["SPY", "TLT"]))
    prices = fetch_prices(all_tickers, lookback_days=252)
    returns = get_returns(prices)
    asset_returns = returns[[c for c in ASSETS if c in returns.columns]]

    # Stash the prices on disk so the dashboard can read them without hammering yfinance.
    from data import save_price_cache
    save_price_cache(prices)

    # ── 3a. Ask Claude what's trending today ──────────────────────────────────
    extra_tickers: list[str] = []
    if TRENDING_DISCOVERY_ENABLED:
        from trending import discover_trending
        trending = discover_trending()
        extra_tickers = [t["ticker"] for t in trending]

    # Glue the always-on watchlist together with today's trending names, no dupes.
    full_watchlist = list(dict.fromkeys(WATCHLIST + extra_tickers))
    logger.info("Total watchlist for today: %d stocks (%d static + %d trending)",
                len(full_watchlist), len(WATCHLIST), len(extra_tickers))

    # ── 3b. Run sentiment and the watchlist scan at the same time ─────────────
    # These two don't depend on each other and both wait on slow API calls, so we
    # fire them off together instead of one-then-the-other.
    logger.info("Starting sentiment analysis and watchlist scan (parallel)…")
    from sentiment import run_sentiment_analysis
    from watchlist import scan_watchlist

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        sentiment_future = pool.submit(run_sentiment_analysis, [a for a in ASSETS if a in prices.columns])
        watchlist_future = pool.submit(scan_watchlist, full_watchlist)
        sentiment_results = sentiment_future.result()
        watchlist_data = watchlist_future.result()   # the full scan, which the alpha sleeve picks from

    # ── 4. Read the room — what kind of market are we in? ─────────────────────
    logger.info("Detecting market regime…")
    spy_prices = prices.get("SPY", None)
    tlt_prices = prices.get("TLT", None)
    regime = detect_regime(spy_prices, tlt_prices)

    # ── 5. Pick the strategy for today, then build the target portfolio ───────
    # The strategy is chosen from the market regime plus how each approach has
    # actually been performing lately; then the optimizer turns that into weights.
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

    # ── 5b. Mix in the alpha sleeve (our best individual-stock picks) ─────────
    # This shrinks the ETF weights a bit and uses that room for the stock bets.
    from alpha_sleeve import merge_with_etf_weights
    target_weights = merge_with_etf_weights(etf_target_weights, watchlist_data)

    # ── 5c. Risk overlay — vol-target the whole book, park the rest in cash ────
    # Scales exposure toward a target volatility so the 3x book can't run wild into
    # a crash. Leaves the underlying strategy untouched; just caps the risk.
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
        # Shadow record for the crash model: what it WOULD have done today (not applied).
        if overlay_info.get("crash_prob") is not None and overlay_info.get("ml_shadow_mult") is not None:
            ml_note = (f"ml_shadow p={overlay_info['crash_prob']:.2f} "
                       f"would_mult={overlay_info['ml_shadow_mult']:.2f}")
            logger.info("ML crash-throttle (SHADOW, not applied): %s", ml_note)

    logger.info("Final target weights:")
    for ticker, w in sorted(target_weights.items(), key=lambda x: -x[1]):
        if w > 0.001:
            logger.info("  %-6s  %.1f%%", ticker, w * 100)

    # ── 6. Safety checks — last chance to call the whole thing off ────────────
    from broker import get_portfolio_value, get_current_positions
    portfolio_value = get_portfolio_value()
    if portfolio_value <= 0:
        # A failed API call returns 0.0 — never log or trade against a bogus value.
        # (This is what wrote the phantom $0 equity row on 2026-06-08.)
        logger.error("Portfolio value unavailable (got %.2f) — aborting run, logging nothing",
                     portfolio_value)
        return
    current_weights = get_current_positions()

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
            "final_weights": json.dumps(target_weights),   # log what we wanted, even though we didn't trade — the dashboard shows it
            "notes": "; ".join(failures + ([ml_note] if ml_note else [])),
        })
        logger.warning("Pipeline aborted — risk checks failed.")
        return

    # ── 7. Is it even worth trading? Skip if we're already close enough ───────
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
            "notes": "; ".join(["no_rebalance"] + ([ml_note] if ml_note else [])
                               + (["cash_swept"] if swept else [])),
        })
        return

    # ── 8. Actually place the trades ──────────────────────────────────────────
    logger.info("Rebalancing…")
    from broker import rebalance, sweep_idle_cash
    orders = rebalance(target_weights)
    logger.info("%d orders placed.", len(orders))
    if orders:
        import time as _time
        _time.sleep(10)                    # let fills settle before measuring idle cash
    swept = sweep_idle_cash()              # whatever's still uninvested goes to bills
    if swept:
        orders.append(swept)

    # ── 9. Write down what happened so we can look back on it later ───────────
    _log_daily({
        "date": datetime.today().date(),
        "strategy": strategy,
        "regime": regime,
        "portfolio_value": portfolio_value,
        "sharpe": result["sharpe_ratio"],
        "expected_return": result["expected_annual_return"],
        "annual_vol": result["annual_volatility"],
        "orders_placed": len(orders),
        "final_weights": json.dumps(target_weights),
        "notes": "; ".join(([ml_note] if ml_note else [])
                           + (["cash_swept"] if swept else [])),
    })

    logger.info("Pipeline complete.")


if __name__ == "__main__":
    main()
