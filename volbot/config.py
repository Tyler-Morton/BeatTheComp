"""volbot config — LADDERED 3-index vol-premium paper sleeve (v2).

v2 = the backtested ladder upgrade (research/volbot_ladder_backtest.py):
  - 3 underlyings (SPY/QQQ/IWM), each gated by its OWN vol index (VIX/VXN/RVX)
  - a new condor allowed every ~week per underlying (overlapping "rungs")
  - per-rung risk 3% of equity, max 4 rungs per underlying, 25% total at-risk cap
  - same validated entry/management rules as v1 (16-delta, ~30 DTE, rich-vol tercile,
    market contango, IV<30, EXPIRE-WORTHLESS, 2x loss-stop)
Modeled (2020-2026, net, real bill yields): ~+21%/yr, 12.3% vol, Sharpe 1.27, maxDD -13.7%.
Still ISOLATED from champion/challenger: own keys, own account, own logs.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE = Path(__file__).parent
load_dotenv(BASE.parent / ".env")

# ── KEYS: this bot's OWN paper account (separate from champion/challenger) ─────
API_KEY = os.getenv("VOLBOT_ALPACA_API_KEY")
SECRET_KEY = os.getenv("VOLBOT_ALPACA_SECRET_KEY")

# ── SAFETY GUARDS ─────────────────────────────────────────────────────────────
PAPER = True          # hard paper guard — there is no code path that flips this to live
DRY_RUN = False       # ARMED (v2 ladder verified in dry-run 2026-07-01): places real PAPER condors

# ── UNDERLYINGS: ETF -> its CBOE vol index on FRED ────────────────────────────
UNDERLYINGS = {"SPY": "VIXCLS", "QQQ": "VXNCLS", "IWM": "RVXCLS"}
TERM_NEAR, TERM_FAR = "VIXCLS", "VXVCLS"   # market-wide contango gate: VIX < VIX3M

# ── LADDER STRUCTURE (pre-registered in the backtest — do not tune) ───────────
ENTRY_GAP_DAYS = 7        # min calendar days between entries on the SAME underlying (~5 trading days)
MAX_RUNGS_PER = 4         # max concurrent condors per underlying
RISK_PER_RUNG = 0.03      # each condor's max loss = 3% of account equity
TOTAL_RISK_CAP = 0.25     # total max-loss across ALL open rungs <= 25% of equity

# ── CONDOR STRUCTURE (validated v1 rules, unchanged) ──────────────────────────
TARGET_DTE = 30           # days-to-expiry we aim for at entry
DTE_MIN, DTE_MAX = 25, 38 # accept an expiry in this window
SHORT_DELTA = 0.16        # ~16-delta short strikes, both sides
WING_FRAC = 0.01          # wing width ~= 1% of spot (rounded to a listed strike)
LOSS_STOP_MULT = 2.0      # close a rung if cost-to-close >= this * credit received
CLOSE_AT_DTE = 1          # ride to expiry; close at/under this DTE (dodge assignment)

# ── BETA PARKING (VB-2, registered 2026-07-20) ────────────────────────────────
# The account's idle option collateral buys SPY, so the book earns beta + the
# premium overlay instead of premium on a pile of dead cash ("compete with SPY
# by owning it and stacking the edge on top"). A cash reserve always stays
# behind to collateralize the condors. Condor P&L stays fully separable in the
# logs, so this does NOT contaminate the premium-edge evaluation.
# DEFERRED 2026-07-26 — the code is finished and correct; only the switch is off.
#
# Enabling it as written would have bought $85,331 of SPY on the 2026-07-27 run,
# 86% of a $99,441 account. The comment above claims parking doesn't contaminate
# the premium-edge evaluation because condor P&L stays separable in the logs.
# That is true for ACCOUNTING (volbot_trades.csv isolates it) but NOT for RISK:
# long SPY and short puts lose in the same event, so the two legs are additive on
# the downside, not independent. At the time of deferral the short puts had only
# ~4% cushion (IWM 279/278 vs spot 291.19, SPY 710 vs 738.90) and IWM had fallen
# four sessions running. A 10% SPY move would have cost ~$8.5k on the park plus
# ~$8.2k of condor max loss — about 17% of equity, with both legs maxing together.
#
# RE-ENABLE AFTER 2026-08-21, once the three open rungs (IWM 08-14, IWM 08-21,
# SPY 08-21) have settled and volbot_trades.csv holds its first clean per-condor
# P&L readings. Revisit sizing then — PARK_MAX_FRAC or PARK_SYMBOL="SHV" both
# bound the correlated downside that the unbounded SPY version does not.
BETA_PARK = False
PARK_SYMBOL = "SPY"
PARK_RESERVE_MULT = 2.0     # keep cash >= this x total max-loss at risk...
PARK_MIN_RESERVE = 10_000   # ...and never below this floor
PARK_TRADE_MIN = 500        # ignore SPY adjustments smaller than this (no churn)

# ── ENTRY FILTERS (per underlying, all must pass) ─────────────────────────────
VRP_TERCILE = 0.66        # rich-vol gate: VRP (IV - 20d realized) in its top tercile
VRP_LOOKBACK = 252        # rolling window for the VRP percentile
REALIZED_WIN = 20         # trading days for realized vol
IV_MAX = 30.0             # don't sell into a spike (per underlying's own vol index)
REQUIRE_CONTANGO = True   # market term structure not inverted (VIX < VIX3M)

# ── MISC ──────────────────────────────────────────────────────────────────────
RISK_FREE = 0.04          # for the Black-Scholes delta calc used to pick strikes
STATE_FILE = BASE / "volbot_state.json"
LOG_FILE = BASE / "volbot_log.csv"
# One row per CLOSED condor (not per day). volbot_log.csv is a daily snapshot and
# cannot answer "did the premium edge actually show up?" — a rung's whole life
# collapses into a free-text note and then disappears from state. This is the
# per-trade ledger that makes the sleeve evaluable against the backtest.
TRADES_FILE = BASE / "volbot_trades.csv"
