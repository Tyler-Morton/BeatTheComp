# volbot v2 — LADDERED 3-index vol-premium paper sleeve (SPY/QQQ/IWM)

A 4th, **isolated** paper sleeve that harvests the variance risk premium by selling defined-risk
iron condors on SPY, QQQ and IWM — each gated by its own vol index (VIX/VXN/RVX), only when vol
is expensive (rich-vol tercile) and the term structure is calm. Entries ladder weekly per
underlying (max 4 rungs each, 3% risk per rung, 25% total at-risk cap).
Modeled (research/volbot_ladder_backtest.py, net, real bill yields): ~+21%/yr, 12.3% vol,
Sharpe 1.27, maxDD −13.7%, ~41 trades/yr, corr-to-equity-sleeves ~+0.2.
Full design + evidence: `research/volbot_spec.md` + `research/metabook_spec.md`.

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
1. Pulls SPY/QQQ/IWM spots (Alpaca) + VIX/VXN/RVX + VIX3M (FRED) → per-underlying VRP and its
   rolling top-tercile, plus the market-wide contango gate (VIX < VIX3M).
2. Manages every open rung: hold to expiry (expire-worthless), closing a rung only on the
   2×-credit loss-stop or at ≤ 1 DTE (assignment dodge).
3. Entries per underlying: if its filters pass (rich VRP + own IV < 30 + contango), it's been
   ≥ 7 days since that name's last entry, it has < 4 open rungs, and total at-risk stays
   ≤ 25% of equity → open one ~30-DTE, ~16Δ condor (wings ≈ 1% of spot), sized to 3% risk.
4. Logs to `volbot_log.csv`; the rung list lives in `volbot_state.json`.

## Safety
- Own keys, own account, own logs — **cannot touch champion/challenger.**
- `PAPER = True` hard guard; no path to live.
- `DRY_RUN` gate so nothing trades until you flip it.

## Files
- `config.py` — all parameters + the safety guards.
- `volbot.py` — data, filters, strike selection, sizing, orders, management, run.
