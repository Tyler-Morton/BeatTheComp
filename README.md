# IWillBeatS&P: paper-trading bots and a pre-registered research ledger

Two rule-based portfolios trade on Alpaca paper accounts every market morning. GitHub Actions runs them and commits their logs back to this repo. The goal is to beat the S&P 500 on a risk-adjusted basis. Over about five months neither live book has kept up with SPY, which is too short a record to conclude much from. A third book, VolBot, sold index option premium until it failed a test on real option quotes and was retired. Alongside the books is a ledger of pre-registered experiments, and this README reports its results, failures included.

Claude Code wrote much of the code. I set the design, ran the research and made the calls.

All accounts are paper. `broker.py` refuses to start if `PAPER_TRADING_MODE` is off or `ALPACA_BASE_URL` is not a paper endpoint, and `tests/test_broker.py` covers both cases. VolBot builds its client with `PAPER = True`. Trading real money would take a code change.

---

## Where things stand (2026-11-05)

| Book | What it is | State | Equity log |
|---|---|---|---|
| Champion (`main.py`) | Regime-switching optimizer over ETFs that include 3x funds, 20% vol target | Trades daily | $1,000.00 (2026-05-22) to $842.43: -15.8%, SPY +3.8% |
| Challenger (`challenger/`) | Diversified 3-sleeve book, 16% vol target | Trades daily | $1,000.02 (2026-06-10) to $996.93: -0.3%, SPY +4.6% |
| VolBot (`volbot/`) | Laddered iron condors on SPY, QQQ and IWM | Retired 2026-10-13, no positions since 2026-08-24 | $100,000 to $99,921.26 |
| V3 shadow (`shadow_v3.py`) | Hypothetical champion variant, places no orders | Logging since 2026-10-14 | 17 rows, too few to read |
| Meta-book (`metabook/shadow.py`) | Equal-risk-contribution weights across the three books, places no orders | No schedule, one logged row (2026-07-01) | None |

SPY is the adjusted close in `prices_cache.parquet`, from the session before each book's first row to the session before its latest row. Equity is logged during the morning run. EXP-021 found that the paper account does not appear to be paid dividends (about 73 bp over four months on the challenger), while adjusted SPY includes them, so the comparison leans against the books.

The champion's largest loss was 2026-06-05: -19.0% in one session, with about 96% of the book in 3x ETFs. Its log is missing 21 trading days between 2026-06-24 and 2026-07-24 because of a log-commit bug, since fixed.

---

## The champion's daily run

1. **Guards.** Exits if today's row already exists or the market is closed.
2. **Prices.** Pulls 252 days of adjusted closes for 14 ETFs plus SPY from Alpaca IEX, then yfinance if that fails, then a parquet cache up to 48 hours old.
3. **Regime.** A majority vote of three signals (SPY 20-day vol, SPY 50/200-day trend, SPY vs TLT over 10 days) gives `RISK_ON`, `CHOPPY` or `RISK_OFF`.
4. **Strategy.** The regime picks from the table below. A 60-day Sharpe replay of all three can override the pick if another clears a margin.
5. **Overlay.** Scales the book toward 20% annual vol and parks the rest in SHV.
6. **Checks.** Portfolio vol cap 90%, single-position cap 70% (SHV exempt), average pairwise correlation cap 0.85, 2% drift threshold. A drawdown breaker at -30% from the broker-equity high puts the book in de-risk-only mode. After 63 sessions the high-water mark rebases, which is a safety default and was not backtested.
7. **Orders.** Sells first, waits up to 90 seconds for them to finish, then buys against the cash that has landed. Leftover cash goes to SHV.
8. **Logs.** CSVs and the price cache are committed back to the repo.

| Strategy | Default regime | How it works |
|---|---|---|
| `HRP_MOMENTUM` | RISK_ON | HRP weights, an absolute momentum filter, then the top 3 boosted 60% and the bottom 3 trimmed 40% |
| `HRP` | CHOPPY | Plain Hierarchical Risk Parity |
| `MAX_SHARPE` | RISK_OFF | Mean-variance optimization (SciPy SLSQP) with regime limits that push it into TLT, GLD and SHV |

In practice HRP gives SHV about 99.96% of the book every day, because SHV's variance is so small. Under `RISK_ON` the 1% cap on SHV pushes that weight onto whatever passed the momentum filter, so the book is usually the top three momentum names at about a third each, before the overlay. If only one name passes, it goes to the 70% cap and the rest spreads evenly across names that failed the filter, which is how BITO reached a 43.8% target on 2026-11-05. That spill is an open bug.

**Universe.** QQQ, TQQQ, UPRO, SOXL, TECL, VGT, MTUM, IWM, AVUV, BITO, VEA, GLD, TLT and SHV. SPY is fetched for the regime signals and as the benchmark.

**What was cut.** The first version used Claude Haiku for trending-stock discovery, news sentiment and a stock-picking sleeve. Discovery and the sleeve were cut on 2026-06-23 and sentiment on 2026-07-20. The stock picks could not be backtested and concentrated the book, and sentiment showed little measurable edge. The code stays behind flags in `config.py`, and the daily run no longer calls the Anthropic API. A five-name watchlist (NVDA, TSLA, AAPL, PLTR, COIN) is still scanned through yfinance and logged, and it places no trades.

---

## The risk overlay

`risk_overlay.py` multiplies the book by 20% divided by its trailing 40-day realized vol, capped at 1, so it can cut exposure but never levers up. The overlay predates the ledger and was never pre-registered. These are the numbers on record, with Sharpe measured against a flat 4.5% hurdle:

| Simulation | Window | Trading cost | CAGR | Vol | Sharpe | Max drawdown |
|---|---|---|---|---|---|---|
| Monthly-rebalance sim (`perf_report.py`), graded 2026-07-12 | 2019-01 to 2026-07 | None | 13.9% | 18.7% | 0.553 | -28.1% |
| SPY, same window | 2019-01 to 2026-07 | None | 17.4% | 19.4% | 0.693 | -33.7% |
| Replica of the daily live logic (EXP-024) | 2020-01 to 2026-10 | 5 bp per $ traded | 9.46% | 19.2% | 0.333 | -39.7% |

In the graded window the champion lags SPY on return and on Sharpe, with a shallower drawdown. In the replica, turnover of 68.7x equity a year costs 3.44% a year, and the old breaker froze the book for 136 sessions in 2022-23, which is why the breaker now de-risks. The replica also does not reproduce the live book on 2026-06-05 (26.2% in 3x against about 96% live), and that gap is unexplained.

**ML crash throttle (shadow mode).** A `HistGradientBoostingClassifier`, retrained on each run, estimates the chance that SPY falls more than 5% within 10 days. Rows whose labels overlap the forecast are purged from training. Its would-be size multiplier goes in the `notes` column of `daily_log.csv` and does not touch sizing. No pre-registered experiment has tested it.

---

## Verdict engine

Backtests are graded by `research/verdict.py` (kept local), which writes `web/static/verdict.json`. It computes a Sharpe 95% CI from a 21-day block bootstrap, the Deflated Sharpe Ratio (Bailey and Lopez de Prado) with K read from a trial registry, and a 10,000-path Monte Carlo. Its labels are frozen: CONFIRMED (CI excludes zero and DSR at least 0.95), PROMISING (CI excludes zero or DSR at least 0.90), INSUFFICIENT (everything else).

| Report of 2026-07-12 | Years | Sharpe | 95% CI | K | DSR | Grade |
|---|---|---|---|---|---|---|
| Champion | 7.5 | 0.553 | -0.098 to 1.192 | 11 | 70.6% | INSUFFICIENT |
| Challenger | 20.4 | 0.637 | 0.251 to 1.052 | 4 | 99.97% | CONFIRMED |

CONFIRMED describes a backtest, and this report has not been regenerated since July:

- K is out of date. The ledger's running totals are now 16 (champion family) and 11 (challenger family), and the registry still holds 11 and 4.
- The challenger run used an engine with a same-bar look-ahead, measured at -0.025 Sharpe by the C2 audit and since fixed. Its configuration was the best of its K on the full window, with no holdout.
- The champion sim charges no trading cost and rebalances monthly, while the live book re-decides daily.
- VolBot was never graded by this engine.

For scale, EXP-021's replay of the challenger (2007-07 to 2026-06, same pre-fix engine) gives Sharpe 0.65 against SPY's 0.39 and max drawdown -24.4% against -55.2%.

---

## Research ledger

The written research log is at [`research-log/README.md`](research-log/README.md). The data files and code in `research/` stay local.

Each experiment has its hypothesis, data and numeric gate written down before the data is touched. Every variant counts toward K, the trial count in the Deflated Sharpe penalty. A cheap premise test (Part A) runs before strategy work (Part B), and holdouts stay sealed until a design clears in-sample. The rule is that a miss stays a miss, with no re-run on new parameters. EXP-014 broke that rule, as described below.

**Count as of 2026-11-05: 30 experiment ids**, which are EXP-001 through EXP-030 plus EXP-007b. There is no EXP-018. A pre-registered execution audit (C2) sits outside that count. The newest entry is dated 2026-10-14.

| Outcome | n | Experiments |
|---|---|---|
| Signal not found at its gate | 7 | 001, 003, 004, 006, 008, 012, 013 |
| Signal real, but the trade lost money or could not be implemented | 6 | 005, 007b, 010, 011, 015, 028 |
| Signal real, then gone before the holdout | 1 | 017 |
| Estimator or design change failed its own gate | 7 | 002, 019, 022, 023, 024, 025, 026 |
| Passed its gate, with a caveat | 4 | 009, 014, 020, 027 |
| Inconsistent or inconclusive | 2 | 021, 029 |
| Pilot with no gate | 1 | 007 |
| Open, no result yet | 2 | 016, 030 |

None of the four passes has changed what a live book holds. EXP-009 is a marginal premise result (P = 0.019, driven by the top correlation decile), and no strategy was built on it. EXP-014 did not replicate. EXP-020 passed against SPY, and its follow-up against T-bills failed. EXP-027 authorizes only the V3 shadow.

**Results that taught the most** (VolBot's EXP-010 has its own section):

- **EXP-004 and EXP-007b, median against mean.** 8-K listing-deficiency events showed a mean abnormal return of -6.36% at p = 0.0001 on 2022-2024. The one-shot holdout came back at +3.87%, against a required -3.18% or lower, while the median event still fell 7.52%. A few microcap squeezes set the mean a short book would earn. EXP-007b had the same shape: 168 earnings trades with a +6.1% median and a -4.3% mean.
- **EXP-011, testing cost first.** The implied correlation premium was real (+0.034, P = 0.024), and round-trip costs were 3.7 times the edge. Running the cost gate before any strategy work kept the bill to about $4.
- **EXP-015, Kalshi market making.** Over 300 markets and 120 days the quoting rule made +$165.08 at the front of the queue and -$7.17 at the primary queue depth, where $139.12 of spread earned met $133.60 of inventory loss.
- **EXP-017, a market becoming efficient.** The free National Blend of Models forecast carried information Kalshi's temperature prices lacked from 2021 to May 2025 (beta 0.259). On the sealed holdout, trading on disagreement lost 3.23 cents a contract over 7,316 trades, with 0 of 7 cities positive.
- **EXP-020 and EXP-025, using the right control.** A 30% managed-futures sleeve passed against SPY (holdout Sharpe +0.081, CAGR 2.74 points lower). A red team then showed that T-bills at the same weight pass three of its four gates. Tested against T-bills inside the challenger's overlay, it failed (Sharpe difference -0.039).
- **EXP-022, a better forecast that did not help.** EWMA beat trailing-40d vol on untouched 1990-2004 data (QLIKE ratio 0.981, Holm p 0.0001), and the proxy book's net Sharpe still fell 0.029 against a -0.02 bar.
- **C2 and EXP-024, where the champion's cost lives.** Fills cost 1 to 3 bp each, and the book turned over 71 to 93 times a year. Monthly re-decision cut turnover 75-84% and still failed, because a bootstrap SD of about 0.2 over 6.8 years cannot resolve the Sharpe gate.

A recount in the 2026-10-13 audit found two patterns. Public information was already in the price each time it was tested out of sample (004, 008, 013, 017). Premia that were real went to a cheaper holder, through tail risk in 007b and 010, spread in 011 and queue position in 015.

**Flaws the ledger discloses:**

- **A repeated miscount.** For three experiments I wrote that eleven or twelve experiments had died on transaction costs. A 2026-07-29 recount found 7 with absent signal and 4 where the signal was real. The false sentence stays in the ledger beside its correction.
- **EXP-014, a pass that should not have counted.** It re-ran the killed EXP-002 spec and moved Sharpe from 0.56 to 0.59. Its third condition was rewritten after the first two were known to pass, an undisclosed longer warm-up took COVID out of the HAR arm, and its forecast used one-day-stale inputs. EXP-019 then failed to replicate it (QLIKE ratio 0.976 against trailing-40d, Holm p 0.24). EXP-014 has no section of its own in the ledger, and its write-up is in its spec.
- **Weak gates.** EXP-012's threshold named no estimator, which left three correlation readings and a free choice among them. EXP-021's 6.0% tracking-error bar failed at 6.50%, and the morning equity snapshot alone contributes 6.06%. That result stays INCONSISTENT.
- **Weak spots in the tests.** `backtest.py` and `perf_report.py` charge no trading cost. EXP-008 and EXP-009 use today's index members, which adds survivorship bias. EXP-020's holdout was sealed from the code, but I already knew how trend had done in those years, and its proxy gate passed at 0.604 against 0.60.
- **Stale bookkeeping.** The ledger's K header and `trial_registry.json` lag its running totals. The champion's first 11 trials were back-filled as unnamed configs, and its regime map, override margins and weight cap were never pre-registered. EXP-015's last two parts have no pre-registration block.

**Still open.** EXP-016 scores once when its sample bar is met, with a final deadline of 2027-03-01. EXP-030 prices 94.1% of member-months against a 95% bar and needs CRSP for 61 unresolved delisted-name segments. If CRSP fails its cross-check or links too few of them, EXP-030 closes as INCONCLUSIVE-data.

---

## Data sources

| Source | Used for | Where |
|---|---|---|
| Alpaca market data | Champion's primary daily closes (IEX), VolBot's option quotes, research bars | `data.py`, `tracker.py`, `volbot/volbot.py`; EXP-004, 008 (adjusted daily), C2 (IEX 1-min), 023 (SIP 1-min) |
| yfinance / Yahoo | Champion's fallback, watchlist scan, `backtest.py`, long index history | `data.py`, `watchlist.py`, `backtest.py`; EXP-019, 022, 029; Yahoo chart API in EXP-020. EXP-030 tested Yahoo and rejected it (29 of 33 symbols, bar 90%) |
| Tiingo | Challenger's daily closes, most equity-book backtests | `challenger/main.py`, `challenger/backtest.py`, `perf_report.py`; EXP-001, 003, 005, 006 (cache); 002, 007b, 009, 011, 013, 014, 024 to 030 |
| Databento | `OPRA.PILLAR` option quotes and definitions; `EQUS.SUMMARY` daily bars | EXP-007, 007b (daily bars); 010, 011, 028 (`cbbo-1m`); audit against Tiingo (15 tickers, 498 days) |
| WRDS (CRSP, Fama-French) | CRSP daily returns and closing spreads to cross-check the bots' cached prices; Fama-French 5 + momentum factors for a descriptive attribution of the champion's backtest | `research/wrds/`, run 2026-10-20, outside the numbered ledger. EXP-030 may use CRSP for delisted names, which has not been done |
| Bloomberg Terminal | No recorded use. EXP-029's spec allowed a hand spot-check of about 10 gold dates, and the ledger records none | None |
| Massive.com API | 8-K event tags | EXP-004 |
| SEC EDGAR | 8-K Item 2.02 earnings dates, 10-K Item 1A text, XBRL company facts. An N-PORT sample was parsed and never used in an experiment | EXP-007b, 008, 030 |
| CFTC | Traders in Financial Futures positioning | EXP-013 |
| FRED | VIX family and T-bill rates | `volbot/volbot.py`; EXP-005, 009, 010, 020, 025, 028, 029 |
| AQR | Time Series Momentum factor, monthly | EXP-020, 025 |
| Ken French Data Library | Risk-free rate, industry returns | EXP-029 |
| World Gold Council | Daily gold fix | EXP-029 |
| fja05680/sp500 (GitHub) | Point-in-time S&P 500 membership | EXP-030 |
| Kalshi public API | Markets, quotes, trades, resolutions | EXP-015, 016, 017 |
| Polymarket public API | Snapshots for a Kalshi-Polymarket text matcher, no numbered experiment | `predmarket` collector |
| NOAA/NWS National Blend of Models | Temperature forecasts, through the Iowa Environmental Mesonet archive and NOAA's AWS bucket | EXP-017 |
| Claude Haiku (Anthropic) | Sentiment and discovery until disabled; 10-K language scoring | `sentiment.py`, `trending.py`; EXP-008 |
| Numerai, Kaggle | Side projects on Numerai's v5.2 tournament data and a Kaggle 1-year stock return dataset | Local only, not in the ledger, no bot uses them |

WRDS and Bloomberg are academic-licensed through the University of Utah and are validation-only. Neither feeds a bot, and no WRDS or Bloomberg data or number derived from it appears in this repo. The workflows commit one small price cache (`prices_cache.parquet`, from Alpaca or yfinance) and a yfinance watchlist log. The challenger's Tiingo prices stay local. `predmarket` is a separate private repo that collects Kalshi and Polymarket snapshots. It holds no API keys and places no orders.

---

## VolBot: what it was and what killed it

**What it was.** A separate $100,000 Alpaca paper account that sold iron condors on SPY, QQQ and IWM, at about 16 delta and 30 days to expiry, with wings about 1% of spot. It added at most one rung per underlying per week, up to 4 rungs each, risking 3% of equity per rung and 25% in total. It sold only when implied-minus-realized vol was in its top tercile, the underlying's vol index was under 30, and VIX was below VIX3M. Positions rode to expiry unless they hit a 2x-credit loss stop or reached 1 day to expiry. It started on 2026-06-24 and became the three-index ladder on 2026-07-01.

**Why it looked good.** Its backtest priced options with Black-Scholes from VIX and modeled about +21% a year, Sharpe 1.27 and a -13.7% max drawdown.

**What killed it.** On 2026-07-27 I compared live fills to the backtest for the first time. The model priced a SPY condor at 2.44, the real OPRA NBBO was 0.95, and Alpaca's paper quote was 0.82. The model counted days to expiry in trading days while the bot targets calendar days, and it had no call skew. The live bot also picked call strikes with flat VIX, so the 16-delta short call on the SPY rung that was checked was really about 2.7 delta.

EXP-010 then re-ran the sleeve on six years of Databento OPRA `cbbo-1m` quotes (2020-07 to 2026-07), with no pricing model in the P&L and the real bid and ask paid. The pre-registered bar was Sharpe 0.70.

| | Return/yr | Vol | Sharpe | Max drawdown |
|---|---|---|---|---|
| SPY | +14.8% | 16.9% | 0.64 | -25.4% |
| VolBot as built | -8.0% | 8.1% | -1.54 | -40.6% |
| VolBot as designed (skew-aware strikes) | -10.4% | 11.9% | -1.24 | -49.0% |

That was 334 condors at -$118 a trade, losing in 6 of 7 calendar years. Of the condors that reached expiry, 92% won. But 46% hit the loss stop first, and because the bot checks once a day, stops filled at a median 2.25x and a mean 2.58x of credit, with a maximum of 14.03x. With perfect 2x stops the total would still have been -$10,775, against the actual -$39,314. Quote coverage was 90.9% and 93.5%, just inside the limit for calling the test inconclusive. The first run printed Sharpe 1.76 and PASS because credit was counted twice. I did not believe a result that beat the inflated model, and that is how the bug got found.

**Live record.** Six paper condors opened between 2026-07-13 and 2026-07-28. Three expired worthless and three hit the stop, for a net -$68 (`volbot/volbot_trades.csv`), which is too small a sample to support anything. The expiry-day exit path also crashed on Alpaca HTTP 500s on four dates in August.

**Current state.** Entries have been off since 2026-07-28 (`ENTRIES_ENABLED = False`), following the rule set before the test that a fail means no tuning. The account has held no positions since 2026-08-24. The schedule was removed on 2026-10-13, so `volbot.yml` runs only by manual dispatch. Code, state and logs stay in the repo.

---

## The challenger and the V3 shadow

**Challenger.** Core 45% (a QQQ/QLD ramp from 0 to 1.5x based on QQQ's distance from its 200-day average, with IEF as the cushion), low-vol 28% (XLP, XLU, XLV), ballast 27% (TLT and GLD, inverse-vol). A trend sleeve was tested, lost to its own absence and sits at budget 0. Sleeve weights are recomputed monthly and the 16% vol scaler daily, with the remainder in SHV. It has its own account, logs and workflow.

**V3 paper shadow.** `shadow_v3.py` runs a hypothetical champion variant next to the live book every trading day and places no orders. V3 re-decides regime, strategy and optimizer weights only on the first session of each month, and it caps total target weight in TQQQ, UPRO, SOXL and TECL at 30%, with the excess in SHV.

EXP-027 tested this on the sealed 2011-2018 window at 5 bp. Turnover was 11x a year against 72x, the 1% expected shortfall was about 35% smaller, and max drawdown was -27.7% against -35.0%. It was not shown to beat the champion on Sharpe (90% CI of the difference -0.034 to +0.652), and a red-team rebuild attributed about half of that difference to timing luck. Replacing the champion needs a separate pre-registered live-vs-shadow check after at least 60 sessions, an explanation of the 2026-06-05 replica gap, and my sign-off.

The workflow runs the shadow as its own step after the champion's logs are committed. That step gets no secrets and is `continue-on-error`, and it writes only `shadow_v3_state.json` and `shadow_v3_log.csv`. Tests check that it never touches the broker and that the champion's targets are identical with and without it.

---

## Architecture

```
main.py                    champion's daily run, with a duplicate-run guard
├── data.py                Alpaca IEX -> yfinance -> parquet-cache fallback
├── regime.py              3-signal regime vote
├── optimizer.py           MAX_SHARPE / HRP / HRP_MOMENTUM + adaptive selector
├── risk_overlay.py        Vol target + shadow ML crash throttle
├── risk.py                Drawdown breaker, vol, concentration, correlation, drift
├── broker.py              Paper guard, sell-then-buy rebalance, cash sweep
├── watchlist.py           Logged watchlist scan, no trades
└── sentiment.py, trending.py, alpha_sleeve.py   disabled by config flags

config.py                  Champion settings
backtest.py                2019 -> today, monthly rebalance, no trading cost
perf_report.py             Deployed-config simulation vs SPY (Tiingo)
tracker.py, vs_spy.py      Books vs SPY, from the paper accounts
dashboard.py               Streamlit dashboard: equity, allocation, dry-run and
                           force-rebalance tools (force-rebalance places paper trades)
web/                       Read-only trading desk bound to 127.0.0.1 (Flask + vanilla
                           JS/SVG); the research page needs the local research/ folder
tests/, test_risk_overlay.py   88 offline tests (network calls are blocked)
.github/workflows/         Dispatch and fallback cron, log commits

challenger/                3-sleeve book, own paper account, own daily workflow
volbot/                    Retired condor sleeve; code, state and logs kept
shadow_v3.py               V3 shadow logger, no secrets, no orders
metabook/                  ERC shadow allocator, one logged row, not scheduled
```

**Stack:** Python (pandas, NumPy, SciPy, scikit-learn), Alpaca, Streamlit and Plotly, Flask, GitHub Actions. See `web/README.md` for the trading desk.

---

## Engineering notes

- **Paper guard.** `ALPACA_BASE_URL` used to decide paper or live, so one env var could have moved real money. `_require_paper()` now returns True or raises, and the trading client always gets that value.
- **Sell-then-buy rebalance.** Submitting sells and buys together loses buys while sells are pending. The bot closes full exits with `close_position`, caps partial sells at 99.5% of position value to avoid float-precision rejections, polls sell orders for up to 90 seconds, and sizes each buy against the lesser of cash and buying power. This is not fully settled: 8 of the 14 sessions from 2026-10-19 to 2026-11-05 log a target shortfall above 2%, up to 59.1% on 2026-11-05. That check runs seconds after the orders, so some of it may be orders still pending, and I have not separated the two.
- **Trigger reliability.** GitHub's cron can lag by hours, so cron-job.org posts a `repository_dispatch` at 6:30 AM PT. Staggered crons stay as a fallback, and the duplicate-run guard makes extra firings exit.
- **Log commits.** Commit failures used to be silent, and one was a `git add` error hidden by `|| true`. Those failures cost the 21 missing days above. A failed push now fails the job.
- **Bad data.** Broker glitches once wrote $0.00 and $0.30 equity rows, so the run now aborts on a non-positive read and the breaker ignores implausible values. Raw Alpaca bars made VGT's 8:1 split look like a -87.5% day, so bars are now adjusted and a one-day move above 45% is refused.

---

## Operating cost

| Service | Usage | Cost |
|---|---|---|
| Anthropic | No calls from the daily run since 2026-07-20 | $0 |
| Alpaca paper trading and IEX data | Three paper accounts, two active | $0 |
| Tiingo | 12 symbols a day for the challenger. A paid plan was used during the EXP-030 data build | Not recorded in the repo |
| GitHub Actions | About 3 minutes per real run, public repo | Free tier |
| Databento (research) | EXP-007b, 010, 011 and 028 plus the data audit | About $19 logged |

---

## Run it

```bash
git clone https://github.com/Tyler-Morton/BeatTheComp.git
cd BeatTheComp
pip install -r requirements.txt pytest
cp .env.example .env   # fill ALPACA_API_KEY, ALPACA_SECRET_KEY

python3 -m pytest                    # 88 offline tests
python3 backtest.py                  # 2019 -> today, no trading cost
python3 main.py                      # one run; places paper orders if the market is open
python3 challenger/main.py --dry-run # no orders
streamlit run dashboard.py
python3 web/app.py                   # http://localhost:5050
```

The challenger also needs `CHALLENGER_ALPACA_API_KEY`, `CHALLENGER_ALPACA_SECRET_KEY` and `TIINGO_API_KEY`, which are listed in `.env.example`.

---

## Security

- Secrets live only in `.env`, which is gitignored and has never been committed. `.env.example` is a placeholder template.
- The workflows read keys from repository secrets. The V3 shadow step gets none.
- The trading desk does not load `.env` or import a broker client, and it has no write routes. It reads the CSV logs, price caches, git history, `alerts.log` and the local research ledger.
