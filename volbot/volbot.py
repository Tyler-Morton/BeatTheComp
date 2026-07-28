"""volbot v2 — LADDERED 3-index vol-premium paper sleeve (SPY/QQQ/IWM iron condors).

Daily run:
  1. Market data: SPY/QQQ/IWM spots (Alpaca) + VIX/VXN/RVX + VIX3M (FRED) ->
     per-underlying VRP and its rolling top-tercile threshold, market contango gate.
  2. Manage every open rung: EXPIRE-WORTHLESS (no profit-take, no time-stop); close a rung
     only on the 2x-credit loss-stop or at <=1 DTE (assignment dodge).
  3. Entries: per underlying — if its filters pass, it's been >=ENTRY_GAP_DAYS since the last
     entry on that name, it has <MAX_RUNGS_PER open rungs, and total at-risk stays under
     TOTAL_RISK_CAP — open one ~30-DTE ~16-delta condor sized to RISK_PER_RUNG of equity.
  4. Log everything to volbot_log.csv; rung state in volbot_state.json.

DRY_RUN computes and LOGS intended orders without submitting. Validated design:
research/volbot_ladder_backtest.py + research/volbot_spec.md.
"""
import io
import json
import math
import time
from datetime import date, timedelta

import numpy as np
import pandas as pd
import requests
from scipy.stats import norm

import config as C

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import (GetOptionContractsRequest, OptionLegRequest,
                                     MarketOrderRequest, LimitOrderRequest)
from alpaca.trading.enums import (ContractType, AssetStatus, OrderSide, OrderClass, TimeInForce)
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.historical.option import OptionHistoricalDataClient
from alpaca.data.requests import StockBarsRequest, OptionLatestQuoteRequest
from alpaca.data.timeframe import TimeFrame
from alpaca.data.enums import DataFeed


# ── Black-Scholes deltas (strike picking; greeks aren't on the contract API) ──
def _d1(S, K, T, sig):
    return (math.log(S / K) + (C.RISK_FREE + 0.5 * sig ** 2) * T) / (sig * math.sqrt(T))


def put_delta(S, K, T, sig):
    if T <= 0 or sig <= 0:
        return -1.0 if K > S else 0.0
    return norm.cdf(_d1(S, K, T, sig)) - 1.0


def call_delta(S, K, T, sig):
    if T <= 0 or sig <= 0:
        return 1.0 if K < S else 0.0
    return norm.cdf(_d1(S, K, T, sig))


# ── clients ───────────────────────────────────────────────────────────────────
def clients():
    if not C.API_KEY or not C.SECRET_KEY:
        raise SystemExit("Missing VOLBOT_ALPACA_API_KEY / VOLBOT_ALPACA_SECRET_KEY in .env")
    trade = TradingClient(C.API_KEY, C.SECRET_KEY, paper=C.PAPER)
    stock = StockHistoricalDataClient(C.API_KEY, C.SECRET_KEY)
    opt = OptionHistoricalDataClient(C.API_KEY, C.SECRET_KEY)
    return trade, stock, opt


# ── market data + per-underlying filters ──────────────────────────────────────
def _fred(series):
    txt = requests.get(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series}", timeout=30).text
    df = pd.read_csv(io.StringIO(txt))
    df.columns = ["date", series]
    df[series] = pd.to_numeric(df[series], errors="coerce")
    df["date"] = pd.to_datetime(df["date"])
    return df.set_index("date")[series].dropna()


def market_data(stock) -> dict:
    """Per-underlying spot/IV/VRP-gate + the market-wide contango gate."""
    req = StockBarsRequest(symbol_or_symbols=list(C.UNDERLYINGS), timeframe=TimeFrame.Day,
                           start=pd.Timestamp.now() - pd.Timedelta(days=560), feed=DataFeed.IEX)
    bars = stock.get_stock_bars(req).df["close"].unstack(level=0).sort_index()
    bars.index = pd.to_datetime(bars.index).tz_localize(None).normalize()

    near, far = _fred(C.TERM_NEAR), _fred(C.TERM_FAR)
    contango = float(near.iloc[-1]) < float(far.iloc[-1])

    # bars comes back out too: settling an expired rung needs the underlying's
    # close on its expiry date, and refetching it separately would be a second
    # API call for data we already have.
    out = {"contango": contango, "term_near": float(near.iloc[-1]),
           "term_far": float(far.iloc[-1]), "bars": bars, "u": {}}
    for u, ivname in C.UNDERLYINGS.items():
        ivs = near if ivname == C.TERM_NEAR else _fred(ivname)
        px = bars[u].dropna()
        realized = px.pct_change().rolling(C.REALIZED_WIN).std() * np.sqrt(252)
        iv_al = ivs.reindex(realized.index, method="ffill") / 100.0
        vrp = (iv_al - realized).dropna()
        thr = vrp.rolling(C.VRP_LOOKBACK, min_periods=60).quantile(C.VRP_TERCILE)
        iv_today = float(ivs.iloc[-1])
        rich = bool(vrp.iloc[-1] > thr.iloc[-1])
        out["u"][u] = dict(S=float(px.iloc[-1]), iv=iv_today, vrp=float(vrp.iloc[-1]),
                           thr=float(thr.iloc[-1]), rich=rich,
                           no_spike=iv_today < C.IV_MAX,
                           passes=contango and rich and iv_today < C.IV_MAX)
    return out


# ── contract selection / pricing ──────────────────────────────────────────────
def pick_condor(trade, u: str, S: float, iv_pct: float):
    """The 4 contracts for a ~16-delta condor on `u`, wings ~WING_FRAC of spot, ~30 DTE."""
    sig = iv_pct / 100.0
    lo = (date.today() + timedelta(days=C.DTE_MIN)).isoformat()
    hi = (date.today() + timedelta(days=C.DTE_MAX)).isoformat()

    def fetch(ctype):
        req = GetOptionContractsRequest(
            underlying_symbols=[u], status=AssetStatus.ACTIVE, type=ctype,
            expiration_date_gte=lo, expiration_date_lte=hi,
            strike_price_gte=str(round(S * 0.80, 0)), strike_price_lte=str(round(S * 1.20, 0)),
            limit=1000)
        return trade.get_option_contracts(req).option_contracts

    puts, calls = fetch(ContractType.PUT), fetch(ContractType.CALL)
    if not puts or not calls:
        return None
    exps = sorted({c.expiration_date for c in puts} & {c.expiration_date for c in calls},
                  key=lambda d: abs((pd.Timestamp(d).date() - date.today()).days - C.TARGET_DTE))
    if not exps:
        return None
    exp = exps[0]
    T = max((pd.Timestamp(exp).date() - date.today()).days, 1) / 365.0
    puts = sorted([c for c in puts if c.expiration_date == exp], key=lambda c: float(c.strike_price))
    calls = sorted([c for c in calls if c.expiration_date == exp], key=lambda c: float(c.strike_price))

    width = max(round(S * C.WING_FRAC), 1.0)
    short_put = min(puts, key=lambda c: abs(put_delta(S, float(c.strike_price), T, sig) + C.SHORT_DELTA))
    short_call = min(calls, key=lambda c: abs(call_delta(S, float(c.strike_price), T, sig) - C.SHORT_DELTA))
    spk, sck = float(short_put.strike_price), float(short_call.strike_price)
    long_put = min(puts, key=lambda c: abs(float(c.strike_price) - (spk - width)))
    long_call = min(calls, key=lambda c: abs(float(c.strike_price) - (sck + width)))
    if float(long_put.strike_price) >= spk or float(long_call.strike_price) <= sck:
        return None                                   # no distinct wing available
    return dict(u=u, exp=str(exp),
                short_put=short_put.symbol, long_put=long_put.symbol,
                short_call=short_call.symbol, long_call=long_call.symbol,
                spk=spk, lpk=float(long_put.strike_price),
                sck=sck, lck=float(long_call.strike_price))


def mid(opt, symbol):
    q = opt.get_option_latest_quote(OptionLatestQuoteRequest(symbol_or_symbols=symbol))[symbol]
    if q.bid_price and q.ask_price:
        return (q.bid_price + q.ask_price) / 2.0
    return q.ask_price or q.bid_price or 0.0


def price_condor(opt, rung):
    m = {k: mid(opt, rung[k]) for k in ("short_put", "long_put", "short_call", "long_call")}
    credit = (m["short_put"] + m["short_call"]) - (m["long_put"] + m["long_call"])
    width = max(rung["spk"] - rung["lpk"], rung["lck"] - rung["sck"])
    return credit, width


# ── orders ────────────────────────────────────────────────────────────────────
def _legs(rung, opening):
    s, b = (OrderSide.SELL, OrderSide.BUY) if opening else (OrderSide.BUY, OrderSide.SELL)
    return [OptionLegRequest(symbol=rung["short_put"], side=s, ratio_qty=1),
            OptionLegRequest(symbol=rung["long_put"], side=b, ratio_qty=1),
            OptionLegRequest(symbol=rung["short_call"], side=s, ratio_qty=1),
            OptionLegRequest(symbol=rung["long_call"], side=b, ratio_qty=1)]


def submit(trade, rung, qty, opening, limit_price=None):
    """Send one MLEG order. limit_price=None means a market order.

    Alpaca's MLEG sign convention: limit_price POSITIVE = a debit you'll pay,
    NEGATIVE = a credit you want to receive.
    """
    action = "OPEN" if opening else "CLOSE"
    tag = (f"{rung['u']} {qty}x SP{rung['spk']:.0f}/LP{rung['lpk']:.0f} "
           f"SC{rung['sck']:.0f}/LC{rung['lck']:.0f} exp {rung['exp']}")
    kind = "MKT" if limit_price is None else f"LMT {limit_price:+.2f}"
    if C.DRY_RUN:
        print(f"  [DRY_RUN] would {action} {tag} [{kind}]")
        return None
    legs = _legs(rung, opening)
    if limit_price is None:
        req = MarketOrderRequest(qty=qty, order_class=OrderClass.MLEG,
                                 time_in_force=TimeInForce.DAY, legs=legs)
    else:
        req = LimitOrderRequest(qty=qty, order_class=OrderClass.MLEG,
                                time_in_force=TimeInForce.DAY, legs=legs,
                                limit_price=round(limit_price, 2))
    res = trade.submit_order(req)
    print(f"  {action} submitted ({tag}) [{kind}]: order {res.id}")
    return res.id


def execute(trade, rung, qty, opening, best, worst, allow_market):
    """Work a limit ladder from `best` toward `worst`. Returns (order_id, net).

    `best`/`worst` are quoted as POSITIVE magnitudes in the natural direction:
    on an open they're credits we want (higher = better), on a close they're
    debits we'll pay (lower = better). The Alpaca sign flip happens here.

    allow_market=False -> if the ladder is exhausted, CANCEL and take no trade.
    That's correct for entries: refusing a bad price costs one skipped rung.
    allow_market=True  -> finish with a market order. That's correct for exits,
    where not getting out is worse than getting out badly.
    """
    if not C.USE_LIMIT_ORDERS:
        oid = submit(trade, rung, qty, opening)
        return oid, fill_price(trade, oid)

    steps = max(1, C.LIMIT_STEPS)
    tries = max(1, int(C.LIMIT_WAIT_SEC / 1.5))
    for i in range(steps):
        frac = i / max(steps - 1, 1)
        px = best + (worst - best) * frac
        oid = submit(trade, rung, qty, opening, limit_price=-px if opening else px)
        net = fill_price(trade, oid, tries=tries, pause=1.5)
        if net is not None:
            return oid, net
        try:
            trade.cancel_order_by_id(oid)
        except Exception:
            pass
        print(f"    no fill at {px:.2f}, re-pricing")

    if allow_market:
        print("    limit ladder exhausted — falling back to market (exit must complete)")
        oid = submit(trade, rung, qty, opening)
        return oid, fill_price(trade, oid)
    return None, None


def fill_price(trade, order_id, tries=12, pause=1.5):
    """Net fill price of a multi-leg order, or None if it hasn't filled in time.

    Alpaca's sign convention on an MLEG parent: NEGATIVE = net credit received,
    POSITIVE = net debit paid. Callers flip it as needed.

    This exists because price_condor() reads MID quotes *before* submitting, and
    that mid was what got stored as the rung's credit. On 2026-07-27 an IWM rung
    was recorded at 0.51 while the actual fill was 0.15 — 71% of the credit gone
    crossing four legs. The account received $506.72 that day; the mid-based
    numbers claimed $972. Booking the mid makes the ledger disagree with the
    broker, which would have quietly inflated every realized_pnl in the
    November evaluation.
    """
    if order_id is None:
        return None
    for _ in range(tries):
        try:
            o = trade.get_order_by_id(order_id)
            if o.filled_avg_price is not None and str(o.status).endswith("FILLED"):
                return float(o.filled_avg_price)
        except Exception:
            pass
        time.sleep(pause)
    return None


# ── state (a LIST of rungs) + logging ─────────────────────────────────────────
def load_state() -> dict:
    if not C.STATE_FILE.exists():
        return {"rungs": [], "last_entry": {}}
    st = json.loads(C.STATE_FILE.read_text())
    if "rungs" not in st:                              # migrate v1 single-position state
        st = {"rungs": [dict(st, u=st.get("u", "SPY"))] if "exp" in st else [], "last_entry": {}}
    st.setdefault("last_entry", {})
    return st


def save_state(st):
    C.STATE_FILE.write_text(json.dumps(st, indent=2))


def log(row):
    """One row per DAY, not per run.

    volbot.yml fires several fallback crons and every one runs the full
    pipeline — which is correct, because it lets a loss-stop fire intraday
    rather than waiting for tomorrow. But each run also appended a row, so the
    file held 56 rows across 20 dates. Any equity series built from it counted
    the same session up to three times.

    Replacing today's row keeps the latest state per session and makes the file
    one observation per day. The per-condor ledger (volbot_trades.csv) is
    append-only and unaffected — a closed rung is a real event, not a snapshot.
    """
    df = pd.DataFrame([row])
    if C.LOG_FILE.exists():
        old = pd.read_csv(C.LOG_FILE)
        if "date" in old.columns:
            old = old[old["date"].astype(str) != str(row.get("date"))]
        df = pd.concat([old, df], ignore_index=True)
    df.to_csv(C.LOG_FILE, index=False)


def settle_value(rung, bars):
    """What an expired condor was actually worth, per contract. None if unknown.

    The old code assumed anything past expiry expired worthless. That is only
    true when the underlying finished between the short strikes — and when it
    doesn't, the assumption books a max-profit win on what was really a loss.
    The error is one-directional, so a sleeve that occasionally breaches would
    have looked flawless in the record forever.

    Iron condor value at expiry = whichever short leg finished in the money,
    capped by its long wing:
        put side  = clamp(spk - S, 0, spk - lpk)
        call side = clamp(S - sck, 0, lck - sck)
    """
    exp = pd.Timestamp(rung["exp"]).normalize()
    px = bars[rung["u"]].dropna()
    on_or_before = px.index[px.index <= exp]
    if len(on_or_before) == 0:
        return None
    S = float(px.loc[on_or_before[-1]])
    put_side = min(max(rung["spk"] - S, 0.0), rung["spk"] - rung["lpk"])
    call_side = min(max(S - rung["sck"], 0.0), rung["lck"] - rung["sck"])
    return put_side + call_side, S


def log_trade(rung, exit_cost, reason, spot=None):
    """One row per closed condor: what it made, and why it ended.

    realized_pnl is signed dollars: (credit taken in - cost to get out) x 100 x qty.
    Deliberately a separate file from the daily log so condor P&L stays cleanly
    separable from the VB-2 beta-parking overlay — the premium edge has to be
    judgeable on its own, or the A/B is worthless.
    """
    credit, qty = rung.get("credit", 0.0), rung.get("qty", 0)
    pnl = (credit - exit_cost) * 100 * qty
    row = dict(
        exit_date=str(date.today()), entry_date=rung.get("entry", ""),
        u=rung["u"], exp=rung["exp"], qty=qty,
        spk=rung["spk"], lpk=rung["lpk"], sck=rung["sck"], lck=rung["lck"],
        credit=round(credit, 2), exit_cost=round(exit_cost, 2),
        # Keep the mid alongside the fill so execution quality is measurable
        # across trades, not just P&L. If entry_slip stays large on IWM this is
        # the column that proves the edge is dying at the door rather than in
        # the strategy.
        credit_mid=rung.get("credit_mid", ""), entry_slip=rung.get("slippage", ""),
        maxloss=rung.get("maxloss", ""),
        realized_pnl=round(pnl, 2),
        pct_of_credit=round(100 * (credit - exit_cost) / credit, 1) if credit else "",
        spot_at_exit=round(spot, 2) if spot is not None else "",
        reason=reason, dry_run=C.DRY_RUN)
    if C.DRY_RUN:
        print(f"  [DRY_RUN] would log trade: {rung['u']} {reason} pnl {pnl:+.2f}")
        return
    pd.DataFrame([row]).to_csv(C.TRADES_FILE, mode="a",
                              header=not C.TRADES_FILE.exists(), index=False)


def broker_option_positions(trade) -> int:
    try:
        return sum(1 for p in trade.get_all_positions()
                   if "option" in str(getattr(p, "asset_class", "")).lower())
    except Exception:
        return -1


# ── orchestration ─────────────────────────────────────────────────────────────
def main():
    trade, stock, opt = clients()
    equity = float(trade.get_account().equity)
    md = market_data(stock)
    st = load_state()
    today = date.today()
    notes = []

    gate = " ".join(f"{u}:{'RICH' if d['rich'] else 'cheap'}/iv{d['iv']:.0f}" for u, d in md["u"].items())
    print(f"{today}  contango={md['contango']} ({md['term_near']:.1f}<{md['term_far']:.1f}) | {gate}")

    # 1) manage every open rung (expire-worthless; only loss-stop / assignment-dodge closes)
    kept = []
    for rung in st["rungs"]:
        dte = (pd.Timestamp(rung["exp"]).date() - today).days
        if dte < 0:
            settled = settle_value(rung, md["bars"])
            if settled is None:
                # No settlement price means we cannot say what this rung made.
                # Holding it for manual review is the honest failure mode;
                # dropping it silently is how the old code lost the P&L.
                notes.append(f"{rung['u']} past expiry but no settlement price "
                             f"— HOLDING for manual review")
                kept.append(rung)
                continue
            cost, spot = settled
            reason = "expiry-worthless" if cost == 0 else "expiry-ITM"
            log_trade(rung, cost, reason, spot)
            pnl = (rung["credit"] - cost) * 100 * rung["qty"]
            notes.append(f"{rung['u']} {reason} (spot {spot:.2f}, "
                         f"cost {cost:.2f}) pnl {pnl:+.0f}")
            continue
        try:
            val, _ = price_condor(opt, rung)
        except Exception as e:
            notes.append(f"{rung['u']} quote fail ({type(e).__name__}) — holding")
            kept.append(rung); continue
        if dte <= C.CLOSE_AT_DTE:
            # allow_market=True: dodging assignment is not optional, so if the
            # ladder doesn't fill we pay up rather than carry the rung to expiry.
            _, net = execute(trade, rung, rung["qty"], opening=False,
                             best=val, worst=val * (1 + C.LIMIT_STEP_SLACK),
                             allow_market=True)
            cost = net if net is not None else val
            log_trade(rung, cost, "expiry-close")
            pnl = (rung["credit"] - cost) * 100 * rung["qty"]
            notes.append(f"{rung['u']} expiry-close (dte {dte}) pnl {pnl:+.0f}")
        elif val >= C.LOSS_STOP_MULT * rung["credit"] and val > 0:
            _, net = execute(trade, rung, rung["qty"], opening=False,
                             best=val, worst=val * (1 + C.LIMIT_STEP_SLACK),
                             allow_market=True)
            cost = net if net is not None else val
            log_trade(rung, cost, "loss-stop")
            pnl = (rung["credit"] - cost) * 100 * rung["qty"]
            notes.append(f"{rung['u']} LOSS-STOP (value {val:.2f} vs credit "
                         f"{rung['credit']:.2f}) pnl {pnl:+.0f}")
        else:
            kept.append(rung)
    st["rungs"] = kept

    # state-desync guard: broker shows options but we track none -> don't open blind
    if not st["rungs"] and broker_option_positions(trade) > 0:
        notes.append("DESYNC: broker has option positions but state is empty — skipping entries")
        _finish(equity, md, st, notes); return

    # 2) entries per underlying (cadence + rung cap + total-risk cap)
    at_risk = sum(r["maxloss"] * 100 * r["qty"] for r in st["rungs"])
    for u, d in md["u"].items():
        if not d["passes"]:
            continue
        last = st["last_entry"].get(u)
        if last and (today - date.fromisoformat(last)).days < C.ENTRY_GAP_DAYS:
            continue
        if sum(1 for r in st["rungs"] if r["u"] == u) >= C.MAX_RUNGS_PER:
            notes.append(f"{u} skip: rung cap"); continue
        rung = pick_condor(trade, u, d["S"], d["iv"])
        if not rung:
            notes.append(f"{u} skip: no suitable contracts"); continue
        credit, width = price_condor(opt, rung)
        maxloss = width - credit
        if credit <= 0 or maxloss <= 0:
            notes.append(f"{u} skip: bad credit ({credit:.2f})"); continue
        # Reject structurally bad trades before we even try to fill them. The
        # 2026-07-27 IWM rung came in at 5% of width — risking 2.85 to make 0.15.
        # No order type saves a trade whose reward:risk is that broken.
        if credit < C.MIN_CREDIT_FRAC * width:
            notes.append(f"{u} skip: credit {credit:.2f} is {credit/width:.0%} of "
                         f"width {width:.0f}, under the {C.MIN_CREDIT_FRAC:.0%} floor")
            continue
        qty = int(C.RISK_PER_RUNG * equity / (maxloss * 100))
        new_risk = maxloss * 100 * qty
        if qty < 1:
            notes.append(f"{u} skip: size<1"); continue
        if at_risk + new_risk > C.TOTAL_RISK_CAP * equity:
            notes.append(f"{u} skip: total-risk cap"); continue
        # Work down from mid, but never below the credit floor. If the book
        # won't pay that, we simply don't trade this rung today.
        floor = C.MIN_CREDIT_FRAC * width
        oid, net = execute(trade, rung, qty, opening=True,
                           best=credit, worst=floor, allow_market=False)
        if oid is None:
            notes.append(f"{u} skip: no fill down to floor {floor:.2f} "
                         f"(mid was {credit:.2f})")
            continue
        # Book the FILL, not the mid. Everything downstream — realized P&L, the
        # at-risk total, the risk cap that gates the next entry — has to be based
        # on what the broker actually did, or the ledger drifts from the account.
        fill_credit = -net if net is not None else credit
        fill_maxloss = width - fill_credit          # true max loss is wider when we slip
        slip = credit - fill_credit
        rung.update(qty=qty, credit=round(fill_credit, 2),
                    credit_mid=round(credit, 2), slippage=round(slip, 2),
                    maxloss=round(fill_maxloss, 2), entry=str(today))
        if not C.DRY_RUN:
            st["rungs"].append(rung)
            st["last_entry"][u] = str(today)
        at_risk += fill_maxloss * 100 * qty
        notes.append(f"{u} OPEN {qty}x credit {fill_credit:.2f} "
                     f"(mid {credit:.2f}, slip {slip:+.2f}) maxloss {fill_maxloss:.2f}")

    # 3) beta parking (VB-2): idle collateral -> SPY, reserve stays for margin
    park_beta(trade, st, notes)

    _finish(equity, md, st, notes)


def park_beta(trade, st, notes):
    """Keep cash near the reserve; everything beyond it sits in SPY.

    reserve = max(PARK_RESERVE_MULT x total-max-loss-at-risk, PARK_MIN_RESERVE).
    Cash above the reserve buys SPY; if cash has fallen below it (a loss-stop hit,
    or new rungs raised the reserve), trim SPY to refill. Small drifts are ignored.
    """
    if not C.BETA_PARK or C.DRY_RUN:
        return
    try:
        from alpaca.trading.enums import OrderSide, TimeInForce
        from alpaca.trading.requests import MarketOrderRequest

        acct = trade.get_account()
        cash = float(acct.cash)
        at_risk = sum(r["maxloss"] * 100 * r["qty"] for r in st["rungs"])
        reserve = max(C.PARK_RESERVE_MULT * at_risk, C.PARK_MIN_RESERVE)
        excess = cash - reserve

        if excess >= C.PARK_TRADE_MIN:
            trade.submit_order(MarketOrderRequest(
                symbol=C.PARK_SYMBOL, notional=round(excess, 2),
                side=OrderSide.BUY, time_in_force=TimeInForce.DAY))
            notes.append(f"beta-park: BUY {C.PARK_SYMBOL} ${excess:,.0f} "
                         f"(reserve ${reserve:,.0f})")
        elif excess <= -C.PARK_TRADE_MIN:
            try:
                pos_val = float(trade.get_open_position(C.PARK_SYMBOL).market_value)
            except Exception:
                pos_val = 0.0          # no SPY held — nothing to trim
            trim = round(min(-excess, pos_val), 2)
            if trim >= C.PARK_TRADE_MIN:
                trade.submit_order(MarketOrderRequest(
                    symbol=C.PARK_SYMBOL, notional=trim,
                    side=OrderSide.SELL, time_in_force=TimeInForce.DAY))
                notes.append(f"beta-park: SELL {C.PARK_SYMBOL} ${trim:,.0f} "
                             f"(refill reserve ${reserve:,.0f})")
    except Exception as exc:
        # Parking is an enhancement, never a reason to fail the condor pipeline.
        notes.append(f"beta-park failed (non-fatal): {type(exc).__name__}")


def _finish(equity, md, st, notes):
    if not C.DRY_RUN:
        save_state(st)
    at_risk = sum(r["maxloss"] * 100 * r["qty"] for r in st["rungs"])
    note = "; ".join(notes) if notes else "flat/hold: no action"
    log(dict(date=str(date.today()), equity=round(equity, 2),
             contango=md["contango"],
             **{f"{u.lower()}_iv": round(d["iv"], 1) for u, d in md["u"].items()},
             **{f"{u.lower()}_rich": d["rich"] for u, d in md["u"].items()},
             rungs=len(st["rungs"]), at_risk=round(at_risk, 0),
             dry_run=C.DRY_RUN, note=note))
    print(f"  rungs open: {len(st['rungs'])} | at-risk ${at_risk:,.0f} "
          f"({at_risk/equity*100:.1f}% of ${equity:,.0f}) -> {note}")


if __name__ == "__main__":
    main()
