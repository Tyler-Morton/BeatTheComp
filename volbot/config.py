"""volbot config — the vol-premium (SPY iron condor) paper sleeve.

ISOLATED from the champion/challenger bots: its own keys, its own account, its own logs.
Nothing here can touch the other accounts.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE = Path(__file__).parent
load_dotenv(BASE.parent / ".env")

# ── KEYS: this bot's OWN paper account (separate from champion/challenger) ─────
# Add these to .env (gitignored). Get them from the NEW paper account on Alpaca.
API_KEY = os.getenv("VOLBOT_ALPACA_API_KEY")
SECRET_KEY = os.getenv("VOLBOT_ALPACA_SECRET_KEY")

# ── SAFETY GUARDS ─────────────────────────────────────────────────────────────
PAPER = True          # hard paper guard — there is no code path that flips this to live
DRY_RUN = False       # ARMED: places real PAPER condors when filters pass.
                      # (Set back to True any time to go log-only without trading.)

# ── STRATEGY (validated: SPY iron condor, ~16Δ, ~30 DTE, expire-worthless, rich-vol) ──
UNDERLYING = "SPY"        # Alpaca has no index options (SPX/XSP); SPY is the tradeable equiv
TARGET_DTE = 30           # days-to-expiry we aim for at entry
DTE_MIN, DTE_MAX = 25, 38 # accept an expiry in this window (to hit a listed Friday)
SHORT_DELTA = 0.16        # ~16-delta short strikes, both sides
WING_WIDTH = 5.0          # $ width of each vertical (this IS the defined max loss)
RISK_FRAC = 0.06          # max loss per condor as a fraction of equity. Targets ~8%/yr (modeled).
                          # Sharpe (~1.6) is INVARIANT to this; only return & drawdown scale.
                          # 0.02≈3%/yr (-3% maxDD) · 0.04≈6% (-6%) · 0.06≈8% (-9%). Dial to taste.
LOSS_STOP_MULT = 2.0      # close if cost-to-close >= this * credit received
CLOSE_AT_DTE = 1          # let it ride to expiry; close at/under this DTE (dodge assignment)

# ── ENTRY FILTERS (all must pass to open a new condor) ────────────────────────
VRP_TERCILE = 0.66        # rich-vol gate: VRP (VIX - 20d realized) must be in its top tercile
VRP_LOOKBACK = 252        # rolling window for the VRP percentile
REALIZED_WIN = 20         # trading days for realized vol
VIX_MAX = 30.0            # don't sell into a spike
REQUIRE_CONTANGO = True   # VIX < VIX3M (term structure not inverted)

# ── MISC ──────────────────────────────────────────────────────────────────────
RISK_FREE = 0.04          # for the Black-Scholes delta calc used to pick strikes
STATE_FILE = BASE / "volbot_state.json"
LOG_FILE = BASE / "volbot_log.csv"
