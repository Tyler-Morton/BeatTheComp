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
from datetime import date, timedelta

import numpy as np
import pandas as pd
import requests
from scipy.stats import norm

import config as C

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import (GetOptionContractsRequest, OptionLegRequest, MarketOrderRequest)
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

    out = {"contango": contango, "term_near": float(near.iloc[-1]), "term_far": float(far.iloc[-1]), "u": {}}
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


def submit(trade, rung, qty, opening):
    action = "OPEN" if opening else "CLOSE"
    tag = (f"{rung['u']} {qty}x SP{rung['spk']:.0f}/LP{rung['lpk']:.0f} "
           f"SC{rung['sck']:.0f}/LC{rung['lck']:.0f} exp {rung['exp']}")
    if C.DRY_RUN:
        print(f"  [DRY_RUN] would {action} {tag}")
        return True
    req = MarketOrderRequest(qty=qty, order_class=OrderClass.MLEG,
                             time_in_force=TimeInForce.DAY, legs=_legs(rung, opening))
    res = trade.submit_order(req)
    print(f"  {action} submitted ({tag}): order {res.id}")
    return True


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
    df = pd.DataFrame([row])
    df.to_csv(C.LOG_FILE, mode="a", header=not C.LOG_FILE.exists(), index=False)


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
            notes.append(f"{rung['u']} rung expired-worthless")
            continue
        try:
            val, _ = price_condor(opt, rung)
        except Exception as e:
            notes.append(f"{rung['u']} quote fail ({type(e).__name__}) — holding")
            kept.append(rung); continue
        if dte <= C.CLOSE_AT_DTE:
            submit(trade, rung, rung["qty"], opening=False)
            notes.append(f"{rung['u']} expiry-close (dte {dte})")
        elif val >= C.LOSS_STOP_MULT * rung["credit"] and val > 0:
            submit(trade, rung, rung["qty"], opening=False)
            notes.append(f"{rung['u']} LOSS-STOP (value {val:.2f} vs credit {rung['credit']:.2f})")
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
        qty = int(C.RISK_PER_RUNG * equity / (maxloss * 100))
        new_risk = maxloss * 100 * qty
        if qty < 1:
            notes.append(f"{u} skip: size<1"); continue
        if at_risk + new_risk > C.TOTAL_RISK_CAP * equity:
            notes.append(f"{u} skip: total-risk cap"); continue
        submit(trade, rung, qty, opening=True)
        rung.update(qty=qty, credit=round(credit, 2), maxloss=round(maxloss, 2),
                    entry=str(today))
        if not C.DRY_RUN:
            st["rungs"].append(rung)
            st["last_entry"][u] = str(today)
        at_risk += new_risk
        notes.append(f"{u} OPEN {qty}x credit {credit:.2f} maxloss {maxloss:.2f}")

    _finish(equity, md, st, notes)


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
