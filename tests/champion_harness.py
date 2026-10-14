"""Run the champion's main.main() fully offline and print the targets it hands the broker.

Used by test_shadow_v3.py in a fresh interpreter, twice: once plain and once with
`--with-shadow`, which imports shadow_v3 and runs a shadow session on the same prices
before the champion runs. The two stdouts must be byte-identical.

Everything external is faked: prices are synthetic, the broker is an in-memory stub,
and every file the champion would write is redirected to a temp dir.
"""
import json
import sys
import tempfile
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import dotenv  # noqa: E402

dotenv.load_dotenv = lambda *a, **k: False      # never pick up a real .env from a parent dir

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402


def synthetic_prices(end: str = "2026-10-12", n: int = 260, seed: int = 7) -> pd.DataFrame:
    from config import ASSETS
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range(end=end, periods=n)
    cols = list(dict.fromkeys(ASSETS + ["SPY", "TLT"]))
    common = rng.normal(0.0008, 0.006, n)
    data = {}
    for t in cols:
        lev = 3.0 if t in ("TQQQ", "UPRO", "SOXL", "TECL") else 1.0
        vol = 0.0004 if t == "SHV" else 0.003
        beta = 0.0 if t in ("SHV", "TLT", "GLD") else lev
        r = beta * common + rng.normal(0.0002, vol * (1.5 if lev > 1 else 1.0), n)
        data[t] = 100 * np.cumprod(1 + r)
    return pd.DataFrame(data, index=idx)


def main(with_shadow: bool) -> None:
    tmp = Path(tempfile.mkdtemp(prefix="champ_harness_"))
    # The champion's real committed price table if present (offline, and it puts 3x ETFs
    # in the book), otherwise a synthetic one.
    cache = ROOT / "prices_cache.parquet"
    prices = pd.read_parquet(cache) if cache.exists() else synthetic_prices()
    run_day = (prices.index[-1] + pd.offsets.BDay(1)).date()

    captured = {}
    fake_broker = types.ModuleType("broker")
    fake_broker.is_market_open = lambda: True
    fake_broker.get_portfolio_value = lambda: 1000.0
    fake_broker.get_current_positions = lambda: {"SHV": 1.0}
    fake_broker.sweep_idle_cash = lambda: None
    fake_broker.get_account_history = lambda days=365: pd.DataFrame(columns=["timestamp", "equity"])

    def _rebalance(target_weights, **kwargs):
        captured["targets"] = dict(target_weights)
        return []
    fake_broker.rebalance = _rebalance
    sys.modules["broker"] = fake_broker

    import data
    data.fetch_prices = lambda tickers, lookback_days=252: prices[[t for t in tickers if t in prices.columns]]
    data.save_price_cache = lambda p: None
    import regime
    regime._log_regime = lambda *a, **k: None
    import risk
    risk._alert = lambda msg: None
    risk.DAILY_LOG = tmp / "daily_log.csv"
    risk.BREAKER_STATE_FILE = tmp / "breaker_state.csv"   # never touch the real breaker state
    import watchlist
    watchlist.scan_watchlist = lambda tickers: []
    import time
    time.sleep = lambda s: None

    if with_shadow:
        import shadow_v3
        shadow_v3.step(None, prices, run_day, 1000.0)

    import main as champion
    champion.DAILY_LOG = tmp / "daily_log.csv"
    champion.fetch_prices = data.fetch_prices
    champion.main()
    print(json.dumps(captured.get("targets"), sort_keys=True))


if __name__ == "__main__":
    main("--with-shadow" in sys.argv)
