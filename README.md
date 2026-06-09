# IWillBeatS&P: Autonomous AI Portfolio Bot

A fully autonomous, AI-driven portfolio system designed to beat the S&P 500 on a risk-adjusted basis. It runs unattended on GitHub Actions every morning: it fetches live market data, queries Claude for sentiment and trending-stock discovery, detects the prevailing market regime, picks the optimal strategy for that regime, applies a volatility-targeting risk overlay, places real orders through Alpaca, and logs everything back to the repo. Two front ends visualize it: a Streamlit operations dashboard and a public showcase web page.

Built solo, end to end: data pipeline, optimization math, LLM integration, broker integration, a quant risk overlay, CI/CD scheduling, and two custom front ends.

> **Status:** running live on Alpaca paper, rebalancing daily via GitHub Actions, fully autonomous.

---

## What it does

Every market morning, the bot:

1. **Pulls 252 days of price history** for ~15 ETFs plus dynamically discovered individual stocks (Alpaca IEX feed, yfinance fallback, on-disk parquet cache as last resort).
2. **Discovers trending stocks** via a Claude web-search call: up to 30 fresh tickers per day based on what is actually surging, in the news, or being talked about.
3. **Scores sentiment** for every candidate ticker through the Anthropic Batch API (Haiku 4.5 with web search), batched for roughly 50% cost savings.
4. **Detects the market regime** via a 3-signal majority vote (volatility, trend, flight-to-safety), classifying the tape as `RISK_ON`, `CHOPPY`, or `RISK_OFF`.
5. **Picks the right strategy for the regime**, with a 60-day Sharpe-based adaptive override:
   - RISK_ON: HRP_MOMENTUM (ride sustained uptrends)
   - CHOPPY: HRP (pure risk parity, no trend assumption)
   - RISK_OFF: MAX_SHARPE (optimizer concentrates into TLT / GLD / SHV)
6. **Applies the volatility-targeting overlay** (see below): scales total exposure toward a constant 20% annual volatility and parks the rest in cash (SHV).
7. **Runs pre-trade safety checks:** drawdown circuit breaker, portfolio-vol cap, single-asset concentration cap, correlation cap, drift threshold.
8. **Rebalances on Alpaca** using a 3-phase pattern (sell everything that needs to shrink, poll the account until buying power settles, then place buys sized to actual available cash) to defeat the float-precision and settlement races that wreck naive rebalancers.
9. **Logs everything** to versioned CSVs that the workflow commits back to the repo.

---

## The risk overlay (the core of the strategy)

The portfolio holds 3x leveraged ETFs (TQQQ, UPRO, UDOW, SOXL, TECL) for upside, but raw leverage is brutal: the unmanaged 3x book ran near 90% annualized volatility with drawdowns past 70%. The overlay in `risk_overlay.py` tames that:

- **Volatility targeting.** Each morning it estimates the book's forward volatility and scales total exposure so the portfolio sits near a **20% annual-vol target**. In calm markets it leans in; in turbulence it de-risks and moves the excess into a cash sleeve (SHV). In backtests this cut volatility by roughly **53%** and pulled max drawdown from about **-71% to -24%**, while staying above SPY over full cycles.
- **ML crash throttle** (built, currently gated off). A gradient-boosted classifier (`HistGradientBoostingClassifier`) estimates the probability of a near-term drawdown and trims size further when risk is elevated. Trained with walk-forward, purged validation. It fails gracefully (returns a neutral 1.0 multiplier) if anything goes wrong, so it can never break a live run.

Both layers were validated before trusting them: purged / walk-forward cross-validation plus the **Deflated Sharpe Ratio** (Bailey and Lopez de Prado), which adjusts a backtest Sharpe down for how many strategy variants were tried. Across 11 configs the best strategy scored **DSR 99.4%**, meaning the edge is very unlikely to be a multiple-testing artifact.

---

## Architecture

```
main.py                    daily orchestrator (idempotent, duplicate-run guard)
├── data.py                Alpaca IEX -> yfinance -> parquet-cache fallback chain
├── trending.py            Claude web-search trending stock discovery
├── sentiment.py           Claude Haiku Batch API sentiment scoring
├── regime.py              3-signal market regime classifier
├── optimizer.py           MAX_SHARPE / HRP / HRP_MOMENTUM + adaptive selector
├── alpha_sleeve.py        Individual-stock momentum picks with quality filters
├── risk_overlay.py        Vol-targeting overlay + ML crash throttle
├── risk.py                Drawdown breaker, vol cap, concentration, correlation
├── broker.py              3-phase Alpaca rebalance (sells -> settle -> buys)
└── watchlist.py           Always-scanned anchor names

backtest.py                2019 -> today simulation with monthly rebalancing
test_risk_overlay.py       Unit tests for the overlay
config.py                  Every tuneable in one place
dashboard.py               Streamlit operations dashboard (dark, Plotly)
web/                       Public showcase page (Flask + animated front end)
.github/workflows/         Staggered cron schedule + idempotency for reliability
```

---

## Notable engineering decisions

- **Volatility targeting on leverage.** Holding 3x ETFs naked is a recipe for ruin. Wrapping them in a vol-targeting overlay keeps the upside capture while controlling the path, which is the difference between an interesting backtest and something you would actually run.
- **Validate before trusting.** Nothing ships without passing out-of-sample tests. Standing rule: compute the Deflated Sharpe Ratio on every new candidate before believing its Sharpe. A leave-one-year-out CV caught a temporal-leakage bug that a naive per-ticker split had hidden behind a fake positive result.
- **3-phase broker rebalance.** Naive implementations submit sells and buys together and lose half the buys to "insufficient buying power" because settlement lags. This bot submits all sells, polls `buying_power` for up to 90s, then sizes each buy against live cash. Sells are capped at 99.5% of position value to avoid float-precision rejections on full liquidations.
- **Cron resilience.** GitHub Actions' free-tier cron is unreliable (delays of 15 min to 3 hr are common). Solved with staggered cron entries through the morning plus a duplicate-run guard in `main.py`, so only the first successful run does work and the rest exit immediately.
- **Drawdown false-trigger fix.** A broker timeout once returned an equity of $0, which the drawdown breaker read as a -100% crash. Fixed by skipping the check when reported portfolio value is non-positive, so a transient API hiccup cannot flatten the book.
- **Data-source fallback chain.** Primary is Alpaca IEX (free, no rate limits). Falls back to yfinance with a browser-mimicking session header, then to a parquet on-disk cache from previous runs. The pipeline keeps running even if a vendor goes down.

---

## Tech stack

- **Python** (pandas, NumPy, SciPy, scikit-learn)
- **Anthropic Claude** (Haiku 4.5, Batch API, web-search tool)
- **Alpaca** (paper and live trading, IEX market data)
- **Streamlit + Plotly** (operations dashboard), **Flask + vanilla JS/SVG** (showcase page)
- **GitHub Actions** (cron scheduling, auto-commit, retries)
- **Quant methods:** Hierarchical Risk Parity, mean-variance / Max-Sharpe via SciPy SLSQP, volatility targeting, gradient-boosted crash classifier, Deflated Sharpe Ratio, purged cross-validation

---

## Strategies

| Strategy | When it runs | How it works |
|---|---|---|
| `HRP_MOMENTUM` | RISK_ON regimes | HRP base weights, absolute momentum filter, relative momentum tilt (top-3 boosted, bottom-3 trimmed) |
| `HRP` | CHOPPY regimes | Pure Hierarchical Risk Parity, robust, no return estimates required |
| `MAX_SHARPE` | RISK_OFF regimes | Classic mean-variance optimization with the full constraint set |

All three are then passed through the volatility-targeting overlay before any order is placed.

---

## Universe

A leveraged-ETF growth core with diversifiers, plus dynamically discovered individual stocks:

- **Growth core:** TQQQ, UPRO, UDOW, SOXL, TECL, QQQ, VGT, MTUM, IWM, AVUV, BITO, VEA
- **Defensive / cash:** GLD, TLT, SHV
- **Anchor watchlist:** NVDA, TSLA, AAPL, PLTR, COIN
- **Dynamic discovery:** up to 30 trending tickers per day via Claude web search

---

## Front ends

**Operations dashboard** (`dashboard.py`): dark Streamlit dashboard for monitoring the bot. Equity curve, allocation donut, holdings table, sentiment grid, regime indicator, watchlist alerts, plus dry-run and force-rebalance tools.

```bash
streamlit run dashboard.py
```

**Showcase page** (`web/`): a clean, light, public-facing page that reads the bot's logs and the live Alpaca account value and presents them like a real fund tearsheet. Animated hero, live portfolio value, a portfolio-vs-SPY chart with `1W / 1M / YTD / ALL` ranges and a hover tooltip, since-inception metrics, current holdings, and the validated backtest numbers. It is strictly read-only and never touches the bot.

```bash
python3 web/app.py     # then open http://localhost:5050
```

See `web/README.md` for details.

---

## Operating cost

| Service | Usage | Cost |
|---|---|---|
| Anthropic (Haiku Batch + web search) | ~30 tickers/day x 22 trading days | ~$1 to $3 / month |
| Alpaca paper trading | unlimited | $0 |
| Alpaca IEX data | unlimited | $0 |
| GitHub Actions | ~3 min/day x 22 days | Free tier |
| **Total** | | **under $3 / month** |

---

## Run it

```bash
git clone https://github.com/Tyler-Morton/BeatTheComp.git
cd BeatTheComp
pip install -r requirements.txt
cp .env.example .env   # fill ALPACA_API_KEY, ALPACA_SECRET_KEY, ANTHROPIC_API_KEY

python3 backtest.py    # 2019 -> today historical simulation
python3 main.py        # one live pipeline run
streamlit run dashboard.py   # operations dashboard
python3 web/app.py           # public showcase page
```

Paper to live is one env var: `ALPACA_BASE_URL=https://api.alpaca.markets`.

---

## Security

- Secrets live only in `.env` (gitignored, never committed). `.env.example` is a placeholder template.
- The GitHub Actions workflow reads keys from repository secrets, never from the codebase.
- The showcase page is read-only: it reads CSV logs and asks Alpaca for the account value, but it cannot place trades or change any bot state.
