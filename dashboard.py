"""Portfolio Bot Dashboard — fintech dark mode, Inter typography, polished UI."""

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


# ── Design tokens (Fintech Dark Mode OLED) ─────────────────────────────────────

COLOR = {
    # Surfaces
    "bg":         "#0a0e1a",     # deep navy-black background
    "surface":    "#131829",     # raised card surface
    "surface_2":  "#1a2238",     # higher elevation (hover, modals)
    "border":     "#1f2a44",     # subtle separators
    "border_2":   "#2a3658",     # stronger borders for focus

    # Text
    "text":       "#f1f5f9",     # primary high-contrast
    "text_2":     "#94a3b8",     # secondary muted
    "text_3":     "#64748b",     # tertiary captions

    # Brand
    "primary":    "#3b82f6",     # bright blue (data lines, links)
    "primary_2":  "#60a5fa",     # lighter blue (hover)
    "accent":     "#f59e0b",     # amber (highlights, alerts)

    # Semantic (financial)
    "success":    "#10b981",     # gain / bullish
    "success_2":  "#34d399",
    "danger":     "#ef4444",     # loss / bearish
    "danger_2":   "#f87171",
    "warning":    "#fbbf24",     # caution
    "info":       "#06b6d4",     # neutral info

    # Regime
    "risk_on":    "#10b981",
    "choppy":     "#fbbf24",
    "risk_off":   "#ef4444",
}

# Plotly theme
PLOTLY_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Inter, system-ui, sans-serif", color=COLOR["text"], size=12),
    margin=dict(l=10, r=10, t=10, b=10),
    xaxis=dict(gridcolor=COLOR["border"], zerolinecolor=COLOR["border"], color=COLOR["text_2"]),
    yaxis=dict(gridcolor=COLOR["border"], zerolinecolor=COLOR["border"], color=COLOR["text_2"]),
    legend=dict(
        bgcolor="rgba(19,24,41,0.6)",
        bordercolor=COLOR["border"],
        borderwidth=1,
        font=dict(color=COLOR["text_2"], size=11),
    ),
    hoverlabel=dict(
        bgcolor=COLOR["surface_2"],
        bordercolor=COLOR["border_2"],
        font=dict(family="Inter, system-ui, sans-serif", color=COLOR["text"]),
    ),
)


# ── Global CSS — Inter font + dark theme + polish ──────────────────────────────

st.markdown(f"""
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">

<style>
    /* Global font */
    html, body, [class*="css"], .stApp, .stMarkdown, .stText, button, input, textarea, select {{
        font-family: 'Inter', system-ui, -apple-system, sans-serif !important;
        -webkit-font-smoothing: antialiased;
        font-feature-settings: 'cv11', 'ss01', 'ss03';
    }}

    /* Background — true OLED dark */
    .stApp {{
        background: {COLOR['bg']};
    }}

    /* Hide Streamlit chrome */
    #MainMenu, footer, header[data-testid="stHeader"] {{ visibility: hidden; }}

    /* Container — wider feel */
    .block-container {{
        max-width: 1440px;
        padding-top: 1.5rem !important;
        padding-bottom: 4rem !important;
    }}

    /* Typography hierarchy */
    h1 {{
        font-weight: 700 !important;
        font-size: 1.875rem !important;
        letter-spacing: -0.02em !important;
        color: {COLOR['text']} !important;
        margin-bottom: 0.25rem !important;
    }}
    h2 {{
        font-weight: 600 !important;
        font-size: 1.125rem !important;
        letter-spacing: -0.01em !important;
        color: {COLOR['text']} !important;
        margin: 1.5rem 0 0.75rem 0 !important;
        padding-top: 0.5rem !important;
    }}
    h3 {{
        font-weight: 600 !important;
        font-size: 1rem !important;
        color: {COLOR['text_2']} !important;
    }}

    .stCaption, [data-testid="stCaptionContainer"] {{
        color: {COLOR['text_3']} !important;
        font-size: 0.75rem !important;
        letter-spacing: 0.02em !important;
    }}

    /* Metric cards — dark surface, subtle border */
    [data-testid="stMetric"] {{
        background: {COLOR['surface']};
        border: 1px solid {COLOR['border']};
        border-radius: 12px;
        padding: 1rem 1.25rem !important;
        transition: border-color 200ms ease, transform 200ms ease;
    }}
    [data-testid="stMetric"]:hover {{
        border-color: {COLOR['border_2']};
    }}
    [data-testid="stMetricLabel"] {{
        font-size: 0.6875rem !important;
        font-weight: 500 !important;
        letter-spacing: 0.06em !important;
        text-transform: uppercase !important;
        color: {COLOR['text_3']} !important;
    }}
    [data-testid="stMetricValue"] {{
        font-size: 1.625rem !important;
        font-weight: 600 !important;
        font-variant-numeric: tabular-nums !important;
        font-feature-settings: 'tnum';
        color: {COLOR['text']} !important;
        line-height: 1.1 !important;
        margin-top: 0.25rem !important;
    }}
    [data-testid="stMetricDelta"] {{
        font-size: 0.8125rem !important;
        font-weight: 500 !important;
        font-variant-numeric: tabular-nums !important;
    }}

    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {{
        gap: 0.25rem;
        border-bottom: 1px solid {COLOR['border']};
        background: transparent;
    }}
    .stTabs [data-baseweb="tab"] {{
        background: transparent !important;
        border-radius: 8px 8px 0 0 !important;
        color: {COLOR['text_2']} !important;
        font-weight: 500 !important;
        padding: 0.5rem 1rem !important;
    }}
    .stTabs [data-baseweb="tab"][aria-selected="true"] {{
        color: {COLOR['primary_2']} !important;
        border-bottom: 2px solid {COLOR['primary']} !important;
        background: rgba(59, 130, 246, 0.08) !important;
    }}

    /* Dataframe / tables */
    [data-testid="stDataFrame"] {{
        border: 1px solid {COLOR['border']};
        border-radius: 12px;
        overflow: hidden;
    }}

    /* Buttons */
    .stButton button {{
        background: {COLOR['primary']} !important;
        color: white !important;
        border: none !important;
        border-radius: 8px !important;
        font-weight: 500 !important;
        padding: 0.5rem 1rem !important;
        transition: background-color 200ms ease, transform 100ms ease !important;
    }}
    .stButton button:hover {{
        background: {COLOR['primary_2']} !important;
    }}
    .stButton button:active {{
        transform: scale(0.98);
    }}

    /* Alerts */
    [data-testid="stAlert"] {{
        border-radius: 10px !important;
        border-width: 1px !important;
        font-size: 0.875rem !important;
    }}

    /* Dividers — make them subtle */
    hr {{
        border-color: {COLOR['border']} !important;
        margin: 1.5rem 0 !important;
        opacity: 0.6;
    }}

    /* Plotly chart container */
    .js-plotly-plot {{
        background: {COLOR['surface']} !important;
        border: 1px solid {COLOR['border']};
        border-radius: 12px;
        padding: 0.75rem;
    }}

    /* Section card wrapper helper */
    .section-card {{
        background: {COLOR['surface']};
        border: 1px solid {COLOR['border']};
        border-radius: 12px;
        padding: 1.25rem;
        margin-bottom: 1rem;
    }}

    /* Status badge */
    .status-badge {{
        display: inline-flex;
        align-items: center;
        gap: 0.5rem;
        padding: 0.375rem 0.75rem;
        border-radius: 999px;
        font-size: 0.75rem;
        font-weight: 500;
        letter-spacing: 0.02em;
    }}
    .badge-success {{ background: rgba(16,185,129,0.15); color: {COLOR['success_2']}; border: 1px solid rgba(16,185,129,0.3); }}
    .badge-warning {{ background: rgba(245,158,11,0.15); color: {COLOR['accent']}; border: 1px solid rgba(245,158,11,0.3); }}
    .badge-danger  {{ background: rgba(239,68,68,0.15); color: {COLOR['danger_2']}; border: 1px solid rgba(239,68,68,0.3); }}
    .badge-info    {{ background: rgba(6,182,212,0.15); color: {COLOR['info']}; border: 1px solid rgba(6,182,212,0.3); }}

    /* Reduced motion respect */
    @media (prefers-reduced-motion: reduce) {{
        *, *::before, *::after {{
            animation-duration: 0.01ms !important;
            transition-duration: 0.01ms !important;
        }}
    }}

    /* Focus rings for accessibility */
    button:focus-visible, [role="button"]:focus-visible, input:focus-visible {{
        outline: 2px solid {COLOR['primary']} !important;
        outline-offset: 2px !important;
    }}

    /* Monospaced numbers in tables */
    table td, table th {{
        font-variant-numeric: tabular-nums !important;
    }}
</style>
""", unsafe_allow_html=True)


# ── Data loaders ───────────────────────────────────────────────────────────────

@st.cache_data(ttl=60)
def _load_csv(path: str, parse_dates: list[str] | None = None) -> pd.DataFrame:
    if not Path(path).exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, parse_dates=parse_dates or [])
    except Exception:
        return pd.DataFrame()


def _load_daily() -> pd.DataFrame:
    df = _load_csv(str(DAILY_LOG), ["date"])
    if df.empty: return df
    return df.sort_values("date").reset_index(drop=True)


def _load_sentiment() -> pd.DataFrame:
    return _load_csv(str(SENTIMENT_LOG), ["timestamp"])


def _load_regime() -> pd.DataFrame:
    return _load_csv(str(REGIME_LOG), ["timestamp"])


def _load_watchlist() -> pd.DataFrame:
    return _load_csv(str(WATCHLIST_LOG), ["timestamp"])


def _load_alerts() -> pd.DataFrame:
    return _load_csv(str(WATCHLIST_ALERTS), ["timestamp"])


@st.cache_data(ttl=600)
def _load_quarterly() -> pd.DataFrame:
    p = Path(QUARTERLY_BACKTEST)
    if not p.exists(): return pd.DataFrame()
    try: return pd.read_csv(p, index_col=0)
    except Exception: return pd.DataFrame()


def _parse_weights(raw) -> dict:
    if isinstance(raw, dict): return raw
    if not raw or not isinstance(raw, str): return {}
    try: return json.loads(raw)
    except Exception:
        try:
            import ast
            return ast.literal_eval(raw)
        except Exception:
            return {}


def _latest_row(df: pd.DataFrame) -> dict:
    return {} if df.empty else df.iloc[-1].to_dict()


def _clean_notes(raw) -> str:
    if raw is None or (isinstance(raw, float) and pd.isna(raw)): return ""
    s = str(raw).strip()
    return "" if s.lower() == "nan" else s


# ── Load data ─────────────────────────────────────────────────────────────────

daily_df = _load_daily()
sentiment_df = _load_sentiment()
regime_df = _load_regime()
wl_df = _load_watchlist()
alerts_df = _load_alerts()
qdf = _load_quarterly()
latest = _latest_row(daily_df)
latest_regime = _latest_row(regime_df).get("regime", "—")


# ── HEADER ────────────────────────────────────────────────────────────────────

REGIME_META = {
    "RISK_ON":  ("Bull",     COLOR["risk_on"],  "success"),
    "CHOPPY":   ("Sideways", COLOR["choppy"],   "warning"),
    "RISK_OFF": ("Defensive",COLOR["risk_off"], "danger"),
}
regime_label, regime_color, regime_badge = REGIME_META.get(latest_regime, ("—", COLOR["text_3"], "info"))

col_title, col_status = st.columns([2, 1])
with col_title:
    st.markdown(f"""
    <div style="display:flex; align-items:center; gap:0.75rem; margin-bottom:0.25rem;">
        <div style="width:8px; height:8px; border-radius:50%; background:{regime_color}; box-shadow: 0 0 12px {regime_color}80;"></div>
        <h1 style="margin:0;">Portfolio Bot</h1>
    </div>
    <div style="color:{COLOR['text_3']}; font-size:0.8125rem; letter-spacing:0.02em;">
        AI-Powered Portfolio · HRP Momentum · Paper Trading
    </div>
    """, unsafe_allow_html=True)

with col_status:
    last_run = str(latest.get("date", "—"))[:10] if latest else "—"
    strategy_name = str(latest.get("strategy", "—"))
    st.markdown(f"""
    <div style="text-align:right; padding-top:0.25rem;">
        <span class="status-badge badge-{regime_badge}">● {latest_regime} · {regime_label}</span>
        <div style="color:{COLOR['text_3']}; font-size:0.75rem; margin-top:0.5rem;">
            Last run: <span style="color:{COLOR['text_2']}; font-variant-numeric:tabular-nums;">{last_run}</span> · Strategy: <span style="color:{COLOR['text_2']};">{strategy_name}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("<div style='margin: 1.25rem 0 0.5rem 0;'></div>", unsafe_allow_html=True)

# ── KPI ROW ────────────────────────────────────────────────────────────────────

def _format_money(v): return f"${v:,.0f}"
def _format_pct(v): return f"{v*100:+.2f}%"

if latest:
    port_val = float(latest.get("portfolio_value", 0))
    sharpe = float(latest.get("sharpe", 0))
    exp_ret = float(latest.get("expected_return", 0))
    ann_vol = float(latest.get("annual_vol", 0))

    # Compute today's change vs yesterday
    if len(daily_df) >= 2:
        prev_val = float(daily_df.iloc[-2]["portfolio_value"])
        day_change = port_val - prev_val
        day_change_pct = (port_val / prev_val - 1) if prev_val else 0
        delta_str = f"{day_change:+.2f} ({day_change_pct*100:+.2f}%)"
    else:
        delta_str = None

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Portfolio Value", _format_money(port_val), delta=delta_str)
    with c2:
        st.metric("Sharpe Ratio", f"{sharpe:.2f}")
    with c3:
        st.metric("Expected Return", _format_pct(exp_ret))
    with c4:
        st.metric("Annual Volatility", _format_pct(ann_vol))
else:
    st.info("No data yet. Trigger a bot run to populate.")


# ── HOLDINGS SECTION ──────────────────────────────────────────────────────────

st.markdown("## Holdings")

if not latest:
    st.info("No holdings data yet.")
else:
    weights = {k: v for k, v in _parse_weights(latest.get("final_weights", "")).items() if v > 0.001}
    notes = _clean_notes(latest.get("notes", ""))
    orders = int(latest.get("orders_placed", 0) or 0)

    # Status messaging
    if "breach" in notes.lower() or "fail" in notes.lower() or "spike" in notes.lower() or "scaling" in notes.lower():
        st.markdown(f'<div class="status-badge badge-warning">⚠ Trades blocked — {notes}. Showing intended target weights.</div>', unsafe_allow_html=True)
    elif notes == "no_rebalance":
        st.markdown(f'<div class="status-badge badge-info">✓ On target — no rebalance needed</div>', unsafe_allow_html=True)
    elif orders > 0:
        st.markdown(f'<div class="status-badge badge-success">✓ Rebalanced today · {orders} orders placed</div>', unsafe_allow_html=True)
    elif notes:
        st.markdown(f'<div class="status-badge badge-warning">⚠ {notes}</div>', unsafe_allow_html=True)

    if weights:
        port_val = float(latest.get("portfolio_value", 0))
        sent_df = sentiment_df

        col_donut, col_table = st.columns([1, 1.4])

        with col_donut:
            sorted_weights = sorted(weights.items(), key=lambda x: -x[1])
            labels = [t for t, _ in sorted_weights]
            values = [v * 100 for _, v in sorted_weights]
            palette = ["#3b82f6","#10b981","#f59e0b","#ef4444","#8b5cf6","#06b6d4","#ec4899","#84cc16","#f97316","#a855f7","#14b8a6","#facc15"]

            fig = go.Figure(go.Pie(
                labels=labels, values=values, hole=0.62,
                textinfo="label+percent", textposition="outside",
                marker=dict(colors=palette[:len(labels)], line=dict(color=COLOR["bg"], width=2)),
                textfont=dict(family="Inter", size=11, color=COLOR["text_2"]),
                hovertemplate="<b>%{label}</b><br>%{value:.1f}%<extra></extra>",
            ))
            fig.update_layout(
                **PLOTLY_LAYOUT,
                height=380,
                showlegend=False,
                annotations=[dict(
                    text=f"<b style='color:{COLOR['text']}; font-size:18px'>{len(labels)}</b><br><span style='color:{COLOR['text_3']}; font-size:11px; letter-spacing:0.08em;'>POSITIONS</span>",
                    x=0.5, y=0.5, showarrow=False, font=dict(family="Inter")
                )]
            )
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

        with col_table:
            rows = []
            for ticker, w in sorted_weights:
                sent = None
                if not sent_df.empty:
                    s = sent_df[sent_df["ticker"] == ticker].tail(1)
                    if not s.empty: sent = float(s.iloc[0]["score"])
                rows.append({
                    "Asset": ticker,
                    "Weight": w,
                    "Value": w * port_val,
                    "Sentiment": sent,
                })
            df = pd.DataFrame(rows)

            st.dataframe(
                df, hide_index=True, use_container_width=True, height=380,
                column_config={
                    "Asset": st.column_config.TextColumn("Asset", width="small"),
                    "Weight": st.column_config.ProgressColumn(
                        "Weight", format="%.1f%%", min_value=0, max_value=df["Weight"].max() if not df.empty else 1,
                    ),
                    "Value": st.column_config.NumberColumn("$ Value", format="$%.0f"),
                    "Sentiment": st.column_config.NumberColumn("Sentiment", format="%+.2f", help="Claude sentiment score (-1 to +1)"),
                },
            )


# ── PERFORMANCE SECTION ───────────────────────────────────────────────────────

st.markdown("## Performance")

if daily_df.empty or "portfolio_value" not in daily_df.columns or len(daily_df) < 2:
    st.markdown(
        f'<div style="background:{COLOR["surface"]}; border:1px solid {COLOR["border"]}; '
        f'border-radius:12px; padding:2.5rem; text-align:center; color:{COLOR["text_3"]};">'
        f'<div style="font-size:2.5rem; opacity:0.4;">📈</div>'
        f'<div style="margin-top:0.5rem;">Equity curve will appear after a few days of data.</div></div>',
        unsafe_allow_html=True,
    )
else:
    daily_df["date"] = pd.to_datetime(daily_df["date"]).dt.normalize()
    first_val = daily_df["portfolio_value"].iloc[0]
    norm_port = daily_df["portfolio_value"] / first_val * 100

    fig_eq = go.Figure()
    fig_eq.add_trace(go.Scatter(
        x=daily_df["date"], y=norm_port, name="Portfolio",
        line=dict(color=COLOR["primary"], width=2.5),
        fill="tozeroy",
        fillcolor="rgba(59, 130, 246, 0.08)",
        hovertemplate="<b>Portfolio</b><br>%{x|%b %d}<br>$%{y:.2f}<extra></extra>",
    ))

    try:
        from data import load_price_cache
        cached = load_price_cache(max_age_hours=12)
        if cached is not None and "SPY" in cached.columns:
            spy = cached["SPY"].dropna()
            start_idx = daily_df["date"].min()
            spy_window = spy[spy.index >= start_idx]
            if not spy_window.empty:
                spy_norm = spy_window / spy_window.iloc[0] * 100
                fig_eq.add_trace(go.Scatter(
                    x=spy_norm.index, y=spy_norm.values, name="SPY",
                    line=dict(color=COLOR["text_3"], width=2, dash="dash"),
                    hovertemplate="<b>SPY</b><br>%{x|%b %d}<br>$%{y:.2f}<extra></extra>",
                ))
    except Exception:
        pass

    days = max((daily_df["date"].iloc[-1] - daily_df["date"].iloc[0]).days, 1)
    total_ret = norm_port.iloc[-1] / 100 - 1
    cagr = (norm_port.iloc[-1] / 100) ** (365.25 / days) - 1 if days > 0 else 0

    c1, c2, c3 = st.columns(3)
    with c1: st.metric("Total Return", _format_pct(total_ret))
    with c2: st.metric("Annualized (CAGR)", _format_pct(cagr))
    with c3: st.metric("Trading Days", f"{len(daily_df)}")

    fig_eq.update_layout(
        **PLOTLY_LAYOUT, height=380,
        xaxis_title=None, yaxis_title="Growth of $100",
        legend=dict(orientation="h", y=1.08, x=0, bgcolor="rgba(0,0,0,0)"),
    )
    fig_eq.update_yaxes(tickprefix="$")
    st.plotly_chart(fig_eq, use_container_width=True, config={"displayModeBar": False})


# ── WATCHLIST ─────────────────────────────────────────────────────────────────

st.markdown("## Watchlist")

if wl_df.empty:
    st.markdown(
        f'<div style="background:{COLOR["surface"]}; border:1px solid {COLOR["border"]}; '
        f'border-radius:12px; padding:2rem; text-align:center; color:{COLOR["text_3"]};">'
        f'No watchlist data yet — scan runs each morning</div>',
        unsafe_allow_html=True,
    )
else:
    latest_wl = wl_df.sort_values("timestamp").drop_duplicates("ticker", keep="last")
    latest_wl = latest_wl.sort_values("today_pct", ascending=False)
    alert_tickers = set(alerts_df["ticker"].tolist()) if not alerts_df.empty else set()

    display = latest_wl[["ticker", "price", "today_pct", "mom_5d", "sentiment_score"]].copy()
    display["Alert"] = display["ticker"].apply(lambda t: "🔔" if t in alert_tickers else "")
    display = display.rename(columns={
        "ticker": "Ticker", "price": "Price", "today_pct": "Today",
        "mom_5d": "5-Day", "sentiment_score": "Sentiment",
    })

    if not alerts_df.empty:
        st.markdown(
            f'<div class="status-badge badge-warning">🔔 {len(alerts_df)} active alerts</div>',
            unsafe_allow_html=True,
        )
        st.markdown("<div style='margin-bottom: 0.5rem;'></div>", unsafe_allow_html=True)

    st.dataframe(
        display, hide_index=True, use_container_width=True, height=min(420, 40 * (len(display) + 1) + 38),
        column_config={
            "Alert": st.column_config.TextColumn("", width="small"),
            "Ticker": st.column_config.TextColumn("Ticker", width="small"),
            "Price": st.column_config.NumberColumn("Price", format="$%.2f"),
            "Today": st.column_config.NumberColumn("Today", format="%+.2f%%", help="Today's price change"),
            "5-Day": st.column_config.NumberColumn("5-Day", format="%+.2f%%", help="5-day momentum"),
            "Sentiment": st.column_config.NumberColumn("Sentiment", format="%+.2f", help="Claude sentiment score"),
        },
    )

    if not alerts_df.empty:
        with st.expander("Alert details"):
            alerts_show = alerts_df.sort_values("timestamp", ascending=False).head(20)
            alerts_show["timestamp"] = pd.to_datetime(alerts_show["timestamp"]).dt.strftime("%Y-%m-%d %H:%M")
            st.dataframe(alerts_show, hide_index=True, use_container_width=True)


# ── BACKTEST ──────────────────────────────────────────────────────────────────

st.markdown("## Backtest — 2019 to Today")

if qdf.empty:
    st.markdown(
        f'<div style="background:{COLOR["surface"]}; border:1px solid {COLOR["border"]}; '
        f'border-radius:12px; padding:2rem; text-align:center; color:{COLOR["text_3"]};">'
        f'Run <code style="color:{COLOR["primary_2"]}; background:{COLOR["surface_2"]}; padding:2px 6px; border-radius:4px;">python3 backtest.py</code> to populate</div>',
        unsafe_allow_html=True,
    )
else:
    strategies = [c for c in qdf.columns if c in ["MAX_SHARPE", "HRP", "HRP_MOMENTUM", "SPY"]]
    color_map = {
        "MAX_SHARPE": "#3b82f6",
        "HRP": "#10b981",
        "HRP_MOMENTUM": "#f59e0b",
        "SPY": "#64748b",
    }

    # Win-rate KPIs
    if "SPY" in qdf.columns:
        win_cols = st.columns(3)
        for i, strat in enumerate(["MAX_SHARPE", "HRP", "HRP_MOMENTUM"]):
            if strat in qdf.columns:
                wins = (qdf[strat] > qdf["SPY"]).sum()
                total = len(qdf)
                with win_cols[i]:
                    st.metric(
                        f"{strat} vs SPY",
                        f"{wins}/{total}",
                        f"{wins/total*100:.0f}% win rate",
                        delta_color="normal" if wins/total >= 0.5 else "inverse",
                    )

    selected = st.multiselect("Strategies", strategies, default=strategies, label_visibility="collapsed")
    if selected:
        fig_q = go.Figure()
        for strat in selected:
            if strat in qdf.columns:
                fig_q.add_trace(go.Bar(
                    name=strat, x=qdf.index.tolist(),
                    y=(qdf[strat] * 100).tolist(),
                    marker_color=color_map.get(strat),
                    hovertemplate=f"<b>{strat}</b><br>%{{x}}: %{{y:+.2f}}%<extra></extra>",
                ))
        fig_q.update_layout(
            **PLOTLY_LAYOUT, barmode="group", height=420,
            xaxis_title=None, yaxis_title="Quarterly Return (%)",
            legend=dict(orientation="h", y=1.08, x=0),
        )
        fig_q.update_yaxes(ticksuffix="%", zerolinecolor=COLOR["border_2"], zerolinewidth=1.5)
        st.plotly_chart(fig_q, use_container_width=True, config={"displayModeBar": False})


# ── RECENT ACTIVITY ──────────────────────────────────────────────────────────

st.markdown("## Recent Activity")

if daily_df.empty:
    st.markdown(
        f'<div style="background:{COLOR["surface"]}; border:1px solid {COLOR["border"]}; '
        f'border-radius:12px; padding:2rem; text-align:center; color:{COLOR["text_3"]};">No activity yet.</div>',
        unsafe_allow_html=True,
    )
else:
    recent = daily_df.tail(30).copy()
    recent["date"] = pd.to_datetime(recent["date"]).dt.date

    cols_to_show = ["date", "strategy", "regime", "portfolio_value", "sharpe", "orders_placed", "notes"]
    cols_present = [c for c in cols_to_show if c in recent.columns]
    display_recent = recent[cols_present].iloc[::-1]

    st.dataframe(
        display_recent, hide_index=True, use_container_width=True,
        column_config={
            "date": st.column_config.TextColumn("Date"),
            "strategy": st.column_config.TextColumn("Strategy"),
            "regime": st.column_config.TextColumn("Regime"),
            "portfolio_value": st.column_config.NumberColumn("Portfolio $", format="$%.2f"),
            "sharpe": st.column_config.NumberColumn("Sharpe", format="%.2f"),
            "orders_placed": st.column_config.NumberColumn("Orders", format="%d"),
            "notes": st.column_config.TextColumn("Notes"),
        },
    )


# ── LIVE TOOLS ────────────────────────────────────────────────────────────────

st.markdown("## Live Tools")

tab1, tab2, tab3 = st.tabs(["Dry Run", "Force Rebalance", "Efficient Frontier"])

with tab1:
    st.caption("Run the optimizer without placing any trades — see what the bot would do.")
    strategy_choice = st.selectbox("Strategy", ["HRP_MOMENTUM", "HRP", "MAX_SHARPE"], key="dr_strat")
    if st.button("Run Optimizer", key="dr_btn", type="primary"):
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
                m3.metric("Volatility", _format_pct(result_dr['annual_volatility']))

                weights_dr = {k: v for k, v in result_dr["weights"].items() if v > 0.001}
                df_dr = pd.DataFrame([
                    {"Asset": t, "Weight": w}
                    for t, w in sorted(weights_dr.items(), key=lambda x: -x[1])
                ])
                st.dataframe(
                    df_dr, hide_index=True, use_container_width=True,
                    column_config={"Weight": st.column_config.ProgressColumn("Weight", format="%.1f%%", min_value=0, max_value=df_dr["Weight"].max() if not df_dr.empty else 1)},
                )
            except Exception as exc:
                st.error(f"Optimizer failed: {exc}")

with tab2:
    st.caption("Force the full rebalance pipeline to run NOW. Places real paper trades on Alpaca.")
    confirm = st.checkbox("I understand this will place paper trades")
    if confirm and st.button("Run Full Pipeline", key="fr_btn", type="primary"):
        with st.spinner("Running pipeline — this takes ~3-8 minutes…"):
            try:
                import importlib, main as m
                importlib.reload(m)
                m.main()
                st.success("Done — refresh to see updated logs.")
                st.cache_data.clear()
            except SystemExit:
                st.info("Market is closed — bot exited cleanly. Nothing was traded.")
            except Exception as exc:
                st.error(f"Pipeline error: {exc}")

with tab3:
    st.caption("3,000 random portfolios vs your current allocation on the risk/return frontier.")
    if st.button("Generate Frontier", key="ef_btn", type="primary"):
        with st.spinner("Computing…"):
            try:
                from data import load_price_cache, fetch_prices, get_returns
                from scipy.optimize import minimize

                cached = load_price_cache(max_age_hours=24)
                if cached is not None:
                    asset_cols = [a for a in ASSETS if a in cached.columns]
                    prices_ef = cached[asset_cols]
                    returns_ef = get_returns(prices_ef)
                else:
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
                    marker=dict(color=COLOR["text_3"], size=3.5, opacity=0.35, line=dict(width=0)),
                    name="Random portfolios", hoverinfo="skip",
                ))

                if latest and latest.get("final_weights"):
                    cur_w_dict = _parse_weights(latest["final_weights"])
                    tickers_ef = returns_ef.columns.tolist()
                    cur_w = np.array([cur_w_dict.get(t, 0.0) for t in tickers_ef])
                    if cur_w.sum() > 0:
                        cur_w /= cur_w.sum()
                        cur_ret = float(cur_w @ mean_r)
                        cur_vol = float(np.sqrt(cur_w @ cov_r @ cur_w))
                        fig_ef.add_trace(go.Scatter(
                            x=[cur_vol], y=[cur_ret], mode="markers+text",
                            marker=dict(color=COLOR["accent"], size=18, symbol="star",
                                        line=dict(color="white", width=1.5)),
                            text=["Your portfolio"], textposition="top center",
                            textfont=dict(color=COLOR["accent"], size=11, family="Inter"),
                            name="Your portfolio",
                        ))

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
                    mode="markers", marker=dict(color=COLOR["info"], size=14, symbol="diamond"),
                    name="Min variance",
                ))

                fig_ef.update_layout(
                    **PLOTLY_LAYOUT, height=500,
                    xaxis_title="Annual Volatility", yaxis_title="Expected Annual Return",
                    legend=dict(orientation="h", y=1.05, x=0),
                )
                fig_ef.update_xaxes(tickformat=".0%")
                fig_ef.update_yaxes(tickformat=".0%")
                st.plotly_chart(fig_ef, use_container_width=True, config={"displayModeBar": False})
            except Exception as exc:
                st.error(f"Frontier unavailable: {exc}")


# ── FOOTER ────────────────────────────────────────────────────────────────────

st.markdown(
    f'<div style="text-align:center; color:{COLOR["text_3"]}; font-size:0.6875rem; '
    f'letter-spacing:0.06em; text-transform:uppercase; margin-top:3rem; padding-top:1.5rem; '
    f'border-top:1px solid {COLOR["border"]};">Powered by Claude · Alpaca · Streamlit</div>',
    unsafe_allow_html=True,
)
