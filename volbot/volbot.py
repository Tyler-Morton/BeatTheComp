"""volbot — vol-premium SPY iron-condor paper sleeve.

Daily run:
  1. Pull market data (SPY price, VIX, VIX3M, 20d realized vol -> VRP + its rolling tercile).
  2. If a condor is open: manage it (loss-stop, or close near expiry to dodge assignment).
  3. If flat AND all entry filters pass: open one ~30-DTE ~16-delta iron condor, sized to risk.
  4. Log everything.

DRY_RUN (default) computes and LOGS the intended trade but submits NOTHING. Flip config.DRY_RUN
to False only after watching a few clean dry runs and adding the VOLBOT_* keys to .env.

Strategy is "expire-worthless": no profit-take, no time-stop — hold to expiry where OTM legs
settle for zero cost. The only active exit is the 2x-credit loss-stop. See research/volbot_spec.md.
"""
import io
import json
import math
from datetime import datetime, date, timedelta

import numpy as np
import pandas as pd
import requests
from scipy.stats import norm

import config as C

# alpaca-py (verified against the official options-iron-condor example)
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import (GetOptionContractsRequest, OptionLegRequest, MarketOrderRequest)
from alpaca.trading.enums import (ContractType, AssetStatus, OrderSide, OrderClass, TimeInForce)
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.historical.option import OptionHistoricalDataClient
from alpaca.data.requests import StockBarsRequest, OptionLatestQuoteRequest
from alpaca.data.timeframe import TimeFrame
from alpaca.data.enums import DataFeed


# ── Black-Scholes (for picking ~16-delta strikes; greeks aren't on the contract API) ──
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
        raise SystemExit("Missing VOLBOT_ALPACA_API_KEY / VOLBOT_ALPACA_SECRET_KEY in .env "
                         "(use the NEW paper account's keys).")
    trade = TradingClient(C.API_KEY, C.SECRET_KEY, paper=C.PAPER)
    stock = StockHistoricalDataClient(C.API_KEY, C.SECRET_KEY)
    opt = OptionHistoricalDataClient(C.API_KEY, C.SECRET_KEY)
    return trade, stock, opt


# ── market data + entry filters ─────────────────────────────────────────────
def _fred(series):
    txt = requests.get(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series}", timeout=30).text
    df = pd.read_csv(io.StringIO(txt))
    df.columns = ["date", series]
    df[series] = pd.to_numeric(df[series], errors="coerce")
    df["date"] = pd.to_datetime(df["date"])
    return df.set_index("date")[series].dropna()


def market_data(stock):
    vix = _fred("VIXCLS")
    vix3m = _fred("VXVCLS")
    # SPY history for realized vol + the VRP percentile series
    req = StockBarsRequest(symbol_or_symbols=C.UNDERLYING, timeframe=TimeFrame.Day,
                           start=pd.Timestamp.now() - pd.Timedelta(days=560), feed=DataFeed.IEX)
    bars = stock.get_stock_bars(req).df
    spy = bars.xs(C.UNDERLYING, level=0)["close"] if isinstance(bars.index, pd.MultiIndex) else bars["close"]
    spy.index = pd.to_datetime(spy.index).tz_localize(None)

    realized = spy.pct_change().rolling(C.REALIZED_WIN).std() * np.sqrt(252)
    v = vix.reindex(realized.index, method="ffill") / 100.0
    vrp = (v - realized).dropna()
    thr = vrp.rolling(C.VRP_LOOKBACK, min_periods=60).quantile(C.VRP_TERCILE)

    today_vix = float(vix.iloc[-1])
    today_vix3m = float(vix3m.iloc[-1])
    today_vrp = float(vrp.iloc[-1])
    today_thr = float(thr.iloc[-1])
    S = float(spy.iloc[-1])

    contango = today_vix < today_vix3m
    rich = today_vrp > today_thr
    no_spike = today_vix < C.VIX_MAX
    passes = (rich and no_spike and (contango or not C.REQUIRE_CONTANGO))
    return dict(S=S, vix=today_vix, vix3m=today_vix3m, vrp=today_vrp, vrp_thr=today_thr,
                contango=contango, rich=rich, no_spike=no_spike, passes=passes)


# ── strike / contract selection ───────────────────────────────────────────────
def pick_condor(trade, md):
    """Find the 4 SPY contracts for a ~16-delta, $5-wide iron condor ~30 DTE."""
    S, sig = md["S"], md["vix"] / 100.0
    lo = (date.today() + timedelta(days=C.DTE_MIN)).isoformat()
    hi = (date.today() + timedelta(days=C.DTE_MAX)).isoformat()
    band_lo, band_hi = round(S * 0.85, 0), round(S * 1.15, 0)

    def fetch(ctype):
        req = GetOptionContractsRequest(
            underlying_symbols=[C.UNDERLYING], status=AssetStatus.ACTIVE, type=ctype,
            expiration_date_gte=lo, expiration_date_lte=hi,
            strike_price_gte=str(band_lo), strike_price_lte=str(band_hi), limit=1000)
        return trade.get_option_contracts(req).option_contracts

    puts, calls = fetch(ContractType.PUT), fetch(ContractType.CALL)
    if not puts or not calls:
        return None
    # pick the expiry closest to TARGET_DTE that has both puts and calls
    exps = sorted({c.expiration_date for c in puts} & {c.expiration_date for c in calls},
                  key=lambda d: abs((pd.Timestamp(d).date() - date.today()).days - C.TARGET_DTE))
    if not exps:
        return None
    exp = exps[0]
    T = max((pd.Timestamp(exp).date() - date.today()).days, 1) / 365.0
    puts = sorted([c for c in puts if c.expiration_date == exp], key=lambda c: float(c.strike_price))
    calls = sorted([c for c in calls if c.expiration_date == exp], key=lambda c: float(c.strike_price))

    # short strikes = listed strike whose BS delta is closest to +/-SHORT_DELTA
    short_put = min(puts, key=lambda c: abs(put_delta(S, float(c.strike_price), T, sig) + C.SHORT_DELTA))
    short_call = min(calls, key=lambda c: abs(call_delta(S, float(c.strike_price), T, sig) - C.SHORT_DELTA))
    spk, sck = float(short_put.strike_price), float(short_call.strike_price)
    # long wings = nearest listed strike WING_WIDTH out
    long_put = min(puts, key=lambda c: abs(float(c.strike_price) - (spk - C.WING_WIDTH)))
    long_call = min(calls, key=lambda c: abs(float(c.strike_price) - (sck + C.WING_WIDTH)))

    return dict(exp=exp, T=T,
                short_put=short_put.symbol, long_put=long_put.symbol,
                short_call=short_call.symbol, long_call=long_call.symbol,
                spk=spk, lpk=float(long_put.strike_price),
                sck=sck, lck=float(long_call.strike_price))


def mid(opt, symbol):
    q = opt.get_option_latest_quote(OptionLatestQuoteRequest(symbol_or_symbols=symbol))[symbol]
    if q.bid_price and q.ask_price:
        return (q.bid_price + q.ask_price) / 2.0
    return q.ask_price or q.bid_price or 0.0


def price_condor(opt, cd):
    m = {k: mid(opt, cd[k]) for k in ("short_put", "long_put", "short_call", "long_call")}
    credit = (m["short_put"] + m["short_call"]) - (m["long_put"] + m["long_call"])
    width = max(cd["spk"] - cd["lpk"], cd["lck"] - cd["sck"])
    return credit, width, m


# ── orders ──────────────────────────────────────────────────────────────────
def _legs(cd, opening):
    """Opening: sell shorts, buy longs. Closing: reverse."""
    s, b = (OrderSide.SELL, OrderSide.BUY) if opening else (OrderSide.BUY, OrderSide.SELL)
    return [OptionLegRequest(symbol=cd["short_put"], side=s, ratio_qty=1),
            OptionLegRequest(symbol=cd["long_put"], side=b, ratio_qty=1),
            OptionLegRequest(symbol=cd["short_call"], side=s, ratio_qty=1),
            OptionLegRequest(symbol=cd["long_call"], side=b, ratio_qty=1)]


def submit(trade, cd, qty, opening):
    action = "OPEN" if opening else "CLOSE"
    if C.DRY_RUN:
        print(f"  [DRY_RUN] would {action} {qty}x condor: SP {cd['spk']} / LP {cd['lpk']} | "
              f"SC {cd['sck']} / LC {cd['lck']}  exp {cd['exp']}")
        return None
    req = MarketOrderRequest(qty=qty, order_class=OrderClass.MLEG,
                             time_in_force=TimeInForce.DAY, legs=_legs(cd, opening))
    res = trade.submit_order(req)
    print(f"  {action} submitted: order {res.id}")
    return res


# ── state + logging ───────────────────────────────────────────────────────────
def has_option_position(trade):
    """Broker-truth guard: prevents a second scheduled run from double-opening a condor."""
    try:
        return any("option" in str(getattr(p, "asset_class", "")).lower()
                   for p in trade.get_all_positions())
    except Exception:
        return False


def load_state():
    if C.STATE_FILE.exists():
        return json.loads(C.STATE_FILE.read_text())
    return None


def save_state(st):
    if st is None:
        C.STATE_FILE.exists() and C.STATE_FILE.unlink()
    else:
        C.STATE_FILE.write_text(json.dumps(st, indent=2))


def log(row):
    df = pd.DataFrame([row])
    df.to_csv(C.LOG_FILE, mode="a", header=not C.LOG_FILE.exists(), index=False)


# ── orchestration ─────────────────────────────────────────────────────────────
def main():
    trade, stock, opt = clients()
    acct = trade.get_account()
    equity = float(acct.equity)
    md = market_data(stock)
    state = load_state()
    today = date.today().isoformat()
    print(f"{today}  SPY {md['S']:.2f} | VIX {md['vix']:.1f} VIX3M {md['vix3m']:.1f} | "
          f"VRP {md['vrp']:.3f} (thr {md['vrp_thr']:.3f}) | contango={md['contango']} rich={md['rich']}")
    note = ""

    # 1) manage an open position
    if state:
        dte = (pd.Timestamp(state["exp"]).date() - date.today()).days
        if dte < 0:
            note = "expired-worthless"; save_state(None); state = None        # OTM expiry, $0 cost
        else:
            cur, _, _ = price_condor(opt, state)            # current cost-to-close (condor value)
            loss_stop = cur >= C.LOSS_STOP_MULT * state["credit"]
            near_exp = dte <= C.CLOSE_AT_DTE
            if loss_stop or near_exp:
                submit(trade, state, state["qty"], opening=False)
                note = "loss-stop-close" if loss_stop else "expiry-close"
                save_state(None); state = None
            else:
                note = f"hold (dte {dte}, value {cur:.2f} vs {C.LOSS_STOP_MULT}x credit {state['credit']:.2f})"

    # 2) open a new condor if flat and filters pass (broker guard blocks double-open on overlap)
    if state is None and md["passes"] and not has_option_position(trade):
        cd = pick_condor(trade, md)
        if cd:
            credit, width, legmids = price_condor(opt, cd)
            maxloss = width - credit
            if credit > 0 and maxloss > 0:
                qty = int(C.RISK_FRAC * equity / (maxloss * 100))
                if qty >= 1:
                    submit(trade, cd, qty, opening=True)
                    rec = {**cd, "qty": qty, "credit": round(credit, 2),
                           "maxloss": round(maxloss, 2), "entry": today}
                    if not C.DRY_RUN:
                        save_state(rec)
                    note = (note + " | " if note else "") + \
                           f"OPEN {qty}x credit {credit:.2f} maxloss {maxloss:.2f}"
                else:
                    note += " | skip: size<1 (credit too thin vs risk)"
            else:
                note += " | skip: non-positive credit/maxloss"
        else:
            note += " | skip: no suitable contracts"
    elif state is None and has_option_position(trade):
        note = (note + " | " if note else "") + "broker shows an option position; skip entry"
    elif state is None:
        note = (note + " | " if note else "") + "flat: filters not met"

    log(dict(date=today, equity=round(equity, 2), spy=md["S"], vix=md["vix"], vix3m=md["vix3m"],
             vrp=round(md["vrp"], 4), passes=md["passes"], dry_run=C.DRY_RUN, note=note))
    print(f"  -> {note}")


if __name__ == "__main__":
    main()
