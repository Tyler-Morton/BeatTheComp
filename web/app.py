"""Portfolio Bot - public showcase page (read-only).

This is a SEPARATE web page from the bot itself. It only READS the CSV files
the bot writes plus the cached SPY prices, and asks Alpaca for the current
account value. It never places trades, never touches main.py, and never changes
any bot state.

Run it with:   python3 web/app.py
Then open:     http://localhost:5050

The bot's normal GitHub Actions cron is completely unaffected by this.
"""

import bisect
import json
import os
import sys
from pathlib import Path

from flask import Flask, jsonify, send_from_directory

# Make the bot's modules importable (broker) since we live in web/.
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from dotenv import load_dotenv
load_dotenv(BASE_DIR / ".env")   # load Alpaca keys from the project's .env

import pandas as pd

STATIC_DIR = Path(__file__).resolve().parent / "static"
DAILY_LOG = BASE_DIR / "daily_log.csv"
PRICE_CACHE = BASE_DIR / "prices_cache.parquet"
CHAL_LOG = BASE_DIR / "challenger" / "daily_log.csv"

app = Flask(__name__, static_folder=str(STATIC_DIR))


# ── Validated research numbers (from your backtests + ROADMAP, not live) ─────────
# These are real, out-of-sample results, kept here as the single source of truth.
BACKTEST = {
    "dsr": 99.4,          # Deflated Sharpe Ratio: probability the edge is real
    "sharpe": 0.89,       # annualized backtest Sharpe (best config, 11 tested)
    "vol_reduction": 53,  # % volatility cut by the vol-targeting overlay
    "max_dd": -24,        # max drawdown WITH the overlay (vs -71% without)
    "max_dd_raw": -71,    # max drawdown of the raw 3x book
    "target_vol": 20,     # the overlay's annual vol target (%)
}

# The Numerai model is a DIFFERENT system from the trading bot. Kept separate
# on purpose so the two never get conflated.
NUMERAI = {
    "corr": 0.0208,
    "sharpe": 1.24,
    "fnc": 0.0200,
}

REGIME_LABELS = {
    "RISK_ON": "Bull",
    "CHOPPY": "Sideways",
    "RISK_OFF": "Defensive",
}

YTD_START = pd.Timestamp("2026-01-02")   # first trading day of the year


def _read_daily() -> pd.DataFrame:
    if not DAILY_LOG.exists():
        return pd.DataFrame()
    try:
        df = pd.read_csv(DAILY_LOG, parse_dates=["date"])
        df = df.sort_values("date")
        # Drop broker-timeout artifacts: a live account can never be worth $0, so a
        # zero/negative value is a bad data point (Alpaca returned $0 on a timeout
        # and the drawdown breaker logged a false -100%). Ignore those rows.
        df = df[df["portfolio_value"].astype(float) > 0]
        # One row per date (the last run of that day) so the curve is clean.
        return df.drop_duplicates(subset="date", keep="last").reset_index(drop=True)
    except Exception:
        return pd.DataFrame()


def _spy_series() -> "pd.Series | None":
    """Daily SPY closes from the bot's own price cache, or None if unavailable."""
    if not PRICE_CACHE.exists():
        return None
    try:
        df = pd.read_parquet(PRICE_CACHE)
        if "SPY" not in df.columns:
            return None
        spy = df["SPY"].dropna()
        spy.index = pd.to_datetime(spy.index)
        return spy.sort_index()
    except Exception:
        return None


def _live_snapshot():
    """Current Alpaca account value, or None if the broker can't be reached."""
    try:
        from broker import get_live_snapshot
        return get_live_snapshot()
    except Exception:
        return None


# Real, out-of-sample backtest results for the challenger (challenger/backtest.py,
# Tiingo 2007-2026). Single source of truth for the page.
CHAL_BACKTEST = {"sharpe": 0.65, "spy_sharpe": 0.39, "vol": 12.1, "max_dd": -24,
                 "spy_max_dd": -55, "target_vol": 16}
CHAL_START_EQUITY = 1000.0


def _challenger_equity():
    """Live equity of the SECOND (challenger) paper account, read-only.

    Uses its own TradingClient with the challenger keys; never touches the
    champion's broker singleton."""
    key = os.getenv("CHALLENGER_ALPACA_API_KEY")
    sec = os.getenv("CHALLENGER_ALPACA_SECRET_KEY")
    if not key or not sec:
        return None
    try:
        from alpaca.trading.client import TradingClient
        acct = TradingClient(key, sec, paper=True).get_account()
        return float(acct.equity)
    except Exception:
        return None


def _challenger_data():
    """Daily equity points + summary stats for the challenger section."""
    points: dict[str, float] = {}
    if CHAL_LOG.exists():
        try:
            df = pd.read_csv(CHAL_LOG, parse_dates=["date"])
            df = df[df["equity"].astype(float) > 0]
            df = df.sort_values("date").drop_duplicates(subset="date", keep="last")
            points = {d.strftime("%Y-%m-%d"): float(e)
                      for d, e in zip(df["date"], df["equity"])}
        except Exception:
            points = {}

    live = _challenger_equity()
    today = pd.Timestamp.now().strftime("%Y-%m-%d")
    if live:
        points[max(points) if points and max(points) > today else today] = live
    if not points:
        if live is None:
            return None
        points = {today: live}

    dates = sorted(points)
    equity = points[dates[-1]]
    total_return = (equity / CHAL_START_EQUITY - 1) * 100
    return {
        "equity": round(equity, 2),
        "total_return": round(total_return, 2),
        "started": dates[0],
        "days": len(dates),
        "is_live": live is not None,
        "points": {d: round(v, 2) for d, v in points.items()},
        "backtest": CHAL_BACKTEST,
    }


def _build_chart(daily: pd.DataFrame, live_equity: float):
    """Daily portfolio-vs-SPY series, from the first trading day of the year.

    Before the bot launched, the portfolio line sits flat at its starting value
    (the cash that was waiting to be deployed). SPY is the raw daily close; the
    front end rebases both lines to a common $1,000 start per selected window.
    """
    if daily.empty:
        return {"inception": None, "series": []}

    launch = daily["date"].iloc[0]
    start_val = float(daily["portfolio_value"].iloc[0])   # ~1000 at launch
    last_date = daily["date"].iloc[-1]

    port_map = dict(zip(daily["date"], daily["portfolio_value"].astype(float)))
    if live_equity:
        port_map[last_date] = float(live_equity)   # pin the tip to the live value
    pdates = sorted(port_map)

    spy = _spy_series()

    # Backbone = real trading days from Jan 2 to the latest portfolio date.
    if spy is not None:
        days = [d for d in spy.index if YTD_START <= d <= last_date]
    else:
        days = [d for d in pdates if d >= YTD_START]
    if last_date not in days:
        days.append(last_date)
    days = sorted(set(days))

    series = []
    for d in days:
        if d < launch:
            pv = start_val                       # flat cash baseline pre-launch
        else:
            idx = bisect.bisect_right(pdates, d) - 1
            pv = port_map[pdates[idx]] if idx >= 0 else start_val
        sv = None
        if spy is not None:
            prior = spy[spy.index <= d]
            if len(prior):
                sv = float(prior.iloc[-1])
        series.append({
            "date": d.strftime("%Y-%m-%d"),
            "port": round(pv, 2),
            "spy": round(sv, 4) if sv is not None else None,
        })

    return {"inception": launch.strftime("%Y-%m-%d"), "series": series}


def _metrics(daily: pd.DataFrame, live_equity: float, chart: dict, cash_pct):
    """Honest, since-inception live stats computed from the daily log."""
    if daily.empty:
        return {}

    vals = daily["portfolio_value"].astype(float).tolist()
    dates = daily["date"].tolist()
    if live_equity and vals:
        vals[-1] = float(live_equity)

    rets = [vals[i] / vals[i - 1] - 1 for i in range(1, len(vals)) if vals[i - 1]]
    total_return = (vals[-1] / vals[0] - 1) * 100 if vals and vals[0] else 0.0
    best = max(rets) * 100 if rets else 0.0
    worst = min(rets) * 100 if rets else 0.0
    win_rate = (sum(1 for r in rets if r > 0) / len(rets) * 100) if rets else 0.0
    days_live = (dates[-1] - dates[0]).days if len(dates) >= 2 else 0
    rebalances = int((daily.get("orders_placed", pd.Series(dtype=float)).fillna(0) > 0).sum())

    # SPY over the same since-inception window, from the chart series.
    spy_return = None
    alpha = None
    inception = chart.get("inception")
    post = [s for s in chart.get("series", []) if inception and s["date"] >= inception and s["spy"]]
    if len(post) >= 2 and post[0]["spy"]:
        spy_return = (post[-1]["spy"] / post[0]["spy"] - 1) * 100
        alpha = total_return - spy_return

    return {
        "total_return": round(total_return, 2),
        "spy_return": round(spy_return, 2) if spy_return is not None else None,
        "alpha": round(alpha, 2) if alpha is not None else None,
        "best_day": round(best, 2),
        "worst_day": round(worst, 2),
        "win_rate": round(win_rate, 0),
        "days_live": days_live,
        "rebalances": rebalances,
        "cash_pct": round(cash_pct, 0) if cash_pct is not None else None,
    }


@app.route("/")
def index():
    return send_from_directory(STATIC_DIR, "index.html")


@app.route("/api/stats")
def stats():
    daily = _read_daily()
    live = _live_snapshot()
    latest = daily.iloc[-1].to_dict() if not daily.empty else {}

    # ── Portfolio value: prefer the real-time Alpaca number, fall back to CSV ──
    if live and live.get("equity"):
        equity = float(live["equity"])
        last_equity = float(live.get("last_equity") or 0)
        is_live = True
    else:
        equity = float(latest.get("portfolio_value", 0) or 0)
        last_equity = float(daily.iloc[-2]["portfolio_value"]) if len(daily) >= 2 else 0.0
        is_live = False

    if last_equity:
        day_change = equity - last_equity
        day_change_pct = (equity / last_equity - 1) * 100
    else:
        day_change = day_change_pct = 0.0

    regime = str(latest.get("regime", "RISK_ON"))

    # ── Current holdings + cash sleeve ────────────────────────────────────────
    # Prefer live Alpaca positions; if the broker is unreachable, fall back to the
    # latest target weights from the daily log so the page always shows something.
    positions = []
    cash_pct = None
    if live and live.get("positions"):
        for sym, p in sorted(live["positions"].items(), key=lambda x: -x[1]["weight"]):
            if p["weight"] > 0.005:
                positions.append({
                    "symbol": sym,
                    "weight": round(p["weight"] * 100, 1),
                    "value": round(p["market_value"], 2),
                })
        shv = live["positions"].get("SHV", {})
        if shv:
            cash_pct = shv.get("weight", 0) * 100
    elif latest.get("final_weights"):
        try:
            raw = latest["final_weights"]
            fw = json.loads(raw) if isinstance(raw, str) else dict(raw)
        except Exception:
            fw = {}
        for sym, w in sorted(fw.items(), key=lambda x: -x[1]):
            if w and w > 0.005:
                positions.append({
                    "symbol": sym,
                    "weight": round(w * 100, 1),
                    "value": round(w * equity, 2),
                })
        if fw.get("SHV"):
            cash_pct = fw["SHV"] * 100

    chart = _build_chart(daily, equity if is_live else None)
    metrics = _metrics(daily, equity if is_live else None, chart, cash_pct)

    # ── Challenger: annotate the chart series + build its summary block ───────
    chal = _challenger_data()
    if chal:
        pts = chal.pop("points")
        cdates = sorted(pts)
        start = cdates[0]
        last_val = None
        for s in chart.get("series", []):
            if s["date"] < start:
                s["chal"] = None
            else:
                prior = [d for d in cdates if d <= s["date"]]
                last_val = pts[prior[-1]] if prior else last_val
                s["chal"] = last_val
        # make sure the newest challenger point lands on the chart even if the
        # champion's log hasn't caught up to that date yet
        if chart.get("series") and cdates[-1] > chart["series"][-1]["date"]:
            chart["series"].append({"date": cdates[-1], "port": chart["series"][-1]["port"],
                                    "spy": chart["series"][-1]["spy"], "chal": pts[cdates[-1]]})

    return jsonify({
        "is_live": is_live,
        "equity": round(equity, 2),
        "day_change": round(day_change, 2),
        "day_change_pct": round(day_change_pct, 2),
        "regime": regime,
        "regime_label": REGIME_LABELS.get(regime, regime),
        "last_run": str(latest.get("date", ""))[:10],
        "trading_days": len(daily),
        "chart": chart,
        "metrics": metrics,
        "positions": positions,
        "challenger": chal,
        "backtest": BACKTEST,
        "numerai": NUMERAI,
    })


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5050"))
    print("\n  Portfolio Bot showcase page")
    print(f"  -> http://localhost:{port}\n")
    print("  (read-only: this does not touch your bot or place any trades)\n")
    app.run(host="127.0.0.1", port=port, debug=False)
