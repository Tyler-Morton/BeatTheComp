# Trading desk dashboard

A read-only web dashboard for the three paper books. It replaces the old
public showcase page (still in git history before this commit).

## Run it

```bash
python3 web/app.py            # http://localhost:5050  (PORT=xxxx to change)
```

## Screens

| Route | What it shows |
|---|---|
| `#/desk` | Each book's equity, last-session P&L, return vs SPY, max drawdown, live Sharpe, last-run status (ran / missed / failed); all books rebased to 100 vs SPY; meta-book shadow weights; latest research entries |
| `#/book/<champion\|challenger\|volbot>` | Equity vs SPY with same starting capital, drawdown, holdings, allocation over time, risk overlay (champion: gross exposure + regime strip; challenger: vol scaler; volbot: capital at risk), turnover, rebalance log, VolBot's closed trades and IV, and the verdict-engine backtest grade |
| `#/research` | The experiment ledger parsed from `research/experiments.md`, filterable by status, with each entry's key line |
| `#/health` | Last GitHub Actions runs (via the local `gh` CLI), data freshness per log, `alerts.log`, recent commits |

## JSON API

`/api/desk`, `/api/book/<id>`, `/api/research`, `/api/health`. All GET, no auth, bound to 127.0.0.1.

## Where the data comes from

- Equity, weights, regime, overlay: `daily_log.csv`, `challenger/daily_log.csv`, `volbot/volbot_log.csv`, `volbot/volbot_trades.csv`, `volbot/volbot_state.json`, `regime_log.csv`, `metabook/shadow_log.csv`
- SPY: `prices_cache.parquet` and `challenger/live_prices.parquet`
- Backtest grade: `web/static/verdict.json` (written by `research/verdict.py`)
- Research ledger: `research/experiments.md`. It is gitignored, so in a git worktree the app looks in the main checkout. Override with `DESK_RESEARCH_DIR`.
- Workflow runs: `gh run list` (cached 2 min). Set `DESK_NO_GH=1` to skip it.

## Definitions

- **Run status.** *Ran*: the log has a row for the latest trading day that should have run (before 17:00 UTC, that is the previous trading day). *Missed*: it doesn't. *Failed*: the latest GitHub Actions run of that book's workflow concluded `failure`. NYSE holidays are excluded.
- **Sharpe (live).** Daily log returns, annualised by sqrt(252), zero risk-free rate. With under ~126 sessions the page says the sample is short.
- **vs SPY.** Book return minus SPY price return over the book's own logged window.
- **Research status.** Read from each entry's `**Status:**` line, `### RESULT` headers and `**VERDICT**` lines. A kill or fail anywhere in the entry is FAIL, even if a premise gate passed first (those are tagged "premise held"). MEASURED is a measurement with a written result and no pass/fail verdict.

## Read-only by construction

The app does not load `.env`, import a broker client, or expose any write route.
It only reads files and runs `git log` and `gh run list`.
