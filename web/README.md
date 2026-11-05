# Trading desk dashboard

A read-only web dashboard for the three paper books.

## Run it

```bash
python3 web/app.py            # http://localhost:5050  (PORT=xxxx to change)
```

## Screens

| Route | What it shows |
|---|---|
| `#/desk` | Each book's equity, last-session P&L, return vs SPY, max drawdown, live Sharpe and last-run status (ran / missed / failed). Below that, all books rebased to 100 vs SPY, meta-book shadow weights and the latest research entries |
| `#/book/<champion\|challenger\|volbot>` | Equity vs SPY with the same starting capital, and drawdown. Champion and challenger add holdings, allocation over time, risk overlay (champion: gross exposure and regime strip; challenger: vol scaler), turnover, rebalance log and the backtest grade from `verdict.json`. VolBot adds closed trades, IV and capital at risk |
| `#/research` | The experiment ledger parsed from `research/experiments.md`, with a status filter, search and each entry's key line |
| `#/health` | Last GitHub Actions runs (via the local `gh` CLI), data freshness per log, `alerts.log`, recent commits |

## JSON API

`/api/desk`, `/api/book/<id>`, `/api/research`, `/api/health`. All GET, no auth, bound to 127.0.0.1.

## Where the data comes from

- Equity, weights, regime, overlay: `daily_log.csv`, `challenger/daily_log.csv`, `volbot/volbot_log.csv`, `volbot/volbot_trades.csv`, `volbot/volbot_state.json`, `regime_log.csv`, `metabook/shadow_log.csv`
- SPY: `prices_cache.parquet`, plus `challenger/live_prices.parquet` if it's on disk. The challenger writes that one during a run, and it isn't committed.
- Backtest grade: `web/static/verdict.json` (written by `research/verdict.py`)
- Research ledger: `research/experiments.md`. It is gitignored, so in a git worktree the app looks in the main checkout. Override with `DESK_RESEARCH_DIR`.
- Alerts: `alerts.log`. Also gitignored, with the same fallback to the main checkout.
- Workflow runs: `gh run list` (cached 2 min). Set `DESK_NO_GH=1` to skip it.

## Definitions

- **Run status.** *Ran*: the log has a row with a usable equity value for the latest trading day that should have run (before 17:00 UTC, that is the previous trading day, and the last cron is at 16:10 UTC). *Missed*: it doesn't. *Failed*: the latest GitHub Actions run of that book's workflow concluded `failure`. NYSE holidays are excluded, and the list in `app.py` only covers 2026 and 2027. VolBot's workflow is manual-only now, so VolBot shows Missed unless someone runs it.
- **Log gaps.** A book page lists any stretch of more than 6 calendar days with no usable log row, like the champion's Jun 23 to Jul 27 gap (22 sessions). The charts draw a straight line across it.
- **Sharpe (live).** Simple daily returns from the logged equity, annualized by sqrt(252), zero risk-free rate. With under ~126 sessions the book page says the sample is short.
- **vs SPY.** Book return minus SPY return over the book's own logged window. The SPY closes are dividend-adjusted, so this includes dividends.
- **Research status.** Read from each entry's `**Status:**` line, `### RESULT` headers and `**VERDICT**` lines. A kill or fail in any of those is FAIL, even if a premise gate passed first (those are tagged "premise held"). MEASURED is a measurement with a written result and no pass/fail verdict.

## Read-only

The app has no write routes, doesn't import a broker client and doesn't read any key from the environment.
It only reads files and runs `git log`, `git rev-parse` and `gh run list`.

`app.run` gets `load_dotenv=False`, so the app doesn't load `.env`. Flask's default would load it, because `requirements.txt` installs python-dotenv, and the broker keys would end up in the process and get passed on to `git` and `gh`. Start the app with `python3 web/app.py` as shown above, since `flask run` loads `.env` on its own.
