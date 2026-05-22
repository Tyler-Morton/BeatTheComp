from pathlib import Path

BASE_DIR = Path(__file__).parent

# ── Strategy ────────────────────────────────────────────────────────────────
# Fallback used only when AUTO_SELECT_STRATEGY = False
ACTIVE_STRATEGY = "HRP_MOMENTUM"   # MAX_SHARPE | HRP | HRP_MOMENTUM

# When True, the bot picks the best strategy for the detected market regime.
# Mapping is based on which strategy historically dominates each condition:
#   RISK_ON  → HRP_MOMENTUM (momentum works in sustained uptrends)
#   CHOPPY   → HRP          (pure risk-parity, no trend assumptions)
#   RISK_OFF → MAX_SHARPE   (tight constraints push weight to TLT/SHV/GLD)
AUTO_SELECT_STRATEGY = True
# Regime → strategy mapping based on backtest results (2019–2026):
#   RISK_ON:  HRP_MOMENTUM — momentum works in sustained uptrends (5.1% avg/qtr)
#   CHOPPY:   HRP          — no trend to ride, pure risk-parity holds up best
#   RISK_OFF: MAX_SHARPE   — optimizer pushes hard into TLT/GLD/SHV under crash constraints
STRATEGY_BY_REGIME = {
    "RISK_ON":  "HRP_MOMENTUM",
    "CHOPPY":   "HRP",
    "RISK_OFF": "MAX_SHARPE",
}

# ── Risk parameters ─────────────────────────────────────────────────────────
RISK_FREE_RATE = 0.045
LOOKBACK_DAYS = 252
REBALANCE_DRIFT_THRESHOLD = 0.05
MAX_SINGLE_WEIGHT = 0.35
MIN_SINGLE_WEIGHT = 0.02
DRAWDOWN_CIRCUIT_BREAKER = 0.15
MAX_PORTFOLIO_VOL = 0.25

# ── Alpha sleeve (individual stocks) ────────────────────────────────────────
# Carves out a small % of the portfolio for high-momentum watchlist picks.
# Picks top N watchlist stocks meeting both sentiment + momentum thresholds.
ALPHA_SLEEVE_ENABLED = True
ALPHA_SLEEVE_PCT = 0.15           # 15% of portfolio (~$150 of $1000)
ALPHA_SLEEVE_PICKS = 3            # top 3 watchlist stocks
ALPHA_MIN_SENTIMENT = 0.5         # need bullish sentiment to qualify
ALPHA_MIN_5D_MOMENTUM = 0.05      # need +5% over 5 days
ALPHA_MAX_PER_STOCK = 0.08        # cap any single stock at 8% of total portfolio

# ── Universe ─────────────────────────────────────────────────────────────────
ASSETS = [
    "QQQ",   # Nasdaq 100 large cap growth
    "AVUV",  # Small cap value — factor premium
    "VGT",   # US tech sector
    "GLD",   # Gold — crash hedge
    "TLT",   # Long treasuries — risk-off
    "IWM",   # Russell 2000 small cap
    "BITO",  # Bitcoin ETF
    "VEA",   # International developed markets
    "XLC",   # Communications sector
    "SHV",   # Cash proxy for risk-off rotation
]

WATCHLIST = [
    "NVDA",  # AI/chips bellwether
    "RGTI",  # Quantum computing
    "IONQ",  # Quantum computing
    "QBTS",  # D-Wave quantum
    "PLTR",  # AI/defense data
    "TSLA",  # High volatility momentum
    "MSFT",  # Large cap quality
    "AMZN",  # E-commerce/cloud
    "META",  # Social/AI
    "SMCI",  # AI server infrastructure
]

# ── Log paths ────────────────────────────────────────────────────────────────
DAILY_LOG = BASE_DIR / "daily_log.csv"
SENTIMENT_LOG = BASE_DIR / "sentiment_log.csv"
REGIME_LOG = BASE_DIR / "regime_log.csv"
WATCHLIST_LOG = BASE_DIR / "watchlist_log.csv"
WATCHLIST_ALERTS = BASE_DIR / "watchlist_alerts.csv"
ALERTS_LOG = BASE_DIR / "alerts.log"
QUARTERLY_BACKTEST = BASE_DIR / "quarterly_backtest.csv"
BACKTEST_RESULTS = BASE_DIR / "backtest_results.png"
