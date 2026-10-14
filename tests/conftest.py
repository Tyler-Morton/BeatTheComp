"""Shared fixtures. Everything here is offline: no Alpaca, Tiingo, FRED or yfinance."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    """Any accidental HTTP call fails the test instead of hitting a real API."""
    import requests

    def _blocked(*a, **k):
        raise RuntimeError("network disabled in unit tests")
    monkeypatch.setattr(requests.Session, "request", _blocked)


@pytest.fixture
def asset_returns():
    """~300 days of synthetic daily returns for the champion universe."""
    from config import ASSETS
    rng = np.random.default_rng(42)
    n = 300
    idx = pd.bdate_range("2025-01-01", periods=n)
    vols = {t: (0.04 if t in ("TQQQ", "UPRO", "SOXL", "TECL") else 0.012) for t in ASSETS}
    vols["SHV"] = 0.0005
    common = rng.normal(0.0004, 0.008, n)
    data = {t: 0.5 * common * (vols[t] / 0.012) + rng.normal(0.0005, vols[t], n) for t in ASSETS}
    return pd.DataFrame(data, index=idx)
