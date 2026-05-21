# AI Portfolio Optimization Bot

An AI-powered, fully automated portfolio bot designed to outperform the S&P 500.  
Runs daily via GitHub Actions, rebalances on Alpaca (paper or live), and serves a live Streamlit dashboard.

---

## Architecture

```
main.py  ← daily orchestrator (GitHub Actions triggers this)
  ├── data.py         — yfinance price fetching
  ├── sentiment.py    — Claude Haiku Batch API, web search per ticker
  ├── watchlist.py    — alert scanner (never auto-trades)
  ├── regime.py       — 3-signal majority vote: RISK_ON / CHOPPY / RISK_OFF
  ├── optimizer.py    — MAX_SHARPE | HRP | HRP_MOMENTUM (default)
  ├── risk.py         — drawdown breaker, vol scaling, concentration, correlation
  └── broker.py       — Alpaca paper/live trading

backtest.py    — full historical simulation 2019–today, saves charts + CSV
dashboard.py   — Streamlit UI (run with check.sh)
config.py      — all tuneable parameters in one place
```

---

## Setup

### 1. Clone and install

```bash
git clone <your-repo-url>
cd IWillBeatS\&P
pip install -r requirements.txt
```

### 2. Configure secrets

```bash
cp .env.example .env
# Edit .env — fill in your Alpaca and Anthropic API keys
```

### 3. Run the backtest (generates charts + CSV immediately)

```bash
python backtest.py
```

This downloads price history from 2019, simulates all three strategies monthly,
and writes `backtest_results.png` and `quarterly_backtest.csv`.

### 4. Open the dashboard

```bash
./check.sh
# Or manually: streamlit run dashboard.py
```

---

## Daily pipeline

```bash
python main.py
```

Runs once per trading day (or via GitHub Actions at 9:45 AM ET):

1. Market-open check — exits cleanly if closed  
2. Fetch 252 days of price data  
3. Sentiment analysis (Claude Batch API) + watchlist scan — **parallel**  
4. Detect market regime (3-signal vote)  
5. Optimize with active strategy + sentiment + regime constraints  
6. Safety checks (drawdown, vol, concentration, correlation, drift)  
7. Rebalance on Alpaca if drift ≥ 5%  
8. Append row to `daily_log.csv`  

---

## Strategies

Switch via `ACTIVE_STRATEGY` in `config.py`:

| Strategy | Description |
|---|---|
| `HRP_MOMENTUM` | **Default.** HRP + absolute momentum filter + relative momentum tilt |
| `HRP` | Hierarchical Risk Parity — robust, no return estimates needed |
| `MAX_SHARPE` | Classic mean-variance, maximize Sharpe ratio |

---

## Adding / removing assets

Edit the `ASSETS` list in `config.py`. The optimizer and backtester automatically
adapt — no other changes needed. Tickers that fail to download are dropped
gracefully with a warning.

```python
# config.py
ASSETS = [
    "QQQ",
    "VGT",
    # add or remove any ETF here
]
```

---

## Paper → live trading

One line in `broker.py` controls this (or set via env var):

```python
# broker.py — TradingClient init
_client = TradingClient(
    api_key=...,
    secret_key=...,
    paper=False,    # ← change True → False for live
)
```

Or swap to live Alpaca API keys in `.env`:
```
ALPACA_BASE_URL=https://api.alpaca.markets
```

---

## GitHub Actions setup

1. Push this repo to GitHub  
2. Go to **Settings → Secrets and variables → Actions**  
3. Add each secret:
   - `ALPACA_API_KEY`
   - `ALPACA_SECRET_KEY`
   - `ANTHROPIC_API_KEY`
   - `EMAIL_USER` *(optional)*
   - `EMAIL_PASS` *(optional)*
4. The workflow runs automatically at 9:45 AM ET, Mon–Fri  
5. Trigger manually: **Actions → Daily Portfolio Rebalance → Run workflow**

After each run, updated CSV logs are committed back to the repo automatically.
Pull the latest with `./check.sh` before viewing the dashboard.

---

## Estimated monthly cost

| Service | Usage | Est. cost |
|---|---|---|
| Anthropic (Haiku Batch) | ~10 tickers/day × 22 trading days | ~$0.50–$1.50 |
| Alpaca paper trading | Free | $0 |
| GitHub Actions | ~2 min/day × 22 days | Free (within limits) |
| **Total** | | **< $2/month** |

> Batch API pricing is ~50% cheaper than standard API calls.  
> Web search tool may add minor additional cost per search.

---

## Risk parameters (config.py)

| Parameter | Default | Effect |
|---|---|---|
| `MAX_SINGLE_WEIGHT` | 35% | Max allocation to any one asset |
| `MIN_SINGLE_WEIGHT` | 2% | Minimum allocation (avoids zero positions) |
| `DRAWDOWN_CIRCUIT_BREAKER` | 15% | Pause trading if down >15% from ATH |
| `MAX_PORTFOLIO_VOL` | 25% | Scale to SHV if portfolio vol exceeds this |
| `REBALANCE_DRIFT_THRESHOLD` | 5% | Skip rebalance if max drift < 5% |

---

## File reference

| File | Purpose |
|---|---|
| `config.py` | All constants — edit this to tune the bot |
| `data.py` | yfinance price fetching with graceful failures |
| `regime.py` | Market regime detection (vol + trend + flight-to-safety) |
| `optimizer.py` | Three portfolio optimization strategies |
| `risk.py` | Pre-trade safety checks + email alerts |
| `sentiment.py` | Claude Batch API sentiment scoring |
| `watchlist.py` | Alert scanner for NVDA, PLTR, etc. |
| `broker.py` | Alpaca API — get positions, place orders |
| `backtest.py` | Historical simulation 2019–today |
| `dashboard.py` | Streamlit web UI |
| `main.py` | Daily orchestrator |
| `check.sh` | `git pull && streamlit run dashboard.py` |
| `.github/workflows/rebalance.yml` | GitHub Actions — runs at 9:45 AM ET |
| `daily_log.csv` | Per-day run log (auto-generated) |
| `sentiment_log.csv` | Per-ticker sentiment history |
| `regime_log.csv` | Regime detection history |
| `watchlist_log.csv` | Watchlist scan history |
| `watchlist_alerts.csv` | Triggered watchlist alerts |
| `quarterly_backtest.csv` | Backtest quarterly returns |
| `backtest_results.png` | Equity curves + quarterly chart + heatmap |
