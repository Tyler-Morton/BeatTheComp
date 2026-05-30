# IWillBeatS&P — Autonomous AI Portfolio Bot

A fully autonomous, AI-driven portfolio system designed to beat the S&P 500. It runs unattended on GitHub Actions every morning, fetches live market data, queries Claude for sentiment and trending-stock discovery, detects the prevailing market regime, picks the optimal strategy for that regime, places real orders through Alpaca, and serves a live Streamlit dashboard with the current state of the portfolio.

Built solo, end-to-end: data pipeline, optimization math, LLM integration, broker integration, CI/CD scheduling, and a custom dashboard.

---

## What it does

Every market morning, the bot:

1. **Pulls 252 days of price history** for ~15 ETFs + dynamically discovered individual stocks (Alpaca IEX feed, yfinance fallback, on-disk parquet cache as last resort).
2. **Discovers trending stocks** via a Claude web-search call — up to 30 fresh tickers per day based on what's actually being talked about, surging, or breaking.
3. **Scores sentiment** for every candidate ticker through the Anthropic Batch API (Haiku 4.5 with web search), batched for ~50% cost savings.
4. **Detects market regime** via a 3-signal majority vote — volatility, trend, and flight-to-safety — classifying the tape as `RISK_ON`, `CHOPPY`, or `RISK_OFF`.
5. **Picks the right strategy for the regime**, with a 60-day Sharpe-based adaptive override:
   - RISK_ON → HRP_MOMENTUM (ride sustained uptrends)
   - CHOPPY → HRP (pure risk parity, no trend assumption)
   - RISK_OFF → MAX_SHARPE (optimizer concentrates into TLT / GLD / SHV)
6. **Carves a 40% "alpha sleeve"** for the top 3 individual stock picks from the trending universe — gated by sentiment ≥ 0.5, 5-day momentum ≥ 5%, positive 20-day momentum, price ≥ $3, and not already up > 30% intraday.
7. **Runs pre-trade safety checks** — drawdown circuit breaker, portfolio-vol cap, single-asset concentration cap, correlation cap, drift threshold.
8. **Rebalances on Alpaca** using a 3-phase pattern (sell everything that needs to shrink → poll account until buying power settles → place buys sized to actual available cash) to defeat the float-precision and settlement races that wreck naive rebalancers.
9. **Logs everything** to versioned CSVs that get committed back to the repo by the workflow.

---

## Architecture

```
main.py                    daily orchestrator (idempotent — duplicate-run guard)
├── data.py                Alpaca IEX → yfinance → parquet-cache fallback chain
├── trending.py            Claude web-search trending stock discovery
├── sentiment.py           Claude Haiku Batch API sentiment scoring
├── regime.py              3-signal market regime classifier
├── optimizer.py           MAX_SHARPE / HRP / HRP_MOMENTUM + adaptive selector
├── alpha_sleeve.py        Individual-stock momentum picks with quality filters
├── risk.py                Drawdown breaker, vol cap, concentration, correlation
├── broker.py              3-phase Alpaca rebalance (sells → settle → buys)
└── watchlist.py           Always-scanned anchor names

backtest.py                2019 → today simulation with monthly rebalancing
dashboard.py               Streamlit dashboard (dark OLED, Plotly, custom motion)
config.py                  Every tuneable in one place
.github/workflows/         6 cron schedules + idempotency for cron-reliability
```

---

## Notable engineering decisions

- **3-phase broker rebalance.** Naive implementations submit sells and buys together and lose half the buys to "insufficient buying power" because settlement lags. This bot submits all sells, polls `buying_power` for up to 30s, then sizes each buy against live cash. Sells are capped at 99.5% of position value to avoid float-precision rejections on full-position liquidations.

- **Cron resilience.** GitHub Actions' free-tier cron is unreliable — delays of 15 min to 3 hr are common. Solved with 6 staggered cron entries through the morning + a duplicate-run guard in `main.py` so only the first successful run does work; the rest exit immediately.

- **Data-source fallback chain.** Primary is Alpaca IEX (free with paper account, no rate limits). Falls back to yfinance with a browser-mimicking session header (defeats their bot detection), then falls back to a parquet on-disk cache committed by previous runs. Result: pipeline keeps running even if a vendor goes down.

- **HRP weight-ordering bug.** Hierarchical clustering reorders the weights Series, which silently broke positional bounds clipping. Fixed by keying bounds by ticker symbol throughout.

- **Adaptive strategy override.** The regime → strategy mapping is the default, but if a non-default strategy has a materially higher 60-day Sharpe (≥ 100% margin in RISK_ON regimes), the bot overrides itself.

- **Quality filters on momentum picks.** Pure momentum scoring buys tops. Filters skip stocks already up >30% intraday, require positive 20-day momentum to confirm the move isn't a fakeout, and apply a soft penalty to anything already extended intraday.

---

## Tech stack

- **Python** (pandas, NumPy, SciPy, scikit-learn)
- **Anthropic Claude** (Haiku 4.5, Batch API, web-search tool)
- **Alpaca** (paper + live trading, IEX market data)
- **Streamlit + Plotly** (custom-themed dashboard)
- **GitHub Actions** (cron scheduling, auto-commit, retries)
- **Optimization**: Hierarchical Risk Parity (Ward linkage + recursive bisection), mean-variance / Max-Sharpe via SciPy SLSQP, momentum tilting

---

## Strategies

| Strategy | When it's used | How it works |
|---|---|---|
| `HRP_MOMENTUM` | RISK_ON regimes | HRP base weights + absolute momentum filter + relative momentum tilt (top-3 boosted +60%, bottom-3 trimmed 40%) |
| `HRP` | CHOPPY regimes | Pure Hierarchical Risk Parity — robust, no return estimates required |
| `MAX_SHARPE` | RISK_OFF regimes | Classic mean-variance optimization with full constraint set |

---

## Universe

The bot trades a curated leveraged-ETF growth core with diversifiers, **plus** dynamically discovered individual stocks:

- **Growth core:** TQQQ, UPRO, SOXL, TECL, QQQ, VGT, MTUM, IWM, AVUV, BITO, VEA
- **Defensive:** GLD, TLT, SHV
- **Anchor watchlist:** NVDA, TSLA, AAPL, PLTR, COIN
- **Dynamic discovery:** up to 30 trending tickers per day via Claude web search

---

## Dashboard

Custom Streamlit dashboard with a dark OLED theme, Plotly charts with custom easing curves, an equity curve auto-fit to actual portfolio dollar values, allocation donut, holdings table with momentum bars, sentiment grid, regime indicator, and watchlist alerts. Polished per Emil Kowalski's design philosophy — restrained motion, real materiality, no AI-default purple.

```bash
streamlit run dashboard.py
```

---

## Operating cost

| Service | Usage | Cost |
|---|---|---|
| Anthropic (Haiku Batch + web search) | ~30 tickers/day × 22 trading days | ~$1–3 / month |
| Alpaca paper trading | unlimited | $0 |
| Alpaca IEX data | unlimited | $0 |
| GitHub Actions | ~3 min/day × 22 days | Free tier |
| **Total** | | **< $3 / month** |

---

## Run it

```bash
git clone <repo>
cd IWillBeatS\&P
pip install -r requirements.txt
cp .env.example .env   # fill ALPACA_API_KEY, ALPACA_SECRET_KEY, ANTHROPIC_API_KEY

python backtest.py     # 2019 → today historical simulation
python main.py         # one live pipeline run
streamlit run dashboard.py
```

Paper → live is one env var: `ALPACA_BASE_URL=https://api.alpaca.markets`.

---

## Status

Currently running in production on Alpaca paper, rebalancing daily via GitHub Actions, fully autonomous.
