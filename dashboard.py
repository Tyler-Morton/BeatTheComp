"""Streamlit dashboard — reads CSV logs, optional live API calls via buttons."""

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

st.set_page_config(page_title="Portfolio Bot", layout="wide", page_icon="📈")

_STRATEGY_COLORS = {
    "MAX_SHARPE": "#4C72B0",
    "HRP": "#55A868",
    "HRP_MOMENTUM": "#C44E52",
    "SPY": "#8172B2",
}
_REGIME_COLORS = {"RISK_ON": "🟢", "CHOPPY": "🟡", "RISK_OFF": "🔴"}


# ── Data loaders ───────────────────────────────────────────────────────────────

@st.cache_data(ttl=60)
def _load_daily() -> pd.DataFrame:
    p = Path(DAILY_LOG)
    if not p.exists():
        return pd.DataFrame()
    df = pd.read_csv(p, parse_dates=["date"])
    return df.sort_values("date")


@st.cache_data(ttl=60)
def _load_sentiment() -> pd.DataFrame:
    p = Path(SENTIMENT_LOG)
    if not p.exists():
        return pd.DataFrame()
    return pd.read_csv(p, parse_dates=["timestamp"])


@st.cache_data(ttl=60)
def _load_regime() -> pd.DataFrame:
    p = Path(REGIME_LOG)
    if not p.exists():
        return pd.DataFrame()
    return pd.read_csv(p, parse_dates=["timestamp"])


@st.cache_data(ttl=60)
def _load_watchlist() -> pd.DataFrame:
    p = Path(WATCHLIST_LOG)
    if not p.exists():
        return pd.DataFrame()
    return pd.read_csv(p, parse_dates=["timestamp"])


@st.cache_data(ttl=60)
def _load_alerts() -> pd.DataFrame:
    p = Path(WATCHLIST_ALERTS)
    if not p.exists():
        return pd.DataFrame()
    return pd.read_csv(p, parse_dates=["timestamp"])


@st.cache_data(ttl=300)
def _load_quarterly() -> pd.DataFrame:
    p = Path(QUARTERLY_BACKTEST)
    if not p.exists():
        return pd.DataFrame()
    return pd.read_csv(p, index_col=0)


def _latest_row(df: pd.DataFrame) -> dict:
    if df.empty:
        return {}
    return df.iloc[-1].to_dict()


# ── Header ─────────────────────────────────────────────────────────────────────

st.title("📈 AI Portfolio Optimization Bot")
st.caption("Powered by Claude Haiku · Alpaca · HRP Momentum Strategy")

daily_df = _load_daily()
latest = _latest_row(daily_df)
regime_df = _load_regime()
latest_regime = _latest_row(regime_df).get("regime", "—")
regime_icon = _REGIME_COLORS.get(latest_regime, "⚪")

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Portfolio Value", f"${float(latest.get('portfolio_value', 0)):,.0f}" if latest else "—")
c2.metric("Sharpe Ratio", f"{float(latest.get('sharpe', 0)):.2f}" if latest else "—")
c3.metric("Expected Return", f"{float(latest.get('expected_return', 0)):.1%}" if latest else "—")
c4.metric(f"Regime {regime_icon}", latest_regime)
c5.metric("Last Rebalance", str(latest.get("date", "—"))[:10] if latest else "—")

st.divider()

# ── Section 1 — Portfolio Allocations ─────────────────────────────────────────

st.subheader("1 · Portfolio Allocations")

if latest and "final_weights" in latest and latest["final_weights"]:
    try:
        import ast
        weights_raw = latest["final_weights"]
        weights: dict = ast.literal_eval(weights_raw) if isinstance(weights_raw, str) else weights_raw
        sentiment_df = _load_sentiment()

        fig_donut = go.Figure(go.Pie(
            labels=list(weights.keys()),
            values=[v * 100 for v in weights.values()],
            hole=0.45,
            textinfo="label+percent",
        ))
        fig_donut.update_layout(height=350, showlegend=False, margin=dict(t=20, b=20))
        st.plotly_chart(fig_donut)

        # Weight table
        rows = []
        for ticker, w in weights.items():
            sent_score = "—"
            if not sentiment_df.empty:
                s = sentiment_df[sentiment_df["ticker"] == ticker].tail(1)
                if not s.empty:
                    sent_score = f"{float(s.iloc[0]['score']):.2f}"
            rows.append({"Asset": ticker, "Sentiment": sent_score,
                         "Target %": f"{w:.1%}", "Drift": "—", "$Value": "—"})
        st.dataframe(pd.DataFrame(rows), hide_index=True)
    except Exception:
        st.info("Weight data not yet available.")
else:
    st.info("No allocation data yet. Run main.py to generate.")

st.divider()

# ── Section 2 — Watchlist Alerts ──────────────────────────────────────────────

st.subheader("2 · Watchlist Alerts")
alerts_df = _load_alerts()
wl_df = _load_watchlist()

if not wl_df.empty:
    latest_wl = wl_df.sort_values("timestamp").drop_duplicates("ticker", keep="last")
    latest_wl = latest_wl.sort_values("today_pct", ascending=False)
    alert_tickers = set(alerts_df["ticker"].tolist()) if not alerts_df.empty else set()

    display = latest_wl[["ticker", "price", "today_pct", "mom_5d", "sentiment_score"]].copy()
    display["Status"] = display["ticker"].apply(lambda t: "🚨 ALERT" if t in alert_tickers else "OK")

    def _color_row(row):
        if row["Status"] == "🚨 ALERT":
            return ["background-color: #fff3cd"] * len(row)
        if row["today_pct"] > 0.05:
            return ["background-color: #d4edda"] * len(row)
        if row["today_pct"] < -0.05:
            return ["background-color: #f8d7da"] * len(row)
        return [""] * len(row)

    styled = display.style.apply(_color_row, axis=1).format({
        "price": "${:.2f}", "today_pct": "{:.1%}", "mom_5d": "{:.1%}", "sentiment_score": "{:.2f}",
    })
    st.dataframe(styled, hide_index=True)

    if not alerts_df.empty:
        st.warning(f"⚠️ {len(alerts_df)} active alerts today")
        st.dataframe(
            alerts_df.sort_values("timestamp", ascending=False).head(20),
            use_container_width=True, hide_index=True,
        )
else:
    st.info("No watchlist data yet.")

st.divider()

# ── Section 3 — Equity Curve ──────────────────────────────────────────────────

st.subheader("3 · Equity Curve vs SPY")

if not daily_df.empty and "portfolio_value" in daily_df.columns:
    first_val = daily_df["portfolio_value"].iloc[0]
    norm_port = daily_df["portfolio_value"] / first_val * 100

    fig_eq = go.Figure()
    fig_eq.add_trace(go.Scatter(x=daily_df["date"], y=norm_port, name="Portfolio",
                                 line=dict(color="#C44E52", width=2)))

    # SPY overlay from yfinance if available
    try:
        import yfinance as yf
        start_d = daily_df["date"].min()
        spy_raw = yf.download("SPY", start=start_d, auto_adjust=True, progress=False, multi_level_index=False)
        if not spy_raw.empty:
            spy_norm = spy_raw["Close"] / spy_raw["Close"].iloc[0] * 100
            fig_eq.add_trace(go.Scatter(x=spy_norm.index, y=spy_norm.values, name="SPY",
                                         line=dict(color="#8172B2", width=2, dash="dash")))
    except Exception:
        pass

    cagr = ((norm_port.iloc[-1] / 100) ** (365.25 / max((daily_df["date"].iloc[-1] - daily_df["date"].iloc[0]).days, 1)) - 1) if len(norm_port) > 1 else 0
    st.caption(f"Portfolio CAGR ≈ {cagr:.1%} since first run")
    fig_eq.update_layout(height=400, xaxis_title="Date", yaxis_title="Growth of $100",
                          legend=dict(orientation="h", y=1.02))
    st.plotly_chart(fig_eq)
else:
    st.info("No equity history yet.")

st.divider()

# ── Section 4 — Quarterly Performance ────────────────────────────────────────

st.subheader("4 · Quarterly Backtest Performance")
qdf = _load_quarterly()

if not qdf.empty:
    strategies = [c for c in qdf.columns if c in ["MAX_SHARPE", "HRP", "HRP_MOMENTUM", "SPY"]]
    selected = st.multiselect("Strategies to display", strategies, default=strategies)

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
            barmode="group", height=450,
            xaxis_title="Quarter", yaxis_title="Return (%)",
            legend=dict(orientation="h", y=1.02),
        )
        st.plotly_chart(fig_q)
else:
    st.info("Run backtest.py to populate quarterly data.")

st.divider()

# ── Section 5 — Market Condition Breakdown ────────────────────────────────────

st.subheader("5 · Market Condition Breakdown")

if not qdf.empty and not regime_df.empty:
    regime_col: list[str] = []
    for q_str in qdf.index:
        try:
            q_end = pd.Period(q_str, "Q").end_time
            diffs = abs(pd.to_datetime(regime_df["timestamp"]) - q_end)
            nearest_idx = diffs.idxmin()
            regime_col.append(regime_df.loc[nearest_idx, "regime"])
        except Exception:
            regime_col.append("CHOPPY")

    qdf_r = qdf.copy()
    qdf_r["Regime"] = regime_col if len(regime_col) == len(qdf_r) else "CHOPPY"

    strat_cols = [c for c in qdf.columns if c != "SPY"]
    records = []
    for _, row in qdf_r.iterrows():
        for strat in strat_cols:
            spy_ret = row.get("SPY", 0.0)
            records.append({
                "Regime": row["Regime"], "Strategy": strat,
                "Avg Return": row.get(strat, 0.0) * 100,
                "Beat SPY": 1 if row.get(strat, 0.0) > spy_ret else 0,
            })
    df_cond = pd.DataFrame(records)
    pivot = df_cond.groupby(["Regime", "Strategy"])["Avg Return"].mean().unstack()
    fig_heat = px.imshow(pivot, text_auto=".1f", color_continuous_scale="RdYlGn",
                          color_continuous_midpoint=0, title="Avg Quarterly Return by Regime (%)")
    st.plotly_chart(fig_heat)
else:
    st.info("Backtest and regime data needed for this section.")

st.divider()

# ── Section 6 — Efficient Frontier ───────────────────────────────────────────

st.subheader("6 · Efficient Frontier")

with st.spinner("Generating frontier…"):
    try:
        from data import fetch_prices, get_returns
        prices_ef = fetch_prices(ASSETS, 252)
        returns_ef = get_returns(prices_ef)
        mean_r = returns_ef.mean().values * 252
        cov_r = returns_ef.cov().values * 252
        n_assets = len(ASSETS[:len(mean_r)])

        n_sim = 3000
        sim_ret, sim_vol = [], []
        for _ in range(n_sim):
            w = np.random.dirichlet(np.ones(len(mean_r)))
            sim_ret.append(float(w @ mean_r))
            sim_vol.append(float(np.sqrt(w @ cov_r @ w)))

        fig_ef = go.Figure()
        fig_ef.add_trace(go.Scatter(x=sim_vol, y=sim_ret, mode="markers",
                                     marker=dict(color="lightgrey", size=3), name="Random portfolios"))

        # Current portfolio
        if latest and "final_weights" in latest and latest["final_weights"]:
            try:
                import ast
                cur_w_dict = ast.literal_eval(latest["final_weights"]) if isinstance(latest["final_weights"], str) else latest["final_weights"]
                tickers_ef = returns_ef.columns.tolist()
                cur_w = np.array([cur_w_dict.get(t, 0.0) for t in tickers_ef])
                cur_w /= cur_w.sum() if cur_w.sum() > 0 else 1
                cur_ret = float(cur_w @ mean_r)
                cur_vol = float(np.sqrt(cur_w @ cov_r @ cur_w))
                fig_ef.add_trace(go.Scatter(x=[cur_vol], y=[cur_ret], mode="markers",
                                             marker=dict(color="gold", size=16, symbol="star"),
                                             name="Current portfolio"))
            except Exception:
                pass

        # Min variance
        from scipy.optimize import minimize
        res_mv = minimize(
            lambda w: float(np.sqrt(w @ cov_r @ w)),
            x0=np.ones(len(mean_r)) / len(mean_r),
            method="SLSQP",
            bounds=[(0, 1)] * len(mean_r),
            constraints=[{"type": "eq", "fun": lambda w: w.sum() - 1}],
        )
        mv_vol = float(np.sqrt(res_mv.x @ cov_r @ res_mv.x))
        mv_ret = float(res_mv.x @ mean_r)
        fig_ef.add_trace(go.Scatter(x=[mv_vol], y=[mv_ret], mode="markers",
                                     marker=dict(color="blue", size=12, symbol="circle"),
                                     name="Min variance"))

        fig_ef.update_layout(height=450, xaxis_title="Annual Volatility",
                              yaxis_title="Expected Annual Return",
                              xaxis_tickformat=".0%", yaxis_tickformat=".0%")
        st.plotly_chart(fig_ef)
    except Exception as exc:
        st.warning(f"Efficient frontier unavailable: {exc}")

st.divider()

# ── Section 7 — Rebalance Log ─────────────────────────────────────────────────

st.subheader("7 · Rebalance Log (Last 30 Days)")

if not daily_df.empty:
    cutoff = pd.Timestamp.today() - pd.Timedelta(days=30)
    recent = daily_df[daily_df["date"] >= cutoff] if "date" in daily_df.columns else daily_df.tail(30)

    if not recent.empty and "sharpe" in recent.columns:
        # Sharpe over time
        fig_sh = go.Figure()
        fig_sh.add_trace(go.Scatter(
            x=recent["date"], y=recent["sharpe"].astype(float),
            fill="tozeroy", line=dict(color="#4C72B0"), name="Sharpe",
        ))
        fig_sh.update_layout(height=300, xaxis_title="Date", yaxis_title="Sharpe Ratio")
        st.plotly_chart(fig_sh)

    st.dataframe(
        recent[["date", "strategy", "regime", "portfolio_value", "sharpe", "orders_placed"]].tail(30),
        use_container_width=True, hide_index=True,
    )
else:
    st.info("No daily log data yet.")

st.divider()

# ── Section 8 — Controls ──────────────────────────────────────────────────────

st.subheader("8 · Controls")

col_ctrl1, col_ctrl2 = st.columns(2)

with col_ctrl1:
    st.markdown("**Strategy**")
    strategy_choice = st.selectbox("Active strategy", ["HRP_MOMENTUM", "HRP", "MAX_SHARPE"])
    rf_rate = st.slider("Risk-free rate", 0.0, 0.10, RISK_FREE_RATE, 0.005, format="%.3f")

    if st.button("🔍 Dry Run Optimizer (no trades)"):
        with st.spinner("Running optimizer…"):
            try:
                import importlib
                import config as cfg
                cfg.RISK_FREE_RATE = rf_rate  # live update for this run
                from data import fetch_prices, get_returns
                from optimizer import optimize
                from regime import detect_regime

                prices_dr = fetch_prices(ASSETS, 252)
                returns_dr = get_returns(prices_dr)
                regime_dr = detect_regime(prices_dr.get("SPY"), prices_dr.get("TLT"))
                result_dr = optimize(strategy=strategy_choice, returns=returns_dr, regime=regime_dr)

                st.success(f"Regime: {regime_dr} | Sharpe: {result_dr['sharpe_ratio']:.2f} | "
                           f"Vol: {result_dr['annual_volatility']:.1%}")
                st.json(result_dr["weights"])
            except Exception as exc:
                st.error(f"Optimizer error: {exc}")

with col_ctrl2:
    st.markdown("**Actions**")
    if st.button("⚡ Force Rebalance NOW"):
        st.warning("This will place real/paper trades. Are you sure?")
        if st.button("✅ Confirm Rebalance"):
            with st.spinner("Running full pipeline…"):
                try:
                    import main as m
                    m.main()
                    st.success("Rebalance complete. Refresh to see updated logs.")
                except Exception as exc:
                    st.error(f"Pipeline error: {exc}")
