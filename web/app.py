"""Trading desk — read-only web dashboard for the three PAPER books.

Reads only what the bots already write (CSV logs, the price caches, git history,
alerts.log, the local research ledger) and serves it as JSON to a static
front end in web/static/. It never places orders, never imports a broker
client, and never sends any .env value to the browser.

Run:   python3 web/app.py          ->  http://localhost:5050
Env:   PORT=5050                    port to bind (127.0.0.1 only)
       DESK_RESEARCH_DIR=...        override where research/experiments.md lives
       DESK_NO_GH=1                 skip the `gh run list` call on the Health page
"""

from __future__ import annotations

import json
import math
import os
import re
import subprocess
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
from flask import Flask, abort, jsonify, send_from_directory

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = Path(__file__).resolve().parent / "static"

CHAMP_LOG = BASE_DIR / "daily_log.csv"
CHAL_LOG = BASE_DIR / "challenger" / "daily_log.csv"
VOL_LOG = BASE_DIR / "volbot" / "volbot_log.csv"
VOL_TRADES = BASE_DIR / "volbot" / "volbot_trades.csv"
VOL_STATE = BASE_DIR / "volbot" / "volbot_state.json"
REGIME_LOG = BASE_DIR / "regime_log.csv"
META_LOG = BASE_DIR / "metabook" / "shadow_log.csv"
PRICE_CACHES = [BASE_DIR / "prices_cache.parquet",
                BASE_DIR / "challenger" / "live_prices.parquet"]
VERDICT = STATIC_DIR / "verdict.json"

CASH = "SHV"
TRADING_DAYS = 252

# NYSE full-day closures, so a holiday never shows up as a "missed" run.
NYSE_HOLIDAYS = {
    "2026-01-01", "2026-01-19", "2026-02-16", "2026-04-03", "2026-05-25",
    "2026-06-19", "2026-07-03", "2026-09-07", "2026-11-26", "2026-12-25",
    "2027-01-01", "2027-01-18", "2027-02-15", "2027-03-26", "2027-05-31",
    "2027-06-18", "2027-07-05", "2027-09-06", "2027-11-25", "2027-12-24",
}
# Last scheduled cron for each book (UTC hour). Before this hour a missing
# row for today is "scheduled", not "missed".
BOOKS = {
    "champion": {
        "name": "Champion",
        "desc": "Regime-switching HRP on 3x ETFs with a 20% vol-target overlay",
        "workflow": "Daily Portfolio Rebalance",
        "deadline_utc": 17,
        "verdict_key": "champion",
    },
    "challenger": {
        "name": "Challenger",
        "desc": "Three-sleeve diversified book, vol-targeted to 16%",
        "workflow": "Challenger Daily Rebalance",
        "deadline_utc": 17,
        "verdict_key": "challenger",
    },
    "volbot": {
        "name": "VolBot",
        "desc": "Laddered SPY/QQQ/IWM iron condors. Entries halted after EXP-010 failed",
        "workflow": "VolBot Daily",
        "deadline_utc": 17,
        "verdict_key": None,
    },
}

app = Flask(__name__, static_folder=str(STATIC_DIR), static_url_path="/static")


# ─────────────────────────────── helpers ────────────────────────────────────

def _r(x, n=4):
    """Round, mapping NaN/inf to None so the JSON stays valid."""
    if x is None:
        return None
    try:
        x = float(x)
    except (TypeError, ValueError):
        return None
    if math.isnan(x) or math.isinf(x):
        return None
    return round(x, n)


def _read_csv(path: Path, date_col: str = "date") -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        df = pd.read_csv(path)
    except Exception:
        return pd.DataFrame()
    if date_col in df.columns:
        df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
        df = df.dropna(subset=[date_col]).sort_values(date_col)
    return df


def _weights(raw) -> dict:
    if not isinstance(raw, str) or not raw.strip():
        return {}
    try:
        w = json.loads(raw)
        return {k: float(v) for k, v in w.items() if v is not None}
    except Exception:
        return {}


def _spy() -> pd.Series:
    """Daily SPY closes, merged from every local price cache the bots keep."""
    parts = []
    for p in PRICE_CACHES:
        if not p.exists():
            continue
        try:
            df = pd.read_parquet(p)
            if "SPY" in df.columns:
                s = df["SPY"].dropna()
                s.index = pd.to_datetime(s.index).tz_localize(None).normalize()
                parts.append(s)
        except Exception:
            continue
    if not parts:
        return pd.Series(dtype=float)
    s = pd.concat(parts)
    return s[~s.index.duplicated(keep="first")].sort_index()


def _is_trading_day(d: date) -> bool:
    return d.weekday() < 5 and d.isoformat() not in NYSE_HOLIDAYS


def _prev_trading_day(d: date) -> date:
    d -= timedelta(days=1)
    while not _is_trading_day(d):
        d -= timedelta(days=1)
    return d


_gh_cache: dict = {"t": 0.0, "runs": None, "err": None}


def _gh_runs():
    """Recent GitHub Actions runs via the local `gh` CLI, cached 2 minutes.

    Returns (runs, error). The token stays inside gh; nothing about it is
    passed to the browser."""
    if os.getenv("DESK_NO_GH"):
        return None, "disabled (DESK_NO_GH)"
    if time.time() - _gh_cache["t"] < 120:
        return _gh_cache["runs"], _gh_cache["err"]
    runs, err = None, None
    try:
        out = subprocess.run(
            ["gh", "run", "list", "-L", "40", "--json",
             "workflowName,status,conclusion,event,createdAt,updatedAt,headSha,displayTitle,url,databaseId"],
            cwd=BASE_DIR, capture_output=True, text=True, timeout=12)
        if out.returncode == 0:
            runs = json.loads(out.stdout or "[]")
        else:
            err = (out.stderr or "gh failed").strip().splitlines()[-1][:200]
    except FileNotFoundError:
        err = "gh CLI not installed"
    except Exception as e:  # timeout, bad json
        err = type(e).__name__
    _gh_cache.update(t=time.time(), runs=runs, err=err)
    return runs, err


# ─────────────────────────────── book series ────────────────────────────────

def _equity_frame(book: str) -> pd.DataFrame:
    """date + equity (one row per date, last write wins, bad rows dropped)."""
    if book == "champion":
        df = _read_csv(CHAMP_LOG)
        if df.empty:
            return df
        df = df.rename(columns={"portfolio_value": "equity"})
    elif book == "challenger":
        df = _read_csv(CHAL_LOG)
    elif book == "volbot":
        df = _read_csv(VOL_LOG)
    else:
        return pd.DataFrame()
    if df.empty or "equity" not in df.columns:
        return pd.DataFrame()
    df["equity"] = pd.to_numeric(df["equity"], errors="coerce")
    # A paper account is never worth $0; those rows are broker timeouts.
    df = df[df["equity"] > 0]
    return df.drop_duplicates(subset="date", keep="last").reset_index(drop=True)


def _stats(eq: pd.Series, dates: pd.Series, spy: pd.Series) -> dict:
    vals = eq.astype(float).to_numpy()
    n = len(vals)
    if n == 0:
        return {}
    rets = pd.Series(vals).pct_change().dropna()
    peak = pd.Series(vals).cummax()
    dd = pd.Series(vals) / peak - 1
    vol = rets.std() * math.sqrt(TRADING_DAYS) if len(rets) > 2 else None
    sharpe = (rets.mean() / rets.std() * math.sqrt(TRADING_DAYS)
              if len(rets) > 2 and rets.std() > 0 else None)
    total = vals[-1] / vals[0] - 1
    spy_ret = None
    if len(spy):
        s0 = spy[spy.index <= dates.iloc[0]]
        s1 = spy[spy.index <= dates.iloc[-1]]
        if len(s0) and len(s1):
            spy_ret = float(s1.iloc[-1] / s0.iloc[-1] - 1)
    day = vals[-1] - vals[-2] if n >= 2 else None
    day_pct = vals[-1] / vals[-2] - 1 if n >= 2 else None
    return {
        "equity": _r(vals[-1], 2),
        "start_equity": _r(vals[0], 2),
        "total_return": _r(total),
        "spy_return": _r(spy_ret),
        "vs_spy": _r(total - spy_ret) if spy_ret is not None else None,
        "day_pnl": _r(day, 2),
        "day_pct": _r(day_pct, 5),
        "drawdown": _r(dd.iloc[-1]),
        "max_drawdown": _r(dd.min()),
        "sharpe": _r(sharpe, 2),
        "vol": _r(vol),
        "obs": n,
        "start": dates.iloc[0].strftime("%Y-%m-%d"),
        "last": dates.iloc[-1].strftime("%Y-%m-%d"),
    }


def _series(df: pd.DataFrame, spy: pd.Series) -> list[dict]:
    """Equity + SPY close aligned on the book's own dates (SPY forward-filled)."""
    out = []
    peak = 0.0
    for d, e in zip(df["date"], df["equity"]):
        peak = max(peak, float(e))
        sv = None
        if len(spy):
            prior = spy[spy.index <= d]
            if len(prior):
                sv = float(prior.iloc[-1])
        out.append({"d": d.strftime("%Y-%m-%d"), "eq": _r(e, 2), "spy": _r(sv, 3),
                    "dd": _r(float(e) / peak - 1 if peak else 0)})
    return out


def _run_status(book: str, last: str | None, runs) -> dict:
    now = datetime.now(timezone.utc)
    today = now.date()
    cfg = BOOKS[book]
    wf_runs = [r for r in (runs or []) if r.get("workflowName") == cfg["workflow"]]
    latest = wf_runs[0] if wf_runs else None
    last_d = date.fromisoformat(last) if last else None

    if _is_trading_day(today):
        expected = today if now.hour >= cfg["deadline_utc"] else _prev_trading_day(today)
    else:
        expected = _prev_trading_day(today)

    pending_today = _is_trading_day(today) and (not last_d or last_d < today) \
        and now.hour < cfg["deadline_utc"]
    if last_d and last_d >= today:
        state, label = "ran", "Ran today"
    elif last_d and last_d >= expected:
        state, label = "ran", f"Ran {last_d:%b} {last_d.day}"
    else:
        state, label = "missed", f"Missed {expected:%b} {expected.day}"

    # A failed latest run overrides a quiet log (the log only shows success).
    if latest and latest.get("conclusion") == "failure":
        state, label = "failed", "Last run failed"

    gh = None
    if latest:
        gh = {"status": latest.get("status"), "conclusion": latest.get("conclusion"),
              "at": latest.get("createdAt"), "url": latest.get("url"),
              "event": latest.get("event")}
    return {"state": state, "label": label, "last_log": last, "pending_today": pending_today,
            "workflow": cfg["workflow"],
            "fails_recent": sum(1 for r in wf_runs if r.get("conclusion") == "failure"),
            "expected": expected.isoformat(), "gh": gh}


def _book_summary(book: str, spy: pd.Series, runs) -> dict:
    df = _equity_frame(book)
    cfg = BOOKS[book]
    base = {"id": book, "name": cfg["name"], "desc": cfg["desc"]}
    if df.empty:
        base.update(stats={}, series=[], status=_run_status(book, None, runs))
        return base
    st = _stats(df["equity"], df["date"], spy)
    # Stretches with no log rows (e.g. the Jun 24 - Jul 24 log-commit bug).
    # Charts join across them, so name them rather than let a flat line lie.
    d = df["date"].tolist()
    gaps = [{"from": a.strftime("%Y-%m-%d"), "to": b.strftime("%Y-%m-%d"),
             "missing": int(sum(1 for x in pd.bdate_range(a, b)[1:-1]
                                if x.strftime("%Y-%m-%d") not in NYSE_HOLIDAYS))}
            for a, b in zip(d, d[1:]) if (b - a).days > 6]
    base.update(stats=st, series=_series(df, spy), gaps=gaps,
                status=_run_status(book, st["last"], runs))
    return base


# ─────────────────────────────── positions ──────────────────────────────────

def _weights_history(df: pd.DataFrame, col: str, top_n: int = 6):
    """Weights over time collapsed to the top-N symbols + Other + Cash.

    Ranking is by average weight over the whole history, so a symbol's
    colour stays fixed whatever the selected window."""
    rows = [(d, _weights(w)) for d, w in zip(df["date"], df[col])]
    rows = [(d, w) for d, w in rows if w]
    if not rows:
        return {"symbols": [], "rows": [], "current": [], "turnover": []}
    avg: dict[str, float] = {}
    for _, w in rows:
        for k, v in w.items():
            if k != CASH:
                avg[k] = avg.get(k, 0.0) + max(v, 0.0) / len(rows)
    top = [k for k, _ in sorted(avg.items(), key=lambda x: -x[1])[:top_n]]
    symbols = top + ["Other", "Cash"]

    out, turnover, prev = [], [], None
    for d, w in rows:
        tot = sum(max(v, 0.0) for v in w.values()) or 1.0
        norm = {k: max(v, 0.0) / tot for k, v in w.items()}
        r = {s: 0.0 for s in symbols}
        for k, v in norm.items():
            if k == CASH:
                r["Cash"] += v
            elif k in top:
                r[k] += v
            else:
                r["Other"] += v
        r["Cash"] += max(0.0, 1.0 - sum(norm.values()))
        out.append({"d": d.strftime("%Y-%m-%d"), **{k: _r(v) for k, v in r.items()}})
        if prev is not None:
            keys = set(prev) | set(norm)
            t = 0.5 * sum(abs(norm.get(k, 0) - prev.get(k, 0)) for k in keys)
            turnover.append({"d": d.strftime("%Y-%m-%d"), "v": _r(t)})
        prev = norm

    last = rows[-1][1]
    tot = sum(max(v, 0.0) for v in last.values()) or 1.0
    current = sorted(({"sym": k, "w": _r(max(v, 0.0) / tot)} for k, v in last.items()
                      if max(v, 0.0) / tot >= 0.001), key=lambda x: -x["w"])
    return {"symbols": symbols, "rows": out, "current": current, "turnover": turnover,
            "as_of": rows[-1][0].strftime("%Y-%m-%d")}


def _rebalance_log(df: pd.DataFrame, col: str, orders_col: str, notes_col: str = "notes"):
    """Days the book actually traded, with the biggest weight moves."""
    events, prev = [], None
    for _, row in df.iterrows():
        w = _weights(row.get(col))
        if not w:
            continue
        tot = sum(max(v, 0.0) for v in w.values()) or 1.0
        norm = {k: max(v, 0.0) / tot for k, v in w.items()}
        orders = row.get(orders_col)
        try:
            orders = int(orders) if pd.notna(orders) else 0
        except (TypeError, ValueError):
            orders = 0
        if prev is not None and orders > 0:
            keys = set(prev) | set(norm)
            moves = sorted(((k, norm.get(k, 0) - prev.get(k, 0)) for k in keys),
                           key=lambda x: -abs(x[1]))
            moves = [{"sym": k, "dw": _r(v)} for k, v in moves if abs(v) >= 0.005][:4]
            events.append({
                "d": row["date"].strftime("%Y-%m-%d"),
                "orders": orders,
                "turnover": _r(0.5 * sum(abs(norm.get(k, 0) - prev.get(k, 0)) for k in keys)),
                "moves": moves,
                "note": str(row.get(notes_col)) if pd.notna(row.get(notes_col)) else "",
            })
        prev = norm
    return list(reversed(events))


def _champion_detail(spy):
    df = _read_csv(CHAMP_LOG)
    df = df[pd.to_numeric(df["portfolio_value"], errors="coerce") > 0]
    df = df.drop_duplicates(subset="date", keep="last").reset_index(drop=True)
    wh = _weights_history(df, "final_weights")
    exposure = [{"d": r["d"], "v": _r(1 - (r.get("Cash") or 0))} for r in wh["rows"]]
    ml = []
    for d, n in zip(df["date"], df.get("notes", pd.Series(dtype=str))):
        m = re.search(r"would_mult=([\d.]+)", str(n))
        if m:
            ml.append({"d": d.strftime("%Y-%m-%d"), "v": _r(float(m.group(1)))})
    regime = [{"d": d.strftime("%Y-%m-%d"), "regime": str(r), "strategy": str(s)}
              for d, r, s in zip(df["date"], df["regime"], df["strategy"])]
    signals = None
    rl = _read_csv(REGIME_LOG, "timestamp")
    if not rl.empty:
        last = rl.iloc[-1]
        signals = {"at": last["timestamp"].strftime("%Y-%m-%d %H:%M"),
                   "regime": last["regime"], "vol": last["vol_signal"],
                   "trend": last["trend_signal"], "flight": last["flight_signal"]}
    latest = df.iloc[-1]
    return {
        "weights": wh,
        "overlay": {"label": "Gross exposure (1 − cash sleeve)", "series": exposure,
                    "target_note": "Vol-target overlay scales the risky book toward 20% annual vol; the remainder sits in SHV.",
                    "ml_shadow": ml},
        "regime": {"series": regime, "signals": signals,
                   "current": str(latest["regime"]), "strategy": str(latest["strategy"])},
        "rebalances": _rebalance_log(df, "final_weights", "orders_placed"),
        "model": {"exp_return": _r(latest.get("expected_return")),
                  "exp_vol": _r(latest.get("annual_vol")),
                  "exp_sharpe": _r(latest.get("sharpe"), 2)},
    }


def _challenger_detail(spy):
    df = _equity_frame("challenger")
    wh = _weights_history(df, "weights", top_n=6)
    scaler = [{"d": d.strftime("%Y-%m-%d"), "v": _r(v)} for d, v in zip(df["date"], df["vol_scaler"])]
    est = [{"d": d.strftime("%Y-%m-%d"), "v": _r(v)} for d, v in zip(df["date"], df["est_vol"])]
    latest = df.iloc[-1]
    return {
        "weights": wh,
        "overlay": {"label": "Vol scaler (target 16% annual vol)", "series": scaler,
                    "est_vol": est,
                    "target_note": "Scaler = min(1, 16% / estimated vol). Below 1.0 the book holds SHV."},
        "regime": None,
        "rebalances": _rebalance_log(df, "weights", "orders"),
        "model": {"exp_vol": _r(latest.get("est_vol")), "scaler": _r(latest.get("vol_scaler"))},
    }


def _volbot_detail(spy):
    df = _equity_frame("volbot")
    trades = _read_csv(VOL_TRADES, "exit_date")
    tl = []
    if not trades.empty:
        for _, t in trades.iloc[::-1].iterrows():
            tl.append({
                "exit": t["exit_date"].strftime("%Y-%m-%d"), "entry": str(t["entry_date"])[:10],
                "u": t["u"], "exp": str(t["exp"])[:10], "qty": int(t["qty"]),
                "strikes": f'{t["lpk"]:g}/{t["spk"]:g} · {t["sck"]:g}/{t["lck"]:g}',
                "credit": _r(t["credit"], 2), "exit_cost": _r(t["exit_cost"], 2),
                "pnl": _r(t["realized_pnl"], 2), "pct": _r(t["pct_of_credit"], 1),
                "reason": t["reason"], "slip": _r(t["entry_slip"], 2)})
    iv = [{"d": d.strftime("%Y-%m-%d"), "SPY": _r(a, 1), "QQQ": _r(b, 1), "IWM": _r(c, 1)}
          for d, a, b, c in zip(df["date"], df["spy_iv"], df["qqq_iv"], df["iwm_iv"])]
    # at_risk is logged in dollars (sum of max loss over open rungs); show it
    # as a fraction of equity so it reads against the 25% cap.
    at_risk = [{"d": d.strftime("%Y-%m-%d"),
                "v": _r((float(v) if pd.notna(v) else 0.0) / float(e)),
                "usd": _r(v, 0), "rungs": int(r) if pd.notna(r) else 0}
               for d, v, e, r in zip(df["date"], df["at_risk"], df["equity"], df["rungs"])]
    state = {}
    if VOL_STATE.exists():
        try:
            state = json.loads(VOL_STATE.read_text())
        except Exception:
            state = {}
    latest = df.iloc[-1]
    realized = sum(t["pnl"] or 0 for t in tl)
    wins = sum(1 for t in tl if (t["pnl"] or 0) > 0)
    return {
        "trades": tl,
        "trade_stats": {"n": len(tl), "wins": wins, "realized": _r(realized, 2)},
        "iv": iv,
        "overlay": {"label": "Capital at risk (fraction of equity)", "series": at_risk,
                    "target_note": "Cap: 3% per rung, 25% total. Zero while entries are halted."},
        "state": {"open_rungs": len(state.get("rungs", [])), "rungs": state.get("rungs", []),
                  "last_entry": state.get("last_entry", {})},
        "note": str(latest.get("note", "")),
        "flags": {"contango": bool(latest.get("contango")) if pd.notna(latest.get("contango")) else None,
                  "rich": {u: bool(latest.get(f"{u.lower()}_rich")) if pd.notna(latest.get(f"{u.lower()}_rich")) else None
                           for u in ("SPY", "QQQ", "IWM")}},
    }


def _verdict(key):
    if not key or not VERDICT.exists():
        return None
    try:
        v = json.loads(VERDICT.read_text())
        b = v["books"].get(key)
        if not b:
            return None
        keep = ("name", "years", "cagr", "vol", "sharpe", "sharpe_ci95", "k_trials", "dsr",
                "maxdd", "maxdd_date", "sufficiency", "beta", "alpha_ann")
        out = {k: b.get(k) for k in keep}
        mc = b.get("monte_carlo", {})
        out["p_dd20_1yr"] = mc.get("p_dd20_1yr")
        out["p_neg_1yr"] = mc.get("p_neg_1yr")
        out["p_beat_bench_1yr"] = b.get("p_beat_bench_1yr")
        out["generated"] = v.get("generated")
        return out
    except Exception:
        return None


# ─────────────────────────────── research ledger ────────────────────────────

def _research_path() -> Path | None:
    cands = []
    if os.getenv("DESK_RESEARCH_DIR"):
        cands.append(Path(os.getenv("DESK_RESEARCH_DIR")) / "experiments.md")
    cands.append(BASE_DIR / "research" / "experiments.md")
    # research/ is gitignored, so inside a git worktree it only exists in the
    # main checkout. Find that via the shared git dir.
    try:
        common = subprocess.run(["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
                                cwd=BASE_DIR, capture_output=True, text=True, timeout=5).stdout.strip()
        if common:
            cands.append(Path(common).parent / "research" / "experiments.md")
    except Exception:
        pass
    for c in cands:
        if c.exists():
            return c
    return None


def _clean_md(s: str) -> str:
    s = re.sub(r"~~.*?~~", "", s, flags=re.S)
    s = s.replace("**", "").replace("`", "")
    return re.sub(r"\s+", " ", s).strip()


FAIL_RE = re.compile(r"\b(KILL|KILLED|FAIL|FAILED|FAILS|STOPPED|UNREPLICATED|CLOSED)\b|does not survive", re.I)
PASS_RE = re.compile(r"\b(PASS|PASSED|PASSES)\b")
INC_RE = re.compile(r"\b(INCONCLUSIVE|UNDERPOWERED|PILOT ONLY|pending)\b", re.I)


def _classify(text: str) -> str:
    """Status from the decisive verdict text. A kill anywhere is a FAIL even if
    a premise gate passed first — a confirmed premise is not a working trade."""
    t = text
    if FAIL_RE.search(t):
        return "FAIL"
    if PASS_RE.search(t):
        return "PASS"
    if INC_RE.search(t):
        return "INCONCLUSIVE"
    return "PRE-REGISTERED"


def _parse_experiments(md: str) -> list[dict]:
    blocks = re.split(r"(?m)^## ", md)
    out = []
    for b in blocks[1:]:
        head, _, body = b.partition("\n")
        m = re.match(r"((?:EXP-\w+)|(?:C\d+))\s*[—-]+\s*(.*)", head.strip())
        if not m or m.group(1) == "EXP-NNN":
            continue
        eid, title = m.group(1), _clean_md(m.group(2))
        lines = body.splitlines()

        # Status paragraph: from **Status:** to the next blank line / bold field.
        status = ""
        for i, ln in enumerate(lines):
            if ln.startswith("**Status:**"):
                buf = [ln[len("**Status:**"):]]
                for nxt in lines[i + 1:]:
                    if not nxt.strip() or re.match(r"\*\*\w[\w\s-]*:\*\*", nxt) or nxt.startswith("#"):
                        break
                    buf.append(nxt)
                status = _clean_md(" ".join(buf))
                break

        # Decisive lines: result headers and bold verdict lines. "### Overall
        # verdict" sections are decision rules written in advance, so skip them.
        result_hdr = re.compile(r"###\s+(?:PART \w+ |PHASE \d+ )?(RESULT|Result)\b")
        verdict_lines = [ln for ln in lines
                         if result_hdr.match(ln) or re.match(r"\*\*(VERDICT|Verdict)\b", ln)]
        verdict_text = " ".join(_clean_md(v) for v in verdict_lines)
        has_result = any(result_hdr.match(ln) for ln in lines)

        def para_after(i, strip=None):
            """Paragraph starting at line i (optionally minus a lead-in)."""
            buf = [re.sub(strip, "", lines[i]) if strip else lines[i]]
            for nxt in lines[i + 1:]:
                if not nxt.strip() or nxt.startswith(("#", "|", "- ", "1. ")):
                    break
                buf.append(nxt)
            return _clean_md(" ".join(buf))

        key = ""
        for pat in (r"^\*\*One-line lesson[^*]*:\*\*", r"^\*\*Binding constraint:\*\*",
                    r"^\*\*(?:VERDICT|Verdict):?\s*"):
            hit = [i for i, ln in enumerate(lines) if re.match(pat, ln)]
            if hit:
                key = para_after(hit[0], pat)
                if key:
                    break
        if not key and has_result:
            idx = max(i for i, ln in enumerate(lines) if result_hdr.match(ln))
            for j in range(idx + 1, min(idx + 8, len(lines))):
                if lines[j].strip() and not lines[j].startswith(("|", "#")):
                    key = para_after(j)
                    break
        if not key:
            hit = [i for i, ln in enumerate(lines) if re.match(r"###\s+Hypothesis", ln)]
            if hit:
                for j in range(hit[0] + 1, min(hit[0] + 6, len(lines))):
                    if lines[j].strip():
                        key = para_after(j)
                        break
        if not key:
            key = status
        # A bare "Data:/Full record:" paragraph is provenance, not a finding;
        # the result header line says more.
        if re.match(r"(Data|Full record|Ran exactly|Result files)\b", key) and has_result:
            hdr = [ln for ln in lines if result_hdr.match(ln)][-1]
            key = _clean_md(re.sub(r"^###\s+", "", hdr))
        key = re.sub(r"^(RUN|Run)\s+\d{4}-\d{2}-\d{2}\s*·\s*", "", key)
        key = key[:1].upper() + key[1:]

        verdict = _classify(status + " " + verdict_text) if (status or verdict_text) else "PRE-REGISTERED"
        if verdict == "PRE-REGISTERED" and has_result:
            verdict = "MEASURED"
        dates = re.findall(r"\d{4}-\d{2}-\d{2}", status)
        km = re.search(r"K\s*=\s*\d+|K spent: \d+", status)
        out.append({
            "id": eid, "title": title, "status": verdict, "status_text": status,
            "key": key[:460] + ("…" if len(key) > 460 else ""),
            "registered": dates[0] if dates else None,
            "last_date": dates[-1] if dates else None,
            "k": km.group(0) if km else None,
            "premise_passed": bool(re.search(r"PART A PASS|BOTH GATES PASS|premise (itself )?confirmed", status + verdict_text, re.I)) and verdict == "FAIL",
        })

    def sort_key(e):
        n = re.search(r"(\d+)", e["id"])
        return (0 if e["id"].startswith("EXP") else 1, int(n.group(1)) if n else 0, e["id"])
    return sorted(out, key=sort_key)


# ─────────────────────────────── health ─────────────────────────────────────

def _alerts_path() -> Path | None:
    for p in [BASE_DIR / "alerts.log"]:
        if p.exists():
            return p
    try:
        common = subprocess.run(["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
                                cwd=BASE_DIR, capture_output=True, text=True, timeout=5).stdout.strip()
        p = Path(common).parent / "alerts.log"
        if p.exists():
            return p
    except Exception:
        pass
    return None


def _alerts(limit=15):
    p = _alerts_path()
    if not p:
        return None, []
    rows = []
    for ln in p.read_text(errors="replace").splitlines():
        ts, sep, msg = ln.partition(" | ")
        if not sep:
            continue
        cat, _, rest = msg.partition(":")
        if not rest or len(cat) > 40:
            cat, rest = "Alert", msg
        sev = "critical" if re.search(r"circuit breaker|breach|failed|error", msg, re.I) else "warning"
        rows.append({"at": ts[:19], "category": cat.strip(), "msg": rest.strip()[:300], "severity": sev})
    return str(p), list(reversed(rows))[:limit]


def _commits(n=12):
    try:
        out = subprocess.run(["git", "log", f"-{n}", "--format=%h%x1f%an%x1f%cI%x1f%s"],
                             cwd=BASE_DIR, capture_output=True, text=True, timeout=5).stdout
    except Exception:
        return []
    rows = []
    for ln in out.splitlines():
        parts = ln.split("\x1f")
        if len(parts) == 4:
            h, a, t, s = parts
            rows.append({"sha": h, "author": a, "at": t, "subject": s,
                         "bot": "[bot]" in a})
    return rows


def _freshness():
    files = [("Champion log", CHAMP_LOG, "date"), ("Challenger log", CHAL_LOG, "date"),
             ("VolBot log", VOL_LOG, "date"), ("VolBot trades", VOL_TRADES, "exit_date"),
             ("Regime log", REGIME_LOG, "timestamp"), ("Meta-book shadow", META_LOG, "date")]
    out = []
    for label, p, col in files:
        if not p.exists():
            out.append({"label": label, "path": str(p.relative_to(BASE_DIR)), "exists": False})
            continue
        df = _read_csv(p, col)
        last = df[col].max() if not df.empty and col in df.columns else None
        out.append({"label": label, "path": str(p.relative_to(BASE_DIR)), "exists": True,
                    "rows": len(df), "last": last.strftime("%Y-%m-%d") if last is not None else None,
                    "mtime": datetime.fromtimestamp(p.stat().st_mtime, timezone.utc).isoformat()})
    return out


# ─────────────────────────────── routes ─────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory(STATIC_DIR, "index.html")


@app.after_request
def no_cache(resp):
    if resp.mimetype == "application/json":
        resp.headers["Cache-Control"] = "no-store"
    return resp


@app.route("/api/desk")
def api_desk():
    spy = _spy()
    runs, gh_err = _gh_runs()
    books = [_book_summary(b, spy, runs) for b in BOOKS]
    meta = None
    mdf = _read_csv(META_LOG)
    if not mdf.empty:
        last = mdf.iloc[-1]
        meta = {"d": last["date"].strftime("%Y-%m-%d"), "obs_days": int(last["obs_days"]),
                "weights": {"champion": _r(last["w_CHAMP"], 3), "challenger": _r(last["w_CHALL"], 3),
                            "volbot": _r(last["w_VOLBOT"], 3)},
                "note": str(last.get("note", "")) if pd.notna(last.get("note")) else ""}
    exp_path = _research_path()
    research = None
    if exp_path:
        ex = _parse_experiments(exp_path.read_text(errors="replace"))
        research = {s: sum(1 for e in ex if e["status"] == s)
                    for s in ("PASS", "FAIL", "INCONCLUSIVE", "MEASURED", "PRE-REGISTERED")}
        research["total"] = len(ex)
        research["latest"] = [{k: e[k] for k in ("id", "title", "status", "key", "last_date")}
                              for e in sorted(ex, key=lambda e: e["last_date"] or "", reverse=True)[:3]]
    _, alerts = _alerts(limit=1000)
    cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%d")
    return jsonify({
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "books": books, "meta": meta, "research": research,
        "alerts_30d": sum(1 for a in alerts if a["at"][:10] >= cutoff),
        "spy_last": spy.index[-1].strftime("%Y-%m-%d") if len(spy) else None,
        "gh_error": gh_err,
    })


@app.route("/api/book/<book>")
def api_book(book):
    if book not in BOOKS:
        abort(404)
    spy = _spy()
    runs, _ = _gh_runs()
    summary = _book_summary(book, spy, runs)
    try:
        detail = {"champion": _champion_detail, "challenger": _challenger_detail,
                  "volbot": _volbot_detail}[book](spy)
    except Exception as e:  # a malformed log should degrade, not 500 the page
        detail = {"error": f"{type(e).__name__}: {e}"}
    summary.update(detail=detail, verdict=_verdict(BOOKS[book]["verdict_key"]))
    return jsonify(summary)


@app.route("/api/research")
def api_research():
    p = _research_path()
    if not p:
        return jsonify({"available": False, "experiments": [],
                        "hint": "research/experiments.md is gitignored and not present here. "
                                "Set DESK_RESEARCH_DIR to the folder that holds it."})
    ex = _parse_experiments(p.read_text(errors="replace"))
    return jsonify({"available": True, "source": str(p),
                    "modified": datetime.fromtimestamp(p.stat().st_mtime, timezone.utc).isoformat(),
                    "experiments": ex})


@app.route("/api/health")
def api_health():
    runs, err = _gh_runs()
    path, alerts = _alerts()
    return jsonify({
        "runs": [{k: r.get(k) for k in ("workflowName", "status", "conclusion", "event",
                                         "createdAt", "updatedAt", "displayTitle", "url")}
                 for r in (runs or [])],
        "runs_error": err,
        "commits": _commits(),
        "alerts": alerts, "alerts_path": path,
        "freshness": _freshness(),
    })


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5050"))
    print(f"\n  Trading desk (read-only, paper) -> http://localhost:{port}\n")
    app.run(host="127.0.0.1", port=port, debug=False)
