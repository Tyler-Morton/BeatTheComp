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
        # Paper vs live controlled by ALPACA_BASE_URL — only one place to change for live trading
        base_url = os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")
        is_paper = "paper" in base_url.lower()
        _client = TradingClient(
            api_key=os.getenv("ALPACA_API_KEY", ""),
            secret_key=os.getenv("ALPACA_SECRET_KEY", ""),
            paper=is_paper,
        )
        logger.info("Alpaca client initialized (%s)", "paper" if is_paper else "LIVE")
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

        # Compute diffs once
        diffs = {
            sym: target_dollars.get(sym, 0.0) - current_dollars.get(sym, 0.0)
            for sym in set(target_dollars) | set(current_dollars)
        }

        # ── PHASE 1: Submit ALL sell orders first ────────────────────────────
        sell_syms = [s for s, d in diffs.items() if d < -MIN_ORDER_NOTIONAL]
        for sym in sell_syms:
            diff = diffs[sym]
            try:
                # Cap notional at 99.5% of current value to avoid float precision
                # "insufficient qty available" errors on full-position sells
                current_val = current_dollars.get(sym, 0)
                notional = min(abs(diff), current_val * 0.995)
                if notional < MIN_ORDER_NOTIONAL: continue
                req = MarketOrderRequest(
                    symbol=sym, notional=round(notional, 2),
                    side=OrderSide.SELL, time_in_force=TimeInForce.DAY,
                )
                order = tc.submit_order(req)
                orders_placed.append({"symbol": sym, "side": "sell",
                                       "notional": round(notional, 2),
                                       "order_id": str(order.id)})
                logger.info("Order placed: SELL %s $%.2f", sym, notional)
            except Exception as exc:
                logger.error("Sell failed for %s: %s", sym, exc)

        # ── PHASE 2: Wait for sells to settle, then submit buys ──────────────
        # Alpaca fills market orders fast but buying_power update can lag a few sec.
        # Poll until buying_power has increased enough OR 30 seconds elapse.
        if sell_syms:
            import time as _time
            start_bp = float(tc.get_account().buying_power)
            target_buys = sum(d for d in diffs.values() if d > MIN_ORDER_NOTIONAL)
            for _ in range(15):  # max 15 × 2s = 30 seconds
                _time.sleep(2)
                bp_now = float(tc.get_account().buying_power)
                if bp_now >= target_buys * 0.95 or bp_now > start_bp * 5:
                    logger.info("Sells settled — buying power now $%.2f", bp_now)
                    break
            else:
                logger.warning("Sells still settling after 30s — buying power $%.2f (need $%.2f)",
                               float(tc.get_account().buying_power), target_buys)

        # ── PHASE 3: Submit buy orders — sized to actual buying power ────────
        buy_syms = [s for s, d in diffs.items() if d > MIN_ORDER_NOTIONAL]
        buy_syms.sort(key=lambda s: -diffs[s])   # biggest buys first (priority)
        for sym in buy_syms:
            diff = diffs[sym]
            try:
                # Re-check buying power for each order to prevent cascading failures
                bp = float(tc.get_account().buying_power)
                if bp < MIN_ORDER_NOTIONAL:
                    logger.warning("Out of buying power, skipping remaining buys")
                    break
                notional = min(abs(diff), bp * 0.98)  # 2% buffer
                if notional < MIN_ORDER_NOTIONAL: continue
                req = MarketOrderRequest(
                    symbol=sym, notional=round(notional, 2),
                    side=OrderSide.BUY, time_in_force=TimeInForce.DAY,
                )
                order = tc.submit_order(req)
                orders_placed.append({"symbol": sym, "side": "buy",
                                       "notional": round(notional, 2),
                                       "order_id": str(order.id)})
                logger.info("Order placed: BUY %s $%.2f", sym, notional)
            except Exception as exc:
                logger.error("Buy failed for %s: %s", sym, exc)

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
