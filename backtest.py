"""Full historical backtest — all 3 strategies vs SPY from 2019-01-01.

Outputs:
  - Prints full period summary table
  - Prints quarterly breakdown table
  - Saves quarterly_backtest.csv
  - Saves backtest_results.png (3-panel chart)
"""

import logging
import warnings
from datetime import datetime, timedelta

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd
import seaborn as sns
import yfinance as yf

from config import ASSETS, BACKTEST_RESULTS, DRAWDOWN_CIRCUIT_BREAKER, QUARTERLY_BACKTEST, RISK_FREE_RATE
from regime import CHOPPY, RISK_OFF, RISK_ON, _majority_vote, _trend_signal, _vol_signal, _flight_signal

warnings.filterwarnings("ignore")
logger = logging.getLogger(__name__)

STRATEGIES = ["MAX_SHARPE", "HRP", "HRP_MOMENTUM"]
BACKTEST_START = datetime(2019, 1, 1)


# ── Data download ──────────────────────────────────────────────────────────────

def _download_history(tickers: list[str]) -> pd.DataFrame:
    logger.info("Downloading price history for backtest (%d tickers)…", len(tickers))
    frames: list[pd.Series] = []
    for ticker in tickers:
        try:
            raw = yf.download(
                ticker,
                start=BACKTEST_START.strftime("%Y-%m-%d"),
                end=datetime.today().strftime("%Y-%m-%d"),
                auto_adjust=True,
                progress=False,
                multi_level_index=False,
            )
            if raw.empty:
                logger.warning("No backtest data for %s", ticker)
                continue
            frames.append(raw["Close"].rename(ticker))
        except Exception as exc:
            logger.warning("Download failed for %s: %s", ticker, exc)
    if not frames:
        raise RuntimeError("No data downloaded for backtest.")
    prices = pd.concat(frames, axis=1).ffill().bfill()
    return prices


# ── Regime detection for a price slice ────────────────────────────────────────

def _detect_regime_from_prices(prices_slice: pd.DataFrame) -> str:
    spy = prices_slice.get("SPY", pd.Series(dtype=float))
    tlt = prices_slice.get("TLT", pd.Series(dtype=float))
    if spy.empty or len(spy) < 20:
        return CHOPPY
    spy_ret = spy.pct_change().dropna()
    tlt_valid = tlt if not tlt.empty else spy
    sigs = [_vol_signal(spy_ret), _trend_signal(spy), _flight_signal(spy, tlt_valid)]
    return _majority_vote(sigs)


# ── Per-strategy weight computation (no live API calls) ───────────────────────

def _compute_weights(strategy: str, returns: pd.DataFrame, regime: str) -> dict[str, float]:
    """Thin wrapper around optimizer — no sentiment in backtest."""
    from optimizer import optimize
    try:
        result = optimize(strategy=strategy, returns=returns, sentiment_modifiers={}, regime=regime)
        return result["weights"]
    except Exception as exc:
        logger.warning("optimize failed (%s, %s): %s — equal weight fallback", strategy, regime, exc)
        n = len(returns.columns)
        return {t: 1.0 / n for t in returns.columns}


# ── Equity curve simulation ────────────────────────────────────────────────────

def _simulate(prices: pd.DataFrame, strategy: str) -> pd.Series:
    """Monthly rebalance simulation returning daily equity index (start=1.0)."""
    asset_cols = [c for c in ASSETS if c in prices.columns]
    returns = prices[asset_cols + ["SPY"]].pct_change()

    # Month-end rebalance dates
    rebal_dates = pd.date_range(
        start=prices.index[0], end=prices.index[-1], freq="BME"
    )

    equity = pd.Series(index=prices.index, dtype=float)
    equity.iloc[0] = 1.0
    weights: dict[str, float] = {}
    portfolio_ath = 1.0

    for i in range(1, len(prices)):
        date = prices.index[i]

        # Rebalance on month-end or first bar
        if date in rebal_dates or i == 1:
            hist_start = max(0, i - 252)
            hist = returns.iloc[hist_start:i][asset_cols].dropna(axis=1, how="all")
            if not hist.empty and len(hist) >= 20:
                price_slice = prices.iloc[hist_start:i]
                regime = _detect_regime_from_prices(price_slice)
                weights = _compute_weights(strategy, hist, regime)
            elif not asset_cols:
                weights = {}
            else:
                weights = {t: 1.0 / len(asset_cols) for t in asset_cols}

        # Daily portfolio return
        day_ret = sum(
            weights.get(t, 0.0) * returns.loc[date, t]
            for t in weights
            if t in returns.columns and not np.isnan(returns.loc[date, t])
        )

        prev_val = equity.iloc[i - 1]
        new_val = prev_val * (1.0 + day_ret)

        # Drawdown circuit breaker — use config value (was hardcoded)
        portfolio_ath = max(portfolio_ath, new_val)
        if (new_val / portfolio_ath - 1) < -DRAWDOWN_CIRCUIT_BREAKER:
            new_val = prev_val  # freeze portfolio (no trading)

        equity.iloc[i] = new_val

    return equity.dropna()


# ── Performance metrics ────────────────────────────────────────────────────────

def _cagr(equity: pd.Series) -> float:
    years = (equity.index[-1] - equity.index[0]).days / 365.25
    return float((equity.iloc[-1] / equity.iloc[0]) ** (1.0 / years) - 1) if years > 0 else 0.0


def _sharpe(equity: pd.Series) -> float:
    daily_ret = equity.pct_change().dropna()
    if daily_ret.std() < 1e-9:
        return 0.0
    return float((daily_ret.mean() - RISK_FREE_RATE / 252) / daily_ret.std() * np.sqrt(252))


def _max_drawdown(equity: pd.Series) -> float:
    roll_max = equity.cummax()
    dd = (equity - roll_max) / roll_max
    return float(dd.min())


def _annual_returns(equity: pd.Series) -> pd.Series:
    return equity.resample("YE").last().pct_change().dropna()


def _full_period_stats(name: str, equity: pd.Series) -> dict:
    ann = _annual_returns(equity)
    return {
        "Strategy": name,
        "CAGR": f"{_cagr(equity):.1%}",
        "Sharpe": f"{_sharpe(equity):.2f}",
        "Max Drawdown": f"{_max_drawdown(equity):.1%}",
        "Total Return": f"{equity.iloc[-1] / equity.iloc[0] - 1:.1%}",
        "Best Year": f"{ann.max():.1%}" if not ann.empty else "N/A",
        "Worst Year": f"{ann.min():.1%}" if not ann.empty else "N/A",
    }


# ── Quarterly breakdown ────────────────────────────────────────────────────────

def _quarterly_returns(equity: pd.Series) -> pd.Series:
    return equity.resample("QE").last().pct_change().dropna()


def _build_quarterly_df(curves: dict[str, pd.Series]) -> pd.DataFrame:
    q_frames = {name: _quarterly_returns(eq).rename(name) for name, eq in curves.items()}
    df = pd.concat(q_frames.values(), axis=1).dropna(how="all")
    df.index = df.index.to_period("Q").astype(str)
    return df


# ── Market condition breakdown ────────────────────────────────────────────────

def _compute_regime_series(prices: pd.DataFrame) -> pd.Series:
    """Approximate monthly regime label for the full history."""
    month_ends = pd.date_range(prices.index[0], prices.index[-1], freq="BME")
    regimes: list[tuple] = []
    for dt in month_ends:
        hist = prices.loc[:dt].tail(252)
        regime = _detect_regime_from_prices(hist)
        regimes.append((dt, regime))
    return pd.Series(dict(regimes))


# ── Charts ─────────────────────────────────────────────────────────────────────

_COLORS = {
    "MAX_SHARPE": "#4C72B0",
    "HRP": "#55A868",
    "HRP_MOMENTUM": "#C44E52",
    "SPY": "#8172B2",
}


def _plot_equity_curves(ax: plt.Axes, curves: dict[str, pd.Series]) -> None:
    for name, eq in curves.items():
        ax.plot(eq.index, eq.values * 100, label=name, color=_COLORS.get(name), linewidth=1.6)
    ax.set_title("Portfolio Equity Curves vs SPY (2019–Today)", fontsize=12, fontweight="bold")
    ax.set_ylabel("Growth of $100")
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"${x:,.0f}"))
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)


def _plot_quarterly_bars(ax: plt.Axes, qdf: pd.DataFrame) -> None:
    quarters = qdf.index.tolist()
    n_q = len(quarters)
    n_s = len(qdf.columns)
    x = np.arange(n_q)
    w = 0.8 / n_s

    for i, col in enumerate(qdf.columns):
        vals = qdf[col].values * 100
        bars = ax.bar(x + i * w, vals, width=w, label=col, color=_COLORS.get(col), alpha=0.85)

    ax.set_title("Quarterly Returns — All Strategies vs SPY", fontsize=12, fontweight="bold")
    ax.set_xticks(x + w * (n_s - 1) / 2)
    ax.set_xticklabels(quarters, rotation=75, fontsize=6)
    ax.set_ylabel("Return (%)")
    ax.axhline(0, color="black", linewidth=0.8)
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3, axis="y")


def _plot_condition_heatmap(ax: plt.Axes, qdf: pd.DataFrame, regime_series: pd.Series) -> None:
    """Heatmap of avg return per (strategy, regime)."""
    strategy_cols = [c for c in qdf.columns if c != "SPY"]
    records: list[dict] = []
    for q_str in qdf.index:
        # Map quarter string to approximate date
        try:
            q_period = pd.Period(q_str, "Q")
            q_end = q_period.end_time
            # Find nearest regime
            diffs = abs(regime_series.index - q_end)
            regime = regime_series.iloc[diffs.argmin()] if not regime_series.empty else CHOPPY
        except Exception:
            regime = CHOPPY
        spy_ret = qdf.loc[q_str, "SPY"] if "SPY" in qdf.columns else 0.0
        for strat in strategy_cols:
            records.append({
                "Strategy": strat,
                "Regime": regime,
                "Return": qdf.loc[q_str, strat],
                "Beat SPY": int(qdf.loc[q_str, strat] > spy_ret),
            })

    df_r = pd.DataFrame(records)
    if df_r.empty:
        ax.set_visible(False)
        return

    pivot = df_r.groupby(["Regime", "Strategy"])["Return"].mean().unstack() * 100
    sns.heatmap(pivot, annot=True, fmt=".1f", cmap="RdYlGn", center=0, ax=ax,
                linewidths=0.5, cbar_kws={"label": "Avg Quarterly Return (%)"})
    ax.set_title("Avg Return by Market Regime", fontsize=12, fontweight="bold")


# ── Main entry ─────────────────────────────────────────────────────────────────

def run_backtest() -> None:
    all_tickers = list(dict.fromkeys(ASSETS + ["SPY", "TLT"]))
    prices = _download_history(all_tickers)

    curves: dict[str, pd.Series] = {}
    for strategy in STRATEGIES:
        logger.info("Simulating %s…", strategy)
        curves[strategy] = _simulate(prices, strategy)
    curves["SPY"] = (prices["SPY"] / prices["SPY"].iloc[0]).dropna() if "SPY" in prices.columns else pd.Series()

    # ── Full period summary ────────────────────────────────────────────────────
    print("\n" + "═" * 80)
    print("FULL PERIOD SUMMARY (2019-01-01 → today)")
    print("═" * 80)
    header = f"{'Strategy':<18} {'CAGR':>8} {'Sharpe':>8} {'Max DD':>10} {'Total Ret':>12} {'Best Yr':>9} {'Worst Yr':>9}"
    print(header)
    print("-" * 80)
    for name, eq in curves.items():
        if eq.empty:
            continue
        s = _full_period_stats(name, eq)
        print(
            f"{s['Strategy']:<18} {s['CAGR']:>8} {s['Sharpe']:>8} "
            f"{s['Max Drawdown']:>10} {s['Total Return']:>12} "
            f"{s['Best Year']:>9} {s['Worst Year']:>9}"
        )

    # ── Quarterly breakdown ────────────────────────────────────────────────────
    qdf = _build_quarterly_df(curves)
    spy_q = qdf.get("SPY", pd.Series(0.0, index=qdf.index))

    print("\n" + "═" * 80)
    print("QUARTERLY BREAKDOWN")
    print("═" * 80)
    cols = qdf.columns.tolist()
    header_q = f"{'Quarter':<8} " + " ".join(f"{c:>14}" for c in cols) + f"  {'Winner':<14}"
    print(header_q)
    print("-" * 80)
    for q, row in qdf.iterrows():
        parts = []
        for c in cols:
            val = row.get(c, np.nan)
            tag = "✓" if (c != "SPY" and not np.isnan(val) and val > spy_q.get(q, 0.0)) else " "
            parts.append(f"{val:>12.1%}{tag}")
        non_spy = {c: row.get(c, -np.inf) for c in cols if c != "SPY"}
        winner = max(non_spy, key=non_spy.get) if non_spy else "—"
        print(f"{q:<8} " + " ".join(parts) + f"  {winner:<14}")

    # Summary row
    if "SPY" in qdf.columns:
        for strat in [c for c in cols if c != "SPY"]:
            beats = (qdf[strat] > qdf["SPY"]).sum()
            total = len(qdf)
            pct = beats / total * 100 if total > 0 else 0
            print(f"  {strat}: beat SPY in {beats}/{total} quarters ({pct:.0f}%)")

    # ── Per-strategy quarterly stats ──────────────────────────────────────────
    print("\n" + "═" * 80)
    print("QUARTERLY STATS PER STRATEGY")
    print("═" * 80)
    for strat in [c for c in cols if c != "SPY"]:
        s_q = qdf[strat].dropna()
        if s_q.empty:
            continue
        spy_beats = (s_q > spy_q.reindex(s_q.index).fillna(0)).sum()
        print(f"\n{strat}")
        print(f"  Best quarter:      {s_q.idxmax()} ({s_q.max():.1%})")
        print(f"  Worst quarter:     {s_q.idxmin()} ({s_q.min():.1%})")
        print(f"  Positive quarters: {(s_q > 0).sum()}/{len(s_q)} ({(s_q > 0).mean():.0%})")
        print(f"  Beat SPY:          {spy_beats}/{len(s_q)} ({spy_beats/len(s_q):.0%})")
        print(f"  Avg return:        {s_q.mean():.1%}")
        print(f"  Quarterly vol:     {s_q.std():.1%}")

    # ── Market condition breakdown ─────────────────────────────────────────────
    regime_series = _compute_regime_series(prices)

    print("\n" + "═" * 80)
    print("MARKET CONDITION PERFORMANCE")
    print("═" * 80)
    strategy_cols = [c for c in cols if c != "SPY"]
    records: list[dict] = []
    for q_str in qdf.index:
        try:
            q_end = pd.Period(q_str, "Q").end_time
            if not regime_series.empty:
                diffs = abs(regime_series.index - q_end)
                regime = regime_series.iloc[diffs.argmin()]
            else:
                regime = CHOPPY
        except Exception:
            regime = CHOPPY
        spy_ret = qdf.loc[q_str, "SPY"] if "SPY" in qdf.columns else 0.0
        for strat in strategy_cols:
            records.append({"Regime": regime, "Strategy": strat,
                            "Return": qdf.loc[q_str, strat],
                            "BeatSPY": int(qdf.loc[q_str, strat] > spy_ret)})

    if records:
        df_cond = pd.DataFrame(records)
        for regime in [RISK_ON, CHOPPY, RISK_OFF]:
            sub = df_cond[df_cond["Regime"] == regime]
            if sub.empty:
                continue
            n_q = len(sub) // max(len(strategy_cols), 1)
            print(f"\n{regime} ({n_q} quarters):")
            for strat in strategy_cols:
                s_sub = sub[sub["Strategy"] == strat]
                if s_sub.empty:
                    continue
                print(
                    f"  {strat:<16} avg={s_sub['Return'].mean():.1%}  "
                    f"beat SPY {s_sub['BeatSPY'].mean():.0%}"
                )

    # ── Save CSV ───────────────────────────────────────────────────────────────
    qdf.to_csv(QUARTERLY_BACKTEST)
    logger.info("Saved %s", QUARTERLY_BACKTEST)

    # ── Save charts ────────────────────────────────────────────────────────────
    fig, axes = plt.subplots(3, 1, figsize=(16, 22))
    fig.patch.set_facecolor("#f8f9fa")
    for ax in axes:
        ax.set_facecolor("#ffffff")

    _plot_equity_curves(axes[0], curves)
    _plot_quarterly_bars(axes[1], qdf)
    _plot_condition_heatmap(axes[2], qdf, regime_series)

    plt.tight_layout(pad=3.0)
    plt.savefig(BACKTEST_RESULTS, dpi=150, bbox_inches="tight")
    plt.close()
    logger.info("Saved %s", BACKTEST_RESULTS)
    print(f"\n  Charts saved → {BACKTEST_RESULTS}")
    print(f"  CSV saved    → {QUARTERLY_BACKTEST}\n")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    run_backtest()
