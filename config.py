from pathlib import Path

BASE_DIR = Path(__file__).parent

# Strategy. ACTIVE_STRATEGY is only a backup for when auto-select below is off.
ACTIVE_STRATEGY = "HRP_MOMENTUM"   # MAX_SHARPE, HRP or HRP_MOMENTUM
# These settings are aggressive on purpose. Fine for paper money, reckless with real cash.
PAPER_TRADING_MODE = True

# When on, the bot reads the market each day and picks the strategy that tends to do
# best in that kind of market, from STRATEGY_BY_REGIME.
AUTO_SELECT_STRATEGY = True
# Picks come from backtests over 2019-2026.
#   RISK_ON: momentum works in sustained uptrends (about 5.1% a quarter on average).
#   CHOPPY: no trend to follow, so plain risk parity holds up best.
#   RISK_OFF: under crash limits the optimizer moves into TLT, GLD and SHV.
STRATEGY_BY_REGIME = {
    "RISK_ON":  "HRP_MOMENTUM",
    "CHOPPY":   "HRP",
    "RISK_OFF": "MAX_SHARPE",
}

# Risk parameters
RISK_FREE_RATE = 0.045
LOOKBACK_DAYS = 252
REBALANCE_DRIFT_THRESHOLD = 0.05
MAX_SINGLE_WEIGHT = 0.70         # one position can reach 70%, to lean hard into winners
MIN_SINGLE_WEIGHT = 0.0          # no floor: if something doesn't earn weight, it gets zero
REBALANCE_DRIFT_THRESHOLD = 0.02 # re-trade at 2% drift, which keeps us close to target
DRAWDOWN_CIRCUIT_BREAKER = 0.30  # the breaker trips at 30% below the high-water mark
IMPLAUSIBLE_VALUE_FRAC = 0.05    # an equity read below 5% of the high counts as a broker glitch
# After this many sessions in breaker mode without getting back above the trip level, the
# high-water mark resets to current equity and normal trading resumes. 63 is about one
# quarter of trading days. It's a safety default so the book can't freeze forever (the
# EXP-024 replica froze 136 sessions under the old rule). It wasn't optimized or backtested,
# so don't tune it on results.
BREAKER_RESET_SESSIONS = 63
MAX_PORTFOLIO_VOL = 0.90         # high on purpose: an all-3x book naturally runs about 85% vol

# Risk overlay: vol-targeting, with an optional ML throttle.
# Scales the optimizer's whole book toward a target vol and parks the unused slice in cash
# (SHV), without changing the underlying strategy. In web/static/verdict.json the champion with
# this overlay has 18.7% vol and a -28% max drawdown, but trails SPY: CAGR 13.9% vs 17.4%, Sharpe
# 0.553 vs 0.693.
RISK_OVERLAY_ENABLED = True
OVERLAY_TARGET_VOL = 0.20        # annual vol to scale the book toward
# How the overlay estimates risk. "trailing" is 40-day realized stdev. It lags the market,
# which is the champion's one demonstrated structural weakness (seen twice in June and July
# 2026). "har" is a HAR-RV one-step-ahead forecast (Corsi 2009).
#
# HAR isn't validated. EXP-014's A/B pass (Sharpe 0.56 to 0.59) wasn't replicated. EXP-019, a
# clean replication on forecast loss, failed, and found the HAR tested in 014 forecast from
# yesterday's features (a one-day-stale bug, since fixed in risk_overlay). "har" also needs at
# least 530 rows of returns and main.py supplies about 235, so it could never have run live.
# vol_target_scaler now raises instead of quietly falling back to trailing. Don't flip this
# without a new passing experiment and a longer price history in main.py.
OVERLAY_VOL_MODEL = "trailing"   # "trailing" or "har"
OVERLAY_ML_ENABLED = False       # ML crash throttle. Off until vol-targeting proves out live.
OVERLAY_ML_SHADOW = True         # compute the crash probability daily and log what the throttle
                                 # would do, without acting, to build a record before enabling it
CASH_ASSET = "SHV"               # where the de-risked slice parks (ultra-short Treasuries)
CASH_SWEEP_ENABLED = True        # after trading, park leftover uninvested cash in CASH_ASSET
CASH_SWEEP_BUFFER = 2.0          # dollars to leave loose for rounding and order minimums

# Alpha sleeve: a chunk of the portfolio for momentum stocks from the watchlist. A stock has
# to clear both the sentiment and momentum bars to get in, and only the strongest few make it.
ALPHA_SLEEVE_ENABLED = False  # Cut: LLM stock-picking that's unvalidated and can't be backtested.
                              # Picks correlated with the leveraged ETFs, which added concentration,
                              # and a cap bug caused the COIN over-concentration. Now ETF-only.
ALPHA_SLEEVE_PCT = 0.40           # 40% of the book goes to stock picks, the rest stays in ETFs
ALPHA_SLEEVE_PICKS = 3            # only the top 3 names, concentrated on purpose
ALPHA_MIN_SENTIMENT = 0.5         # the news has to be at least decently bullish
ALPHA_MIN_5D_MOMENTUM = 0.05      # up at least 5% over the last week
ALPHA_MAX_PER_STOCK = 0.18        # per-pick cap, applied before rescaling, so a pick can end up above 18%
# Sanity filters on watchlist names.
ALPHA_MIN_PRICE = 3.0             # no penny stocks
ALPHA_MAX_TODAY_PCT = 0.30        # already up 30%+ today means we've missed it, so skip
ALPHA_REQUIRE_POSITIVE_20D = True # the month-long trend has to be up too, which filters out one-day spikes

# Universe
ASSETS = [
    # Growth, what we lean on when the market's healthy (RISK_ON)
    "QQQ",   # Nasdaq 100
    "TQQQ",  # 3x Nasdaq
    "UPRO",  # 3x S&P 500
    "SOXL",  # 3x semiconductors
    "TECL",  # 3x tech sector
    "VGT",   # US tech, no leverage
    "MTUM",  # momentum ETF that owns whatever's working lately
    "IWM",   # Russell 2000 small caps
    "AVUV",  # small-cap value
    "BITO",  # Bitcoin ETF. Same caps as the other stock ETFs, so its weight can get large
    "VEA",   # developed markets outside the US
    # Safety, only really used in CHOPPY and RISK_OFF
    "GLD",   # gold
    "TLT",   # long-term treasuries
    "SHV",   # ultra-short treasuries, basically a stand-in for cash
]

WATCHLIST = [
    # A handful of anchors we always scan, whatever's in the news.
    # Trending discovery would add names on top of these, but it's off, so this is the whole list.
    "NVDA",   # the AI bellwether
    "TSLA",   # a good read on high-beta momentum
    "AAPL",   # stands in for the mega-caps
    "PLTR",   # AI and defense momentum
    "COIN",   # quick gauge of crypto sentiment
]

# Trending-stock discovery (Claude with web search). Disabled. When on, Claude finds about 30
# names each morning based on what's surging, in the news, or being talked about.
TRENDING_DISCOVERY_ENABLED = False   # Off on purpose. LLM discovery was unreliable
                                     # (returned prose instead of JSON) and points the wrong
                                     # way strategically: we don't want LLM-picked momentum names.
                                     # Universe is now the fixed ASSETS plus the WATCHLIST anchors.
TRENDING_MAX_PICKS = 30          # how many names to pull each morning when it's on

# Claude news-sentiment scoring (nudges optimizer position bounds by ticker).
SENTIMENT_ENABLED = False   # Off on purpose: it added little measurable edge and
                            # was the only remaining Anthropic API cost. With it off
                            # the optimizer just sees neutral scores, so no adjustment.

# Log paths
DAILY_LOG = BASE_DIR / "daily_log.csv"
SENTIMENT_LOG = BASE_DIR / "sentiment_log.csv"
REGIME_LOG = BASE_DIR / "regime_log.csv"
WATCHLIST_LOG = BASE_DIR / "watchlist_log.csv"
WATCHLIST_ALERTS = BASE_DIR / "watchlist_alerts.csv"
ALERTS_LOG = BASE_DIR / "alerts.log"
# Saved breaker state: broker-equity high-water mark plus breaker mode and session count.
# A .csv on purpose: rebalance.yml commits root-level *.csv after every run, so the
# state survives the fresh checkout each GitHub Actions run starts from.
BREAKER_STATE_FILE = BASE_DIR / "breaker_state.csv"
QUARTERLY_BACKTEST = BASE_DIR / "quarterly_backtest.csv"
BACKTEST_RESULTS = BASE_DIR / "backtest_results.png"
