# volbot — vol-premium SPY iron-condor paper sleeve

A 4th, **isolated** paper sleeve that harvests the variance risk premium by selling defined-risk
SPY iron condors, only when vol is expensive (rich-vol timing) and the term structure is calm.
Validated in backtest at ~1.6 net Sharpe / DSR ~0.99 / worst month ~−1.6% / corr-to-SPY +0.35.
Full design + evidence: `research/volbot_spec.md`.

> **This is a MODELED edge.** The paper forward-test is the validation gate. We are gathering the
> one thing that can't be overfit: do real SPY option fills match the modeled premium?

## Setup (one time)
1. **Create / open the NEW paper account** on Alpaca (separate from champion & challenger).
2. **Generate paper API keys** and add them to the repo's `.env` (gitignored):
   ```
   VOLBOT_ALPACA_API_KEY=PK...
   VOLBOT_ALPACA_SECRET_KEY=...
   ```
3. **Account settings on that paper account:**
   - **Options Level 3** — paper accounts have it automatically. Nothing to apply for.
   - **Margin account** (not cash) — needed to hold spreads (~$1,000 margin/spread). Paper starts
     at $100k, well over the $2k minimum. Defined-risk spreads do **not** borrow money — the
     "margin" is just collateral for the capped max loss. No loan, no interest, and it's paper.
   - Options data: the default free feed is fine (daily cadence).

## Run
```
cd volbot
python volbot.py
```
- **`DRY_RUN = True`** (default in `config.py`): computes and logs the intended trade, submits
  NOTHING. Watch a few runs — confirm it pulls the chain, picks ~16Δ strikes ~30 DTE, and shows a
  sane credit. Then flip `DRY_RUN = False` to actually paper-trade.
- Runs once per invocation (one daily "tick"). Wire it to GitHub Actions / cron later, like the
  other bots, once you trust it.

## What it does each run
1. Pulls SPY price, VIX, VIX3M (FRED), 20d realized vol → VRP and its rolling top-tercile.
2. If a condor is open: hold it (expire-worthless), unless cost-to-close ≥ 2× credit (loss-stop)
   or it's ≤ 1 DTE (close to dodge assignment).
3. If flat AND (VRP rich AND VIX < 30 AND contango): open one ~30-DTE, ~16Δ, $5-wide condor sized
   to risk 2% of equity as max loss.
4. Logs to `volbot_log.csv`; open-position state in `volbot_state.json`.

## Safety
- Own keys, own account, own logs — **cannot touch champion/challenger.**
- `PAPER = True` hard guard; no path to live.
- `DRY_RUN` gate so nothing trades until you flip it.

## Files
- `config.py` — all parameters + the safety guards.
- `volbot.py` — data, filters, strike selection, sizing, orders, management, run.
