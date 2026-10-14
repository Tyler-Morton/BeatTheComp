"""broker.rebalance against a fake Alpaca client: paper guard, sizing, failure paths."""
from types import SimpleNamespace as NS

import pytest

import broker


class FakeTC:
    def __init__(self, equity=1000.0, cash=0.0, bp=None, positions=None, fail_positions=False):
        self.equity, self.cash = equity, cash
        self.bp = bp if bp is not None else cash
        self.positions = positions or {}          # sym -> (market_value, qty)
        self.fail_positions = fail_positions
        self.orders, self.closed = [], []

    def get_account(self):
        return NS(equity=self.equity, cash=self.cash, buying_power=self.bp)

    def get_all_positions(self):
        if self.fail_positions:
            raise ConnectionError("boom")
        return [NS(symbol=s, market_value=mv, qty=q) for s, (mv, q) in self.positions.items()]

    def get_asset(self, sym):
        return NS(fractionable=True)

    def submit_order(self, req):
        self.orders.append(req)
        return NS(id=f"o{len(self.orders)}")

    def close_position(self, sym):
        self.closed.append(sym)
        return NS(id=f"c{sym}")

    def get_order_by_id(self, oid):
        return NS(status="OrderStatus.FILLED")


@pytest.fixture
def fake(monkeypatch):
    def make(**kw):
        tc = FakeTC(**kw)
        monkeypatch.setattr(broker, "_client", tc)
        broker._fractionable_cache.clear()
        return tc
    return make


def test_paper_guard_default_ok(monkeypatch):
    monkeypatch.delenv("ALPACA_BASE_URL", raising=False)
    assert broker._require_paper() is True


def test_paper_guard_refuses_live_url(monkeypatch):
    monkeypatch.setenv("ALPACA_BASE_URL", "https://api.alpaca.markets")
    with pytest.raises(RuntimeError, match="PAPER guard"):
        broker._require_paper()


def test_paper_guard_refuses_config_flip(monkeypatch):
    import config
    monkeypatch.delenv("ALPACA_BASE_URL", raising=False)
    monkeypatch.setattr(config, "PAPER_TRADING_MODE", False)
    with pytest.raises(RuntimeError):
        broker._require_paper()


def test_aborts_when_positions_unreadable(fake):
    tc = fake(equity=1000, cash=1000, bp=2000, fail_positions=True)
    assert broker.rebalance({"QQQ": 0.5, "SHV": 0.5}) == []
    assert tc.orders == [] and tc.closed == []


def test_buys_capped_by_cash_not_margin(fake):
    # $1000 equity, all cash, but 2x margin buying power: buys must not exceed cash.
    tc = fake(equity=1000, cash=1000, bp=2000)
    broker.rebalance({"QQQ": 1.0})
    assert len(tc.orders) == 1
    assert float(tc.orders[0].notional) <= 1000 * 0.98 + 0.01


def test_full_exit_and_dust_use_close_position(fake):
    tc = fake(equity=1000, cash=0, positions={"TQQQ": (500.0, 5.0), "DUST": (0.4, 0.01),
                                              "QQQ": (499.6, 1.0)})
    broker.rebalance({"QQQ": 0.5, "SHV": 0.5})
    assert set(tc.closed) == {"TQQQ", "DUST"}


def test_partial_trim_never_sells_full_position(fake):
    tc = fake(equity=1000, cash=0, positions={"QQQ": (1000.0, 2.0)})
    broker.rebalance({"QQQ": 0.4, "SHV": 0.6})
    sells = [o for o in tc.orders if "SELL" in str(o.side).upper()]
    assert len(sells) == 1 and float(sells[0].notional) == pytest.approx(600.0)
