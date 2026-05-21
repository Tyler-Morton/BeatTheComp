"""Alpaca broker integration — paper or live via one env var change."""

import logging
import os
from datetime import datetime, timedelta, timezone

import pandas as pd

logger = logging.getLogger(__name__)

_client = None
_data_client = None

MIN_ORDER_NOTIONAL = 1.0   # Alpaca rejects orders below ~$1


def _trading_client():
    global _client
    if _client is None:
        from alpaca.trading.client import TradingClient
        _client = TradingClient(
            api_key=os.getenv("ALPACA_API_KEY", ""),
            secret_key=os.getenv("ALPACA_SECRET_KEY", ""),
            paper=True,
        )
    return _client


# ── Market hours ───────────────────────────────────────────────────────────────

def is_market_open() -> bool:
    try:
        clock = _trading_client().get_clock()
        return bool(clock.is_open)
    except Exception as exc:
        logger.error("Could not check market hours: %s", exc)
        return False


# ── Portfolio state ────────────────────────────────────────────────────────────

def get_portfolio_value() -> float:
    """Return total portfolio equity in dollars."""
    try:
        account = _trading_client().get_account()
        return float(account.equity)
    except Exception as exc:
        logger.error("get_portfolio_value failed: %s", exc)
        return 0.0


def get_current_positions() -> dict[str, float]:
    """Return {symbol: current_weight} based on market values."""
    try:
        positions = _trading_client().get_all_positions()
        account = _trading_client().get_account()
        total = float(account.equity)
        if total <= 0:
            return {}
        return {
            p.symbol: round(float(p.market_value) / total, 4)
            for p in positions
        }
    except Exception as exc:
        logger.error("get_current_positions failed: %s", exc)
        return {}


# ── Rebalancing ────────────────────────────────────────────────────────────────

def rebalance(target_weights: dict[str, float]) -> list[dict]:
    """Place market orders to move toward target_weights. Returns list of orders placed."""
    from alpaca.trading.enums import OrderSide, TimeInForce
    from alpaca.trading.requests import MarketOrderRequest

    tc = _trading_client()
    orders_placed: list[dict] = []

    try:
        portfolio_value = get_portfolio_value()
        current_positions = get_current_positions()
        if portfolio_value <= 0:
            logger.error("Portfolio value is zero — aborting rebalance")
            return []

        # Calculate dollar targets
        target_dollars = {sym: w * portfolio_value for sym, w in target_weights.items()}

        # Get current dollar values
        current_dollars: dict[str, float] = {}
        try:
            positions = tc.get_all_positions()
            for p in positions:
                current_dollars[p.symbol] = float(p.market_value)
        except Exception as exc:
            logger.warning("Could not fetch positions: %s", exc)

        # Sell first, then buy (frees up cash)
        diffs = {
            sym: target_dollars.get(sym, 0.0) - current_dollars.get(sym, 0.0)
            for sym in set(target_dollars) | set(current_dollars)
        }
        sorted_syms = sorted(diffs, key=lambda s: diffs[s])   # sells first

        for sym in sorted_syms:
            diff = diffs[sym]
            if abs(diff) < MIN_ORDER_NOTIONAL:
                continue
            side = OrderSide.BUY if diff > 0 else OrderSide.SELL
            try:
                req = MarketOrderRequest(
                    symbol=sym,
                    notional=round(abs(diff), 2),
                    side=side,
                    time_in_force=TimeInForce.DAY,
                )
                order = tc.submit_order(req)
                rec = {
                    "symbol": sym,
                    "side": side.value,
                    "notional": round(abs(diff), 2),
                    "order_id": str(order.id),
                }
                orders_placed.append(rec)
                logger.info("Order placed: %s %s $%.2f", side.value.upper(), sym, abs(diff))
            except Exception as exc:
                logger.error("Order failed for %s: %s", sym, exc)

    except Exception as exc:
        logger.error("Rebalance error: %s", exc)

    return orders_placed


# ── Account history ────────────────────────────────────────────────────────────

def get_account_history(days: int = 365) -> pd.DataFrame:
    """Return portfolio equity curve as a DataFrame with columns [timestamp, equity]."""
    try:
        from alpaca.trading.requests import GetPortfolioHistoryRequest
        req = GetPortfolioHistoryRequest(period=f"{days}D", timeframe="1D")
        history = _trading_client().get_portfolio_history(req)
        df = pd.DataFrame({
            "timestamp": pd.to_datetime(history.timestamp, unit="s"),
            "equity": history.equity,
        })
        return df
    except Exception as exc:
        logger.warning("get_account_history failed: %s", exc)
        return pd.DataFrame(columns=["timestamp", "equity"])
