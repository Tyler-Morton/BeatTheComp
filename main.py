"""Daily execution pipeline — orchestrates all modules."""

import concurrent.futures
import csv
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from config import ASSETS, DAILY_LOG
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


def main() -> None:
    logger.info("═" * 60)
    logger.info("Portfolio Bot — %s", datetime.now().strftime("%Y-%m-%d %H:%M"))
    logger.info("═" * 60)

    # ── 1. Market open check ───────────────────────────────────────────────────
    from broker import is_market_open
    if not is_market_open():
        logger.info("Market is closed — exiting cleanly.")
        sys.exit(0)

    # ── 2. Fetch price data ────────────────────────────────────────────────────
    logger.info("Fetching price data…")
    all_tickers = list(dict.fromkeys(ASSETS + ["SPY", "TLT"]))
    prices = fetch_prices(all_tickers, lookback_days=252)
    returns = get_returns(prices)
    asset_returns = returns[[c for c in ASSETS if c in returns.columns]]

    # ── 3. Sentiment + watchlist in parallel ───────────────────────────────────
    logger.info("Starting sentiment analysis and watchlist scan (parallel)…")
    from sentiment import run_sentiment_analysis
    from watchlist import scan_watchlist

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        sentiment_future = pool.submit(run_sentiment_analysis, [a for a in ASSETS if a in prices.columns])
        watchlist_future = pool.submit(scan_watchlist)
        sentiment_results = sentiment_future.result()
        watchlist_future.result()

    # ── 4. Detect market regime ────────────────────────────────────────────────
    logger.info("Detecting market regime…")
    spy_prices = prices.get("SPY", None)
    tlt_prices = prices.get("TLT", None)
    regime = detect_regime(spy_prices, tlt_prices)

    # ── 5. Auto-select strategy (regime + adaptive performance), then optimize ─
    strategy = select_strategy(regime, returns=asset_returns)
    logger.info("Running optimizer: %s (regime=%s)…", strategy, regime)
    result = optimize(
        strategy=strategy,
        returns=asset_returns,
        sentiment_modifiers=sentiment_results,
        regime=regime,
    )
    target_weights: dict[str, float] = result["weights"]
    logger.info(
        "Optimizer result — Sharpe: %.2f  Vol: %.1f%%  Ret: %.1f%%",
        result["sharpe_ratio"], result["annual_volatility"] * 100, result["expected_annual_return"] * 100,
    )
    for ticker, w in sorted(target_weights.items(), key=lambda x: -x[1]):
        logger.info("  %-6s  %.1f%%", ticker, w * 100)

    # ── 6. Risk checks ─────────────────────────────────────────────────────────
    from broker import get_portfolio_value, get_current_positions
    portfolio_value = get_portfolio_value()
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
            "final_weights": json.dumps(target_weights),   # save intended weights for dashboard
            "notes": "; ".join(failures),
        })
        logger.warning("Pipeline aborted — risk checks failed.")
        return

    # ── 7. Drift gate ──────────────────────────────────────────────────────────
    if not should_rebalance(current_weights, target_weights):
        logger.info("No rebalance needed — drift below threshold.")
        _log_daily({
            "date": datetime.today().date(),
            "strategy": strategy,
            "regime": regime,
            "portfolio_value": portfolio_value,
            "sharpe": result["sharpe_ratio"],
            "expected_return": result["expected_annual_return"],
            "annual_vol": result["annual_volatility"],
            "orders_placed": 0,
            "final_weights": json.dumps(current_weights),
            "notes": "no_rebalance",
        })
        return

    # ── 8. Rebalance ───────────────────────────────────────────────────────────
    logger.info("Rebalancing…")
    from broker import rebalance
    orders = rebalance(target_weights)
    logger.info("%d orders placed.", len(orders))

    # ── 9. Log ────────────────────────────────────────────────────────────────
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
        "notes": "",
    })

    logger.info("Pipeline complete.")


if __name__ == "__main__":
    main()
