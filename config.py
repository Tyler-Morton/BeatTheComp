from pathlib import Path

BASE_DIR = Path(__file__).parent

# ── Strategy ────────────────────────────────────────────────────────────────
# Only used as a backup if we turn off auto-select below.
ACTIVE_STRATEGY = "HRP_MOMENTUM"   # pick one: MAX_SHARPE | HRP | HRP_MOMENTUM
# Heads up: this is tuned to swing for the fences, not to play it safe. These
# settings are fine for paper money — they'd be genuinely reckless with real cash.
PAPER_TRADING_MODE = True

# When this is on, the bot reads the market each day and picks the strategy that
# tends to do best in that kind of market, instead of always using the same one:
#   RISK_ON  → HRP_MOMENTUM (in a steady uptrend, riding momentum pays off)
#   CHOPPY   → HRP          (no real trend to ride, so just balance risk evenly)
#   RISK_OFF → MAX_SHARPE   (tight limits shove money into TLT/SHV/GLD for safety)
AUTO_SELECT_STRATEGY = True
# Same idea, spelled out — which strategy we lean on in each market, and why.
# The numbers come from backtests over 2019–2026:
#   RISK_ON:  HRP_MOMENTUM — momentum works in sustained uptrends (~5.1% avg/quarter)
#   CHOPPY:   HRP          — nothing to ride, so plain risk-parity holds up best
#   RISK_OFF: MAX_SHARPE   — under crash limits the optimizer piles into TLT/GLD/SHV
STRATEGY_BY_REGIME = {
    "RISK_ON":  "HRP_MOMENTUM",
    "CHOPPY":   "HRP",
    "RISK_OFF": "MAX_SHARPE",
}

# ── Risk parameters ─────────────────────────────────────────────────────────
RISK_FREE_RATE = 0.045
LOOKBACK_DAYS = 252
REBALANCE_DRIFT_THRESHOLD = 0.05
MAX_SINGLE_WEIGHT = 0.70         # let one position get as big as 70% — we want to lean hard into winners
MIN_SINGLE_WEIGHT = 0.0          # no floor; if something doesn't earn weight, it gets zero
REBALANCE_DRIFT_THRESHOLD = 0.02 # only 2% of drift before we re-trade — keeps us close to target
DRAWDOWN_CIRCUIT_BREAKER = 0.30  # don't hit the brakes until we're down 30% from the high
MAX_PORTFOLIO_VOL = 0.90         # high ceiling on purpose — an all-3x-leveraged book naturally runs ~85% vol

# ── Risk overlay (vol-targeting + optional ML throttle) ─────────────────────
# Sits on top of the optimizer's weights: scales the whole book toward a target
# volatility and parks the unused slice in cash (SHV). Tames the 3x book's vol and
# drawdown without changing the underlying strategy. Backtested to cut a 3x book's
# vol ~53%->20% and max drawdown ~-71%->-24% while staying above SPY.
RISK_OVERLAY_ENABLED = True
OVERLAY_TARGET_VOL = 0.20        # annual vol to scale the book toward
OVERLAY_ML_ENABLED = False       # ML crash-throttle on top — OFF for now, enable after vol-target proves out live
CASH_ASSET = "SHV"               # where the de-risked slice parks (ultra-short Treasuries)

# ── Alpha sleeve (the individual-stock bets) ────────────────────────────────
# Sets aside a chunk of the portfolio for hand-picked momentum names from the
# watchlist. A stock has to clear both the sentiment and momentum bars to get in,
# and we only take the strongest few.
ALPHA_SLEEVE_ENABLED = True
ALPHA_SLEEVE_PCT = 0.40           # 40% of the book goes to these stock picks (the rest stays in ETFs)
ALPHA_SLEEVE_PICKS = 3            # only the top 3 names — concentrated, not spread thin
ALPHA_MIN_SENTIMENT = 0.5         # the news has to be at least decently bullish
ALPHA_MIN_5D_MOMENTUM = 0.05      # and it has to be up at least 5% over the last week
ALPHA_MAX_PER_STOCK = 0.18        # cap any single pick at 18% so one name can't run the whole show
# A few sanity filters so junk from the wider trending list doesn't sneak in:
ALPHA_MIN_PRICE = 3.0             # no penny stocks — has to trade above $3
ALPHA_MAX_TODAY_PCT = 0.30        # if it's already up 30%+ today, we've missed it — skip
ALPHA_REQUIRE_POSITIVE_20D = True # the month-long trend has to be up too, which weeds out one-day head-fakes

# ── Universe ─────────────────────────────────────────────────────────────────
ASSETS = [
    # ── The growth engine — what we lean on when the market's healthy (RISK_ON)
    "QQQ",   # Nasdaq 100
    "TQQQ",  # 3x Nasdaq — the rocket fuel
    "UPRO",  # 3x S&P 500 — the broad market, leveraged
    "SOXL",  # 3x semiconductors — our way to ride the AI/chip wave
    "TECL",  # 3x tech sector
    "VGT",   # US tech, no leverage
    "MTUM",  # momentum ETF — it just owns whatever's working lately
    "IWM",   # Russell 2000 small caps
    "AVUV",  # small-cap value
    "BITO",  # Bitcoin ETF — a little crypto exposure
    "VEA",   # developed markets outside the US
    # ── The safety net — only really comes off the bench in CHOPPY / RISK_OFF
    "GLD",   # gold
    "TLT",   # long-term treasuries
    "SHV",   # ultra-short treasuries, basically a stand-in for cash
]

WATCHLIST = [
    # Just a handful of anchors we always want scanned no matter what's in the news.
    # The other ~30 names each day come from the trending discovery and change daily.
    "NVDA",   # the AI bellwether — worth watching every single day
    "TSLA",   # a good read on high-beta momentum
    "AAPL",   # stands in for the mega-caps
    "PLTR",   # AI / defense momentum
    "COIN",   # a quick gauge of how crypto's feeling
]

# Trending-stock discovery (Claude with web search).
# Most of the bot's stock universe isn't hardcoded anymore — Claude goes and finds
# it fresh every morning. So instead of a fixed list, we get ~30 new names a day
# based on what's actually surging, in the news, or being talked about.
TRENDING_DISCOVERY_ENABLED = True
TRENDING_MAX_PICKS = 30          # how many names to pull each morning

# ── Log paths ────────────────────────────────────────────────────────────────
DAILY_LOG = BASE_DIR / "daily_log.csv"
SENTIMENT_LOG = BASE_DIR / "sentiment_log.csv"
REGIME_LOG = BASE_DIR / "regime_log.csv"
WATCHLIST_LOG = BASE_DIR / "watchlist_log.csv"
WATCHLIST_ALERTS = BASE_DIR / "watchlist_alerts.csv"
ALERTS_LOG = BASE_DIR / "alerts.log"
QUARTERLY_BACKTEST = BASE_DIR / "quarterly_backtest.csv"
BACKTEST_RESULTS = BASE_DIR / "backtest_results.png"
