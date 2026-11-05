# volbot v2: laddered vol-premium paper sleeve on SPY, QQQ and IWM

> **Retired 2026-10-13.** The scheduled workflow is off (`workflow_dispatch` only). Code, state
> and logs stay in place for the record. EXP-010 on real OPRA quotes (2020-07 to 2026-07) gave
> Sharpe -1.54 (-8.0%/yr, max drawdown -40.6%) against a pre-registered bar of 0.70, and the paper
> sleeve netted -$68 over 6 condors. Entries were halted 2026-07-28, the last rungs closed
> 2026-08-24 and the account has been flat cash since. The expiry-day exit path also crashed on
> Alpaca HTTP 500s (Aug 13/14/20/21).

An isolated paper sleeve in its own Alpaca account, separate from the champion and challenger. It
sold defined-risk iron condors on SPY, QQQ and IWM to harvest the variance risk premium. Each was
gated by its own vol index (VIX/VXN/RVX) and only traded when vol was expensive (rich-vol tercile)
and the term structure was calm. Entries laddered weekly per underlying (max 4 rungs each, 3% risk
per rung, 25% total at-risk cap).

Modeled (research/volbot_ladder_backtest.py, net, real bill yields): about +21%/yr, 12.3% vol,
Sharpe 1.27, max drawdown -13.7%, about 41 trades/yr, correlation to the equity sleeves about +0.2.
Full design and evidence: `research/volbot_spec.md` and `research/metabook_spec.md`. `research/` is
gitignored, so those stay local.

> That was a modeled edge, and the paper forward-test was the validation gate: would real option
> fills match the modeled premium? They didn't. Fills came in at 5-20% of wing width
> (`volbot_trades.csv`), under the 29-37% the backtest's pricing expects (`config.py`).

## Setup (one time)
1. Create or open the new paper account on Alpaca, separate from champion and challenger.
2. Generate paper API keys and add them to the repo's `.env` (gitignored):
   ```
   VOLBOT_ALPACA_API_KEY=PK...
   VOLBOT_ALPACA_SECRET_KEY=...
   ```
3. Account settings on that paper account:
   - Options Level 3. Paper accounts have it automatically, so there's nothing to apply for.
   - Margin account, not cash. It's needed to hold spreads (about $1,000 margin per spread). Paper
     starts at $100k, well over the $2k minimum. Defined-risk spreads don't borrow money: the
     margin is just collateral for the capped max loss, with no loan or interest.
   - Options data: the default free feed is fine at a daily cadence.

## Run
```
cd volbot
python volbot.py
```
- Runs once per invocation (one daily tick). `.github/workflows/volbot.yml` starts it by hand. It
  ran on a schedule until the sleeve was retired.
- `DRY_RUN = False` in `config.py`, so any order goes to the paper account. Set `DRY_RUN = True` to
  log the intended trade and submit nothing.
- `ENTRIES_ENABLED = False` in `config.py`, so a run only manages open rungs. There are none now.

## What it does each run
1. Pulls SPY/QQQ/IWM spots (Alpaca) and VIX/VXN/RVX plus VIX3M (FRED) to get each underlying's VRP
   and its rolling top tercile, plus the market-wide contango gate (VIX < VIX3M).
2. Manages every open rung: hold to expiry (expire-worthless), closing a rung only on the 2x-credit
   loss stop or at 1 DTE or less (assignment dodge).
3. Stops here while `ENTRIES_ENABLED` is False. Otherwise, entries per underlying: if its filters
   pass (rich VRP, own IV < 30, contango), it's been at least 7 days since that name's last entry,
   it has fewer than 4 open rungs, and total at-risk stays within 25% of equity, it opens one condor
   at about 30 DTE and 16 delta (wings about 1% of spot), sized to 3% risk. The order works a limit
   ladder from mid down to a credit floor (`MIN_CREDIT_FRAC`, 10% of wing width). If nobody pays the
   floor, it skips that rung.
4. Beta parking (`BETA_PARK`) would then put cash above a reserve into SPY. It's off, because long
   SPY and short puts lose in the same event (see `config.py`).
5. Logs to `volbot_log.csv`, one row per day. Each closed condor adds a row to `volbot_trades.csv`
   with its fill, exit cost and realized P&L. The rung list lives in `volbot_state.json`.

## Safety
- Own keys, own account, own logs, so it can't touch champion or challenger.
- `PAPER = True` hard guard, with no path to live.
- `ENTRIES_ENABLED = False` stops new trades, and a missing flag counts as off.
- `DRY_RUN` is there as a gate, but it's off.

## Files
- `config.py`: all parameters and the safety guards.
- `volbot.py`: data, filters, strike selection, sizing, orders, management, run.
- `volbot_state.json`: open rungs and the last entry date per underlying.
- `volbot_log.csv`: daily snapshot of equity, vol and at-risk.
- `volbot_trades.csv`: one row per closed condor.
