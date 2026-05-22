"""Streamlit dashboard — reads CSV logs, optional live API calls via buttons."""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

from config import (
    ASSETS, BACKTEST_RESULTS, DAILY_LOG, QUARTERLY_BACKTEST,
    REGIME_LOG, RISK_FREE_RATE, SENTIMENT_LOG, WATCHLIST_ALERTS, WATCHLIST_LOG,
)

# ── Page config ────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Portfolio Bot",
    layout="wide",
    page_icon="📈",
    initial_sidebar_state="collapsed",
)

# Subtle styling
st.markdown("""
<style>
    .stMetric { background: #1e2330; padding: 12px 16px; border-radius: 8px; }
    .stMetric label { font-size: 0.75rem !important; opacity: 0.7; }
    .stMetric div[data-testid="stMetricValue"] { font-size: 1.5rem !important; }
    div[data-testid="stExpander"] { border: 1px solid #2a3142; border-radius: 8px; }
    h2 { padding-top: 1rem; }
</style>
""", unsafe_allow_html=True)

_STRATEGY_COLORS = {
    "MAX_SHARPE": "#4C72B0",
    "HRP": "#55A868",
    "HRP_MOMENTUM": "#C44E52",
    "SPY": "#8172B2",
}
_REGIME_DISPLAY = {
    "RISK_ON":  ("🟢", "Bull market — riding momentum"),
    "CHOPPY":   ("🟡", "Sideways market — balanced risk parity"),
    "RISK_OFF": ("🔴", "Defensive — heavy in cash & bonds"),
}


# ── Data loaders ───────────────────────────────────────────────────────────────

@st.cache_data(ttl=60)
def _load_csv(path: Path, parse_dates: list[str] | None = None) -> pd.DataFrame:
    if not Path(path).exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, parse_dates=parse_dates or [])
    except Exception:
        return pd.DataFrame()


def _load_daily() -> pd.DataFrame:
    df = _load_csv(DAILY_LOG, ["date"])
    if df.empty:
        return df
    return df.sort_values("date").reset_index(drop=True)


def _load_sentiment() -> pd.DataFrame:
    return _load_csv(SENTIMENT_LOG, ["timestamp"])


def _load_regime() -> pd.DataFrame:
    return _load_csv(REGIME_LOG, ["timestamp"])


def _load_watchlist() -> pd.DataFrame:
    return _load_csv(WATCHLIST_LOG, ["timestamp"])


def _load_alerts() -> pd.DataFrame:
    return _load_csv(WATCHLIST_ALERTS, ["timestamp"])


@st.cache_data(ttl=600)
def _load_quarterly() -> pd.DataFrame:
    p = Path(QUARTERLY_BACKTEST)
    if not p.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(p, index_col=0)
    except Exception:
        return pd.DataFrame()


def _parse_weights(raw) -> dict:
    """Robust weight parsing — handles JSON, Python literal, or already-parsed dict."""
    if isinstance(raw, dict):
        return raw
    if not raw or not isinstance(raw, str):
        return {}
    try:
        return json.loads(raw)
    except Exception:
        try:
            import ast
            return ast.literal_eval(raw)
        except Exception:
            return {}


def _latest_row(df: pd.DataFrame) -> dict:
    return {} if df.empty else df.iloc[-1].to_dict()


# ── Load everything once ───────────────────────────────────────────────────────

daily_df = _load_daily()
sentiment_df = _load_sentiment()
regime_df = _load_regime()
wl_df = _load_watchlist()
alerts_df = _load_alerts()
qdf = _load_quarterly()
latest = _latest_row(daily_df)


# ── Header ─────────────────────────────────────────────────────────────────────

st.title("📈 AI Portfolio Bot")

latest_regime = _latest_row(regime_df).get("regime", "—")
regime_emoji, regime_desc = _REGIME_DISPLAY.get(latest_regime, ("⚪", ""))

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Portfolio", f"${float(latest.get('portfolio_value', 0)):,.0f}" if latest else "—")
c2.metric("Sharpe", f"{float(latest.get('sharpe', 0)):.2f}" if latest else "—")
c3.metric("Exp. Return", f"{float(latest.get('expected_return', 0)):.1%}" if latest else "—")
c4.metric("Regime", f"{regime_emoji} {latest_regime}")
c5.metric("Last Run", str(latest.get("date", "—"))[:10] if latest else "—")

if regime_desc:
    st.caption(regime_desc)

st.divider()


# ── Section 1 — Current Holdings ───────────────────────────────────────────────

st.header("📊 Holdings")

if not latest:
    st.info("No data yet. Once the bot runs, your holdings will appear here.")
else:
    weights = {k: v for k, v in _parse_weights(latest.get("final_weights", "")).items() if v > 0.001}

    # Handle NaN/None notes properly — empty CSV cells come back as float('nan')
    raw_notes = latest.get("notes", "")
    if raw_notes is None or (isinstance(raw_notes, float) and pd.isna(raw_notes)):
        notes = ""
    else:
        notes = str(raw_notes).strip()
        if notes.lower() == "nan":
            notes = ""

    orders = int(latest.get("orders_placed", 0) or 0)
    strategy = str(latest.get("strategy", ""))

    # Status badge — priority order: breach > no_rebalance > orders > clean
    if "breach" in notes.lower() or "fail" in notes.lower() or "spike" in notes.lower():
        status_color, status_text = "warning", f"⚠️ Trades blocked — {notes}. Showing intended target weights."
    elif notes == "no_rebalance":
        status_color, status_text = "info", f"✓ Portfolio already on target — no rebalance needed today (Strategy: {strategy})"
    elif orders > 0:
        status_color, status_text = "success", f"✓ Rebalanced today — {orders} orders placed (Strategy: {strategy})"
    elif notes:
        status_color, status_text = "warning", f"⚠️ {notes}"
    else:
        status_color, status_text = "info", f"Strategy: {strategy}"

    getattr(st, status_color)(status_text)

    if weights:
        portfolio_val = float(latest.get("portfolio_value", 0))

        col_left, col_right = st.columns([1, 1.3])

        with col_left:
            fig_donut = go.Figure(go.Pie(
                labels=list(weights.keys()),
                values=[v * 100 for v in weights.values()],
                hole=0.55,
                textinfo="label+percent",
                textposition="outside",
                marker=dict(line=dict(color="#1e2330", width=2)),
            ))
            fig_donut.update_layout(
                height=360,
                showlegend=False,
                margin=dict(t=10, b=10, l=10, r=10),
                paper_bgcolor="rgba(0,0,0,0)",
            )
            st.plotly_chart(fig_donut, width="stretch")

        with col_right:
            rows = []
            for ticker, w in sorted(weights.items(), key=lambda x: -x[1]):
                sent_score = None
                if not sentiment_df.empty:
                    s = sentiment_df[sentiment_df["ticker"] == ticker].tail(1)
                    if not s.empty:
                        sent_score = float(s.iloc[0]["score"])
                rows.append({
                    "Asset": ticker,
                    "Target %": f"{w:.1%}",
                    "$ Value": f"${w * portfolio_val:,.0f}" if portfolio_val else "—",
                    "Sentiment": f"{sent_score:+.2f}" if sent_score is not None else "—",
                })
            df_holdings = pd.DataFrame(rows)
            st.dataframe(df_holdings, hide_index=True, width="stretch", height=360)

st.divider()


# ── Section 2 — Watchlist ──────────────────────────────────────────────────────

st.header("👀 Watchlist")

if wl_df.empty:
    st.info("No watchlist data yet.")
else:
    latest_wl = wl_df.sort_values("timestamp").drop_duplicates("ticker", keep="last")
    latest_wl = latest_wl.sort_values("today_pct", ascending=False)
    alert_tickers = set(alerts_df["ticker"].tolist()) if not alerts_df.empty else set()

    display = latest_wl[["ticker", "price", "today_pct", "mom_5d", "sentiment_score"]].copy()
    display["Status"] = display["ticker"].apply(lambda t: "🚨 ALERT" if t in alert_tickers else "✓ OK")
    display = display.rename(columns={
        "ticker": "Ticker", "price": "Price", "today_pct": "Today",
        "mom_5d": "5-Day", "sentiment_score": "Sentiment",
    })

    def _style_row(row):
        if "ALERT" in row["Status"]:
            return ["background-color: rgba(255, 193, 7, 0.15)"] * len(row)
        if row["Today"] > 0.05:
            return ["background-color: rgba(40, 167, 69, 0.10)"] * len(row)
        if row["Today"] < -0.05:
            return ["background-color: rgba(220, 53, 69, 0.10)"] * len(row)
        return [""] * len(row)

    styled = display.style.apply(_style_row, axis=1).format({
        "Price": "${:.2f}", "Today": "{:+.1%}", "5-Day": "{:+.1%}", "Sentiment": "{:+.2f}",
    })
    st.dataframe(styled, hide_index=True, width="stretch")

    if not alerts_df.empty:
        with st.expander(f"🚨 {len(alerts_df)} alert(s) — view reasons"):
            alerts_show = alerts_df.sort_values("timestamp", ascending=False).head(20)
            st.dataframe(alerts_show, hide_index=True, width="stretch")

st.divider()


# ── Section 3 — Equity Curve ───────────────────────────────────────────────────

st.header("📈 Performance vs SPY")

if daily_df.empty or "portfolio_value" not in daily_df.columns or len(daily_df) < 2:
    st.info("Equity curve will appear after a few days of data.")
else:
    daily_df["date"] = pd.to_datetime(daily_df["date"]).dt.normalize()
    first_val = daily_df["portfolio_value"].iloc[0]
    norm_port = daily_df["portfolio_value"] / first_val * 100

    fig_eq = go.Figure()
    fig_eq.add_trace(go.Scatter(
        x=daily_df["date"], y=norm_port, name="Your Portfolio",
        line=dict(color="#C44E52", width=2.5),
        fill="tozeroy", fillcolor="rgba(196, 78, 82, 0.1)",
    ))

    # SPY overlay using batch downloader (rate-limit safe)
    try:
        from data import fetch_prices_range
        spy_prices = fetch_prices_range(
            ["SPY"], daily_df["date"].min().to_pydatetime(), datetime.today()
        )
        if not spy_prices.empty and "SPY" in spy_prices.columns:
            spy_norm = spy_prices["SPY"] / spy_prices["SPY"].iloc[0] * 100
            fig_eq.add_trace(go.Scatter(
                x=spy_norm.index, y=spy_norm.values, name="SPY",
                line=dict(color="#8172B2", width=2, dash="dash"),
            ))
    except Exception:
        pass

    days = max((daily_df["date"].iloc[-1] - daily_df["date"].iloc[0]).days, 1)
    total_ret = norm_port.iloc[-1] / 100 - 1
    cagr = (norm_port.iloc[-1] / 100) ** (365.25 / days) - 1 if days > 0 else 0

    c1, c2 = st.columns(2)
    c1.metric("Total Return", f"{total_ret:+.2%}")
    c2.metric("Annualized (CAGR)", f"{cagr:+.2%}")

    fig_eq.update_layout(
        height=400, xaxis_title="", yaxis_title="Growth of $100",
        legend=dict(orientation="h", y=1.05, x=0),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(255,255,255,0.02)",
    )
    st.plotly_chart(fig_eq, width="stretch")

st.divider()


# ── Section 4 — Backtest Performance ──────────────────────────────────────────

st.header("🎯 Backtest — 2019 to Today")

if qdf.empty:
    st.info("Run `python3 backtest.py` to populate backtest data.")
else:
    strategies = [c for c in qdf.columns if c in ["MAX_SHARPE", "HRP", "HRP_MOMENTUM", "SPY"]]
    with st.expander("Quarterly Returns Chart", expanded=True):
        selected = st.multiselect(
            "Strategies",
            strategies,
            default=strategies,
            label_visibility="collapsed",
        )
        if selected:
            fig_q = go.Figure()
            for strat in selected:
                if strat in qdf.columns:
                    fig_q.add_trace(go.Bar(
                        name=strat,
                        x=qdf.index.tolist(),
                        y=(qdf[strat] * 100).tolist(),
                        marker_color=_STRATEGY_COLORS.get(strat),
                    ))
            fig_q.update_layout(
                barmode="group", height=420,
                xaxis_title="", yaxis_title="Quarterly Return (%)",
                legend=dict(orientation="h", y=1.05),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(255,255,255,0.02)",
            )
            st.plotly_chart(fig_q, width="stretch")

    # Win-rate summary
    if "SPY" in qdf.columns:
        win_cols = st.columns(3)
        for i, strat in enumerate(["MAX_SHARPE", "HRP", "HRP_MOMENTUM"]):
            if strat in qdf.columns:
                wins = (qdf[strat] > qdf["SPY"]).sum()
                total = len(qdf)
                win_cols[i].metric(
                    f"{strat} beat SPY",
                    f"{wins}/{total}",
                    f"{wins/total:.0%}",
                )

st.divider()


# ── Section 5 — Recent Activity ───────────────────────────────────────────────

st.header("📜 Recent Activity")

if daily_df.empty:
    st.info("No activity logged yet.")
else:
    recent = daily_df.tail(30).copy()
    recent["date"] = pd.to_datetime(recent["date"]).dt.date

    cols_to_show = ["date", "strategy", "regime", "portfolio_value", "sharpe", "orders_placed", "notes"]
    cols_present = [c for c in cols_to_show if c in recent.columns]
    display_recent = recent[cols_present].iloc[::-1]  # most recent first

    st.dataframe(
        display_recent,
        hide_index=True,
        width="stretch",
        column_config={
            "date": "Date",
            "strategy": "Strategy",
            "regime": "Regime",
            "portfolio_value": st.column_config.NumberColumn("Portfolio $", format="$%.0f"),
            "sharpe": st.column_config.NumberColumn("Sharpe", format="%.2f"),
            "orders_placed": st.column_config.NumberColumn("Orders", format="%d"),
            "notes": "Notes",
        },
    )

st.divider()


# ── Section 6 — Live Tools ────────────────────────────────────────────────────

st.header("🛠️ Live Tools")

tab1, tab2, tab3 = st.tabs(["Dry Run", "Force Rebalance", "Efficient Frontier"])

with tab1:
    st.markdown("**Test the optimizer without placing trades.**")
    strategy_choice = st.selectbox("Strategy", ["HRP_MOMENTUM", "HRP", "MAX_SHARPE"], key="dr_strat")

    if st.button("🔍 Run Optimizer", key="dr_btn"):
        with st.spinner("Optimizing…"):
            try:
                from data import fetch_prices, get_returns
                from optimizer import optimize
                from regime import detect_regime

                prices_dr = fetch_prices(list(set(ASSETS + ["SPY", "TLT"])), 252)
                returns_dr = get_returns(prices_dr[[c for c in ASSETS if c in prices_dr.columns]])
                regime_dr = detect_regime(prices_dr.get("SPY"), prices_dr.get("TLT"))
                result_dr = optimize(strategy=strategy_choice, returns=returns_dr, regime=regime_dr)

                m1, m2, m3 = st.columns(3)
                m1.metric("Regime", regime_dr)
                m2.metric("Sharpe", f"{result_dr['sharpe_ratio']:.2f}")
                m3.metric("Volatility", f"{result_dr['annual_volatility']:.1%}")

                weights_dr = {k: v for k, v in result_dr["weights"].items() if v > 0.001}
                df_dr = pd.DataFrame([
                    {"Asset": t, "Weight": f"{w:.1%}"}
                    for t, w in sorted(weights_dr.items(), key=lambda x: -x[1])
                ])
                st.dataframe(df_dr, hide_index=True, width="stretch")
            except Exception as exc:
                st.error(f"Optimizer failed: {exc}")

with tab2:
    st.warning("⚠️ This places real paper trades on Alpaca. Use only when needed.")
    confirm = st.checkbox("I want to force a rebalance now")
    if confirm and st.button("⚡ Run Full Pipeline", type="primary", key="fr_btn"):
        with st.spinner("Running pipeline — this takes ~1-2 minutes…"):
            try:
                import importlib
                import main as m
                importlib.reload(m)
                m.main()
                st.success("✓ Done — refresh the page to see updated logs.")
                st.cache_data.clear()
            except SystemExit:
                st.info("Market is closed — bot exited cleanly. Nothing was traded.")
            except Exception as exc:
                st.error(f"Pipeline error: {exc}")

with tab3:
    st.markdown("**Where your portfolio sits on the risk/return frontier.**")
    if st.button("Generate Frontier", key="ef_btn"):
        with st.spinner("Computing 3000 random portfolios…"):
            try:
                from data import fetch_prices, get_returns
                from scipy.optimize import minimize

                prices_ef = fetch_prices(ASSETS, 252)
                returns_ef = get_returns(prices_ef)
                mean_r = returns_ef.mean().values * 252
                cov_r = returns_ef.cov().values * 252

                sim_ret, sim_vol = [], []
                for _ in range(3000):
                    w = np.random.dirichlet(np.ones(len(mean_r)))
                    sim_ret.append(float(w @ mean_r))
                    sim_vol.append(float(np.sqrt(w @ cov_r @ w)))

                fig_ef = go.Figure()
                fig_ef.add_trace(go.Scatter(
                    x=sim_vol, y=sim_ret, mode="markers",
                    marker=dict(color="lightgrey", size=4, opacity=0.5),
                    name="Random portfolios", hoverinfo="skip",
                ))

                # Current portfolio
                if latest and latest.get("final_weights"):
                    cur_w_dict = _parse_weights(latest["final_weights"])
                    tickers_ef = returns_ef.columns.tolist()
                    cur_w = np.array([cur_w_dict.get(t, 0.0) for t in tickers_ef])
                    if cur_w.sum() > 0:
                        cur_w /= cur_w.sum()
                        cur_ret = float(cur_w @ mean_r)
                        cur_vol = float(np.sqrt(cur_w @ cov_r @ cur_w))
                        fig_ef.add_trace(go.Scatter(
                            x=[cur_vol], y=[cur_ret], mode="markers",
                            marker=dict(color="gold", size=20, symbol="star"),
                            name="Your portfolio",
                        ))

                # Min variance
                res_mv = minimize(
                    lambda w: float(np.sqrt(w @ cov_r @ w)),
                    x0=np.ones(len(mean_r)) / len(mean_r),
                    method="SLSQP",
                    bounds=[(0, 1)] * len(mean_r),
                    constraints=[{"type": "eq", "fun": lambda w: w.sum() - 1}],
                )
                fig_ef.add_trace(go.Scatter(
                    x=[float(np.sqrt(res_mv.x @ cov_r @ res_mv.x))],
                    y=[float(res_mv.x @ mean_r)],
                    mode="markers",
                    marker=dict(color="cyan", size=14, symbol="diamond"),
                    name="Min variance",
                ))

                fig_ef.update_layout(
                    height=500,
                    xaxis_title="Annual Volatility", yaxis_title="Expected Annual Return",
                    xaxis_tickformat=".0%", yaxis_tickformat=".0%",
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(255,255,255,0.02)",
                )
                st.plotly_chart(fig_ef, width="stretch")
            except Exception as exc:
                st.error(f"Frontier unavailable: {exc}")

st.divider()
st.caption("Built with Claude · Alpaca · Streamlit")
