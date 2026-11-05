"""Config for volbot v2: laddered iron condors on SPY, QQQ and IWM, in its own paper account.

Retired. The research model showed about +21%/yr and Sharpe 1.27, but real quotes showed -8.0%/yr
and Sharpe -1.54 (EXP-010, see ENTRIES_ENABLED).
"""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE = Path(__file__).parent
load_dotenv(BASE.parent / ".env")

# This bot's own paper account, separate from champion and challenger.
API_KEY = os.getenv("VOLBOT_ALPACA_API_KEY")
SECRET_KEY = os.getenv("VOLBOT_ALPACA_SECRET_KEY")

# Safety guards
PAPER = True          # hard paper guard, no code path flips this to live
DRY_RUN = False       # False places real paper condors (v2 ladder was checked in dry run first)

# Each ETF is gated by its own CBOE vol index, pulled from FRED.
UNDERLYINGS = {"SPY": "VIXCLS", "QQQ": "VXNCLS", "IWM": "RVXCLS"}
TERM_NEAR, TERM_FAR = "VIXCLS", "VXVCLS"   # market-wide contango gate: VIX < VIX3M

# Ladder structure. Pre-registered in the backtest, so don't tune it.
ENTRY_GAP_DAYS = 7        # min calendar days between entries on the same underlying (about 5 trading days)
MAX_RUNGS_PER = 4         # max concurrent condors per underlying
RISK_PER_RUNG = 0.03      # each condor's max loss = 3% of account equity
TOTAL_RISK_CAP = 0.25     # total max loss across all open rungs <= 25% of equity

# Condor structure, same rules as v1.
TARGET_DTE = 30           # days-to-expiry we aim for at entry
DTE_MIN, DTE_MAX = 25, 38 # accept an expiry in this window
SHORT_DELTA = 0.16        # about 16-delta short strikes, both sides
WING_FRAC = 0.01          # wing width about 1% of spot, rounded to a listed strike
LOSS_STOP_MULT = 2.0      # close a rung if cost-to-close >= this * credit received
CLOSE_AT_DTE = 1          # ride to expiry; close at/under this DTE (dodge assignment)

# Execution. Entries used to be 4-leg market orders, which cross the full bid-ask four times.
# On 2026-07-27 an IWM condor priced at 0.51 mid filled at 0.15, so 71% of the credit was gone and
# the trade risked 2.85 to make 0.15 (1:19). The backtest assumed 0.015/leg, or 0.06/contract, and
# that fill cost 0.36, six times as much. Limit orders are an execution fix and don't change the
# strategy: they're meant to bring live fills back to what the model assumed.
USE_LIMIT_ORDERS = True
LIMIT_STEPS = 3           # price attempts before giving up (or going to market)
LIMIT_WAIT_SEC = 20       # seconds to leave each attempt working
# This only filters out garbage. It isn't a quality bar. The backtest's pricing expects 29-37% of
# width and live fills run 5-20%, so a floor anywhere near the model would stop the bot trading
# (both SPY rungs were at 11-12%). That gap is a real open question for research, and a threshold
# can't answer it. 10% rejects the 2026-07-27 IWM rung (5% of width, 1:19 reward:risk) and nothing
# else that has traded. Raise it only with evidence, never to improve results after seeing them.
MIN_CREDIT_FRAC = 0.10    # never open for less than this fraction of wing width
LIMIT_STEP_SLACK = 0.20   # on exits, concede up to +20% over mid across the ladder
# Entries are optional: if nobody pays the floor, skip. With 4 rungs per name and a weekly
# cadence, a missed entry is cheap and a bad fill isn't.
# Exits are mandatory: assignment dodges and loss stops have to complete, so they fall back to a
# market order after the limit ladder runs out.

# Beta parking (VB-2). Idle option collateral buys SPY, so the book earns beta plus the premium
# overlay instead of premium on dead cash. A cash reserve stays behind to collateralize the condors.
# Deferred: the code is finished and only the switch is off.
#
# Condor P&L stays separate in volbot_trades.csv, so the accounting is clean, but the risk isn't
# separate. Long SPY and short puts lose in the same event, so they add up on the downside. At
# deferral this would have put 86% of the account in SPY with only about 4% cushion on the short
# puts. A 10% SPY move would have cost about 17% of equity, with both legs maxing together.
#
# The plan was to revisit this once the rungs open at deferral had settled. They have, and the
# sleeve is retired, so it stays off. Re-enabling it would need sizing that bounds the correlated
# downside: a cap on the parked fraction (no such setting exists yet) or PARK_SYMBOL="SHV".
BETA_PARK = False
PARK_SYMBOL = "SPY"
PARK_RESERVE_MULT = 2.0     # keep cash >= this x total max-loss at risk...
PARK_MIN_RESERVE = 10_000   # ...and never below this floor
PARK_TRADE_MIN = 500        # ignore SPY adjustments smaller than this (no churn)

# Entries halted (EXP-010). On real OPRA quotes from 2020-07 to 2026-07 this sleeve loses money:
#   as built     -8.0%/yr, Sharpe -1.54, max drawdown -40.6%
#   as designed -10.4%/yr, Sharpe -1.24, max drawdown -49.0%
# The pre-registered bar was Sharpe >= 0.70. 334 condors, -$118/trade, losing in 6 of 7 years.
#
# The premise is fine: 92% of condors that reach expiry win. The strategy dies in the 46% that hit
# the 2x loss stop first, which executes at a median 2.25x and mean 2.58x (max 14x) because the bot
# only checks daily. Even perfect 2.0x stops are still negative, so the verdict doesn't rest on that.
#
# The pre-registered fail rule says don't tune. DTE, delta, wing width, stop multiple and tercile
# all become free variables the moment we start, and anything can be made to pass.
#
# Only new entries were stopped. Management stayed on so the 5 rungs open at the halt could ride to
# their Aug 14-28 expiries and volbot_trades.csv could give a paper comparison against the backtest.
# All 5 have closed: 3 expired worthless and 2 hit the loss stop.
ENTRIES_ENABLED = False

# Entry filters, per underlying. All must pass.
VRP_TERCILE = 0.66        # rich-vol gate: VRP (IV - 20d realized) in its top tercile
VRP_LOOKBACK = 252        # rolling window for the VRP percentile
REALIZED_WIN = 20         # trading days for realized vol
IV_MAX = 30.0             # don't sell into a spike (per underlying's own vol index)
REQUIRE_CONTANGO = True   # market term structure not inverted (VIX < VIX3M)

RISK_FREE = 0.04          # for the Black-Scholes delta calc used to pick strikes
STATE_FILE = BASE / "volbot_state.json"
LOG_FILE = BASE / "volbot_log.csv"
# One row per closed condor. volbot_log.csv is a daily snapshot and can't show whether the premium
# edge showed up, because a rung's whole life collapses into a free-text note and then disappears
# from state. This ledger is what lets the sleeve be compared against the backtest.
TRADES_FILE = BASE / "volbot_trades.csv"
