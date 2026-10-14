"""Everything that talks to Alpaca lives here.

PAPER ONLY. config.PAPER_TRADING_MODE is a hard guard: the trading client is
always built with paper=True, and a non-paper ALPACA_BASE_URL makes it refuse to
start rather than quietly trade real money.
"""

import logging
import os
from datetime import datetime, timedelta, timezone

import pandas as pd

logger = logging.getLogger(__name__)

_client = None
_data_client = None
_fractionable_cache: dict[str, bool] = {}

MIN_ORDER_NOTIONAL = 1.0   # Alpaca won't take an order smaller than about a dollar


def _require_paper() -> bool:
    """Hard PAPER guard. Returns True or raises — there is no live path.

    This used to derive paper/live from ALPACA_BASE_URL, so setting that env var
    to the live endpoint would have moved real money with no code change. All
    accounts are paper by standing rule; flipping that must be a code change.
    """
    from config import PAPER_TRADING_MODE
    base_url = os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")
    if PAPER_TRADING_MODE is not True or "paper" not in base_url.lower():
        raise RuntimeError(
            f"PAPER guard: refusing to trade (PAPER_TRADING_MODE={PAPER_TRADING_MODE!r}, "
            f"ALPACA_BASE_URL={base_url!r}). All accounts are paper.")
    return True


def _trading_client():
    global _client
    if _client is None:
        from alpaca.trading.client import TradingClient
        _client = TradingClient(
            api_key=os.getenv("ALPACA_API_KEY", ""),
            secret_key=os.getenv("ALPACA_SECRET_KEY", ""),
            paper=_require_paper(),
        )
        logger.info("Alpaca client initialized (paper)")
    return _client


def _data_client_get():
    global _data_client
    if _data_client is None:
        from alpaca.data.historical import StockHistoricalDataClient
        _data_client = StockHistoricalDataClient(
            api_key=os.getenv("ALPACA_API_KEY", ""),
            secret_key=os.getenv("ALPACA_SECRET_KEY", ""),
        )
    return _data_client


def _is_fractionable(tc, symbol: str) -> bool:
    """Return True if the asset can be bought in fractional shares.

    Cached per-symbol. On any lookup error we assume True (the old behavior),
    so a transient API hiccup can't silently block a whole-share fallback.
    """
    if symbol not in _fractionable_cache:
        try:
            asset = tc.get_asset(symbol)
            _fractionable_cache[symbol] = bool(asset.fractionable)
        except Exception as exc:
            logger.warning("Could not check fractionable for %s: %s — assuming yes", symbol, exc)
            return True
    return _fractionable_cache[symbol]


def _latest_price(symbol: str) -> float:
    """Latest trade price for sizing whole-share orders. 0.0 on failure."""
    try:
        from alpaca.data.requests import StockLatestTradeRequest
        dc = _data_client_get()
        resp = dc.get_stock_latest_trade(StockLatestTradeRequest(symbol_or_symbols=symbol))
        return float(resp[symbol].price)
    except Exception as exc:
        logger.warning("_latest_price failed for %s: %s", symbol, exc)
        return 0.0


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
    """What the whole account is worth right now, in dollars."""
    try:
        account = _trading_client().get_account()
        return float(account.equity)
    except Exception as exc:
        logger.error("get_portfolio_value failed: %s", exc)
        return 0.0


def get_current_positions() -> dict[str, float]:
    """What we actually hold right now, as {symbol: share of the portfolio}.

    Each weight is that position's market value divided by total equity, so the
    numbers describe how the money is split up today — not what we're aiming for.
    """
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


def get_live_snapshot() -> dict | None:
    """A fresh picture of the account for the dashboard, or None if we can't reach Alpaca.

    {
      "equity": float,            # current total portfolio value
      "last_equity": float,       # equity at yesterday's close (for daily change)
      "cash": float,
      "positions": {symbol: {"market_value", "weight", "current_price",
                             "unrealized_pl", "unrealized_plpc"}},
    }
    """
    if not os.getenv("ALPACA_API_KEY") or not os.getenv("ALPACA_SECRET_KEY"):
        return None
    try:
        tc = _trading_client()
        account = tc.get_account()
        positions = tc.get_all_positions()
        equity = float(account.equity)
        if equity <= 0:
            return None
        pos = {}
        for p in positions:
            mv = float(p.market_value)
            pos[p.symbol] = {
                "market_value": mv,
                "weight": mv / equity if equity else 0.0,
                "current_price": float(p.current_price),
                "unrealized_pl": float(p.unrealized_pl),
                "unrealized_plpc": float(p.unrealized_plpc),
            }
        return {
            "equity": equity,
            "last_equity": float(account.last_equity),
            "cash": float(account.cash),
            "positions": pos,
        }
    except Exception as exc:
        logger.warning("get_live_snapshot failed: %s", exc)
        return None


# ── Rebalancing ────────────────────────────────────────────────────────────────

def rebalance(target_weights: dict[str, float]) -> list[dict]:
    """Buy and sell whatever it takes to move the account toward target_weights.

    Returns the list of orders we actually fired off.
    """
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

        # Get current dollar values (+ share counts, for whole-share sells)
        current_dollars: dict[str, float] = {}
        current_qty: dict[str, float] = {}
        try:
            positions = tc.get_all_positions()
            for p in positions:
                current_dollars[p.symbol] = float(p.market_value)
                current_qty[p.symbol] = float(p.qty)
        except Exception as exc:
            # Do NOT carry on with an empty book: every diff would then be the
            # full target, and the buy loop would re-buy positions we already
            # hold (on margin, since buying power was the only cap).
            logger.error("Could not fetch positions: %s — aborting rebalance", exc)
            return []

        # Compute diffs once
        diffs = {
            sym: target_dollars.get(sym, 0.0) - current_dollars.get(sym, 0.0)
            for sym in set(target_dollars) | set(current_dollars)
        }

        # ── Step 1: sell everything we need to sell, first ───────────────────
        # We dump all the reductions before buying anything so the cash from
        # those sells is available to fund the buys a moment later.
        sell_syms = [s for s, d in diffs.items() if d < -MIN_ORDER_NOTIONAL]
        # Dust sweep (C2): a held position with NO target is closed whatever its
        # size. Sub-$1 lots never cleared the MIN_ORDER_NOTIONAL test above, so 28
        # leftover lots ($14, 1.5% of equity, mostly ex-alpha-sleeve stocks) sat in
        # the champion book indefinitely. close_position sells by qty, so the
        # notional minimum does not apply (verify on paper: one dust lot first).
        sell_syms += [s for s in current_dollars
                      if s not in sell_syms and target_dollars.get(s, 0.0) == 0.0
                      and current_qty.get(s, 0.0) > 0]
        for sym in sell_syms:
            diff = diffs[sym]
            try:
                current_val = current_dollars.get(sym, 0)
                if target_dollars.get(sym, 0.0) < MIN_ORDER_NOTIONAL:
                    # Full exit: close the whole position. The 99.5% notional cap
                    # below exists for partial trims, but on an exit it left a
                    # 0.5% dust position behind every time.
                    order = tc.close_position(sym)
                    orders_placed.append({"symbol": sym, "side": "sell",
                                           "notional": round(current_val, 2),
                                           "order_id": str(order.id)})
                    logger.info("Order placed: CLOSE %s (~$%.2f)", sym, current_val)
                elif _is_fractionable(tc, sym):
                    # Only ever sell up to 99.5% of what the position is worth. If
                    # we ask for 100% the rounding can land a hair over what we
                    # actually hold, and Alpaca rejects it with "insufficient qty."
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
                else:
                    # Non-fractionable (e.g. LASE/BJDX): Alpaca rejects notional
                    # sells, so sell whole shares. On a full exit (target ~0),
                    # dump every share — otherwise these become roach-motel
                    # positions the bot can buy but never sell.
                    qty_held = current_qty.get(sym, 0)
                    price = current_val / qty_held if qty_held else 0.0
                    if target_dollars.get(sym, 0.0) < MIN_ORDER_NOTIONAL:
                        qty = int(qty_held)               # full exit
                    elif price > 0:
                        qty = int(abs(diff) // price)     # partial trim
                    else:
                        qty = 0
                    if qty < 1: continue
                    req = MarketOrderRequest(
                        symbol=sym, qty=qty,
                        side=OrderSide.SELL, time_in_force=TimeInForce.DAY,
                    )
                    order = tc.submit_order(req)
                    est = qty * price
                    orders_placed.append({"symbol": sym, "side": "sell", "qty": qty,
                                           "notional": round(est, 2),
                                           "order_id": str(order.id)})
                    logger.info("Order placed: SELL %s %d shares (~$%.2f)", sym, qty, est)
            except Exception as exc:
                logger.error("Sell failed for %s: %s", sym, exc)

        # ── Step 2: wait for the sells themselves to finish ──────────────────
        # Poll each sell ORDER until it reaches a final state, instead of
        # guessing from buying power: the old "bp > 5× start" test fired on a
        # partial settle and let the buys run against cash that hadn't landed,
        # leaving part of the book unbought.
        sell_ids = [o["order_id"] for o in orders_placed if o["side"] == "sell"]
        if sell_ids:
            import time as _time
            final = {"filled", "canceled", "expired", "rejected", "done_for_day"}
            pending = set(sell_ids)
            for _ in range(45):  # 45 tries × 2s each = 90 seconds, then we give up waiting
                for oid in list(pending):
                    try:
                        status = str(tc.get_order_by_id(oid).status).split(".")[-1].lower()
                    except Exception as exc:
                        logger.warning("Could not read order %s: %s", oid, exc)
                        continue
                    if status in final:
                        pending.discard(oid)
                if not pending:
                    break
                _time.sleep(2)
            if pending:
                logger.warning("%d of %d sells still open after 90s — buys will be "
                               "sized to the cash that has landed", len(pending), len(sell_ids))
            else:
                logger.info("All %d sells final — buying power now $%.2f",
                            len(sell_ids), float(tc.get_account().buying_power))

        # ── Step 3: do the buying, sized to the cash we really have ──────────
        buy_syms = [s for s, d in diffs.items() if d > MIN_ORDER_NOTIONAL]
        buy_syms.sort(key=lambda s: -diffs[s])   # buy the biggest targets first, in case we run short
        for sym in buy_syms:
            diff = diffs[sym]
            try:
                # Check the cash again before every single buy. If one order eats
                # more than expected, the next one won't blindly overdraw and fail.
                # min(cash, buying_power): buying_power alone includes MARGIN, so
                # with sells still pending the buys borrowed instead of being
                # "sized to the cash that has landed". Same rule as sweep_idle_cash.
                acct = tc.get_account()
                bp = min(float(acct.cash), float(acct.buying_power))
                if bp < MIN_ORDER_NOTIONAL:
                    logger.warning("Out of buying power, skipping remaining buys")
                    break
                notional = min(abs(diff), bp * 0.98)  # leave a 2% cushion so we never ask for more than we have
                if notional < MIN_ORDER_NOTIONAL: continue

                if _is_fractionable(tc, sym):
                    # Fractional dollar order (most stocks)
                    req = MarketOrderRequest(
                        symbol=sym, notional=round(notional, 2),
                        side=OrderSide.BUY, time_in_force=TimeInForce.DAY,
                    )
                    order = tc.submit_order(req)
                    orders_placed.append({"symbol": sym, "side": "buy",
                                           "notional": round(notional, 2),
                                           "order_id": str(order.id)})
                    logger.info("Order placed: BUY %s $%.2f", sym, notional)
                else:
                    # Non-fractionable: must buy whole shares (e.g. ASTC).
                    # Round target dollars down to the nearest share; skip if we
                    # can't afford even one share.
                    price = _latest_price(sym)
                    if price <= 0:
                        logger.warning("No price for non-fractionable %s — skipping", sym)
                        continue
                    qty = int(notional // price)
                    if qty < 1:
                        logger.warning(
                            "Non-fractionable %s: target $%.2f < 1 share ($%.2f) — skipping",
                            sym, notional, price)
                        continue
                    req = MarketOrderRequest(
                        symbol=sym, qty=qty,
                        side=OrderSide.BUY, time_in_force=TimeInForce.DAY,
                    )
                    order = tc.submit_order(req)
                    est = qty * price
                    orders_placed.append({"symbol": sym, "side": "buy", "qty": qty,
                                           "notional": round(est, 2),
                                           "order_id": str(order.id)})
                    logger.info("Order placed: BUY %s %d shares (~$%.2f)", sym, qty, est)
            except Exception as exc:
                logger.error("Buy failed for %s: %s", sym, exc)

    except Exception as exc:
        logger.error("Rebalance error: %s", exc)

    return orders_placed


def sweep_idle_cash() -> dict | None:
    """Park leftover uninvested cash in the cash ETF (SHV) so it earns bill yield.

    Runs after trading settles: whatever cash is still sitting idle beyond a small
    buffer gets moved into CASH_ASSET instead of earning nothing. Returns the order
    dict, or None if there was nothing worth sweeping (or the sweep is disabled).
    """
    from config import CASH_ASSET, CASH_SWEEP_BUFFER, CASH_SWEEP_ENABLED
    if not CASH_SWEEP_ENABLED:
        return None
    from alpaca.trading.enums import OrderSide, TimeInForce
    from alpaca.trading.requests import MarketOrderRequest
    try:
        tc = _trading_client()
        acct = tc.get_account()
        idle = min(float(acct.cash), float(acct.buying_power))
        notional = round(idle - CASH_SWEEP_BUFFER, 2)
        if notional < MIN_ORDER_NOTIONAL:
            return None
        req = MarketOrderRequest(symbol=CASH_ASSET, notional=notional,
                                 side=OrderSide.BUY, time_in_force=TimeInForce.DAY)
        order = tc.submit_order(req)
        logger.info("Cash sweep: BUY %s $%.2f (idle cash -> bills)", CASH_ASSET, notional)
        return {"symbol": CASH_ASSET, "side": "buy", "notional": notional,
                "order_id": str(order.id)}
    except Exception as exc:
        logger.warning("Cash sweep failed (non-fatal): %s", exc)
        return None


# ── Account history ────────────────────────────────────────────────────────────

def get_account_history(days: int = 365) -> pd.DataFrame:
    """The account's value over time, as a table of [timestamp, equity] — i.e. the equity curve."""
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
