"""Unit tests for the simulated PaperBroker and portfolio accounting."""

import pytest

from autonomous_trading_analyst.broker.paper import PaperBroker
from autonomous_trading_analyst.config import Settings
from autonomous_trading_analyst.domain import (
    Action,
    Order,
    OrderStatus,
)


@pytest.fixture
def broker_settings() -> Settings:
    """Fixture providing settings with explicit slippage and commission."""
    return Settings(
        paper_initial_cash=100000.0,
        paper_commission_bps=1.0,  # 0.01%
        paper_slippage_bps=5.0,  # 0.05%
        watchlist=["AAPL", "MSFT"],
    )


@pytest.mark.issue_13
def test_paper_broker_initial_state(broker_settings: Settings) -> None:
    """Verify broker begins with configured initial cash and empty positions."""
    broker = PaperBroker(settings=broker_settings)
    assert broker.cash == 100000.0
    assert len(broker.positions) == 0
    assert len(broker.fills) == 0
    assert broker.total_realized_pnl == 0.0
    assert broker.total_unrealized_pnl == 0.0
    assert broker.total_equity == 100000.0

    state = broker.get_portfolio_state()
    assert state.cash == 100000.0
    assert state.gross_exposure == 0.0


@pytest.mark.issue_13
def test_execute_buy_order_accounting(broker_settings: Settings) -> None:
    """BUY execution applies adverse slippage (+5 bps) and fee, updating cash/position."""
    broker = PaperBroker(settings=broker_settings)

    # Market price = $100.0. Slippage = 5 bps (+0.05%) -> Exec price = $100.05
    # Gross value = 100 * 100.05 = $10,005.00
    # Commission = 1 bps (0.01%) -> $1.0005
    # Total cash deducted = $10,005.00 + $1.0005 = $10,006.0005
    order = Order(
        order_id="ord_buy_1",
        ticker="AAPL",
        action=Action.BUY,
        shares=100.0,
        status=OrderStatus.APPROVED,
    )
    fill = broker.execute_order(order, market_price=100.0)

    assert fill is not None
    assert fill.order_id == "ord_buy_1"
    assert fill.ticker == "AAPL"
    assert fill.action == Action.BUY
    assert fill.shares == 100.0
    assert fill.price == pytest.approx(100.05)
    assert fill.slippage == pytest.approx(5.0)  # 0.05 * 100
    assert fill.commission == pytest.approx(1.0005)

    assert broker.cash == pytest.approx(100000.0 - 10006.0005)
    assert "AAPL" in broker.positions
    pos = broker.positions["AAPL"]
    assert pos.shares == 100.0
    assert pos.average_entry_price == pytest.approx(100.05)
    assert pos.current_price == 100.0
    assert len(broker.fills) == 1
    assert len(broker.history) == 1


@pytest.mark.issue_13
def test_weighted_average_entry_on_repeated_buys(broker_settings: Settings) -> None:
    """Repeated BUY orders update the weighted average entry price correctly."""
    broker = PaperBroker(settings=broker_settings)

    # Buy 1: 100 shares at $100 market price (exec price = $100.05)
    order1 = Order(
        order_id="o1",
        ticker="AAPL",
        action=Action.BUY,
        shares=100.0,
        status=OrderStatus.APPROVED,
    )
    broker.execute_order(order1, market_price=100.0)

    # Buy 2: 100 shares at $200 market price (exec price = $200.10)
    order2 = Order(
        order_id="o2",
        ticker="AAPL",
        action=Action.BUY,
        shares=100.0,
        status=OrderStatus.RESIZED,
    )
    broker.execute_order(order2, market_price=200.0)

    pos = broker.positions["AAPL"]
    assert pos.shares == 200.0
    # Expected avg = (100 * 100.05 + 100 * 200.10) / 200 = 150.075
    assert pos.average_entry_price == pytest.approx(150.075)


@pytest.mark.issue_13
def test_execute_sell_order_and_position_closure(broker_settings: Settings) -> None:
    """SELL orders credit net proceeds, compute realized PnL, and close position on 0 shares."""
    broker = PaperBroker(settings=broker_settings)

    # Setup: Buy 100 shares at $100 (exec price = $100.05, cash paid = $10006.0005)
    buy_order = Order(
        order_id="o_buy",
        ticker="AAPL",
        action=Action.BUY,
        shares=100.0,
        status=OrderStatus.APPROVED,
    )
    broker.execute_order(buy_order, market_price=100.0)
    cash_after_buy = broker.cash

    # Partial Sell: 40 shares at $150 market price
    # Slippage = -5 bps -> exec price = 150 * (1 - 0.0005) = 149.925
    # Gross value = 40 * 149.925 = $5,997.00
    # Commission = 1 bps -> $0.5997
    # Net proceeds added to cash = $5,997.00 - $0.5997 = $5,996.4003
    # Cost basis = 40 * 100.05 = $4,002.00
    # Realized PnL = $5,997.00 - $4,002.00 - $0.5997 = $1,994.4003
    sell_partial = Order(
        order_id="o_sell_1",
        ticker="AAPL",
        action=Action.SELL,
        shares=40.0,
        status=OrderStatus.APPROVED,
    )
    fill_sell_1 = broker.execute_order(sell_partial, market_price=150.0)

    assert fill_sell_1 is not None
    assert fill_sell_1.price == pytest.approx(149.925)
    assert broker.cash == pytest.approx(cash_after_buy + 5996.4003)
    assert broker.total_realized_pnl == pytest.approx(1994.4003)

    pos = broker.positions["AAPL"]
    assert pos.shares == 60.0
    assert pos.average_entry_price == pytest.approx(100.05)  # unchanged on sell

    # Full Sell of remaining 60 shares at $160 market price
    # Exec price = 160 * 0.9995 = 159.92
    # Gross value = 60 * 159.92 = $9,595.20
    # Commission = 1 bps -> $0.95952
    # Net proceeds = $9,594.24048
    # Cost basis = 60 * 100.05 = $6,003.00
    # Realized PnL = 9595.20 - 6003.00 - 0.95952 = $3,591.24048
    sell_close = Order(
        order_id="o_sell_2",
        ticker="AAPL",
        action=Action.SELL,
        shares=60.0,
        status=OrderStatus.APPROVED,
    )
    fill_sell_2 = broker.execute_order(sell_close, market_price=160.0)

    assert fill_sell_2 is not None
    # Position closed completely and removed from active positions dict
    assert "AAPL" not in broker.positions
    expected_total_pnl = 1994.4003 + 3591.24048
    assert broker.total_realized_pnl == pytest.approx(expected_total_pnl)


@pytest.mark.issue_13
def test_order_rejection_and_eligibility(broker_settings: Settings) -> None:
    """Disallowed orders (PENDING, REJECTED, HOLD, non-positive price/shares) return None."""
    broker = PaperBroker(settings=broker_settings)

    pending_order = Order(
        order_id="p1", ticker="AAPL", action=Action.BUY, shares=10.0, status=OrderStatus.PENDING
    )
    assert broker.execute_order(pending_order, 100.0) is None

    rejected_order = Order(
        order_id="r1", ticker="AAPL", action=Action.BUY, shares=10.0, status=OrderStatus.REJECTED
    )
    assert broker.execute_order(rejected_order, 100.0) is None

    hold_order = Order(
        order_id="h1", ticker="AAPL", action=Action.HOLD, shares=10.0, status=OrderStatus.APPROVED
    )
    assert broker.execute_order(hold_order, 100.0) is None

    approved_order = Order(
        order_id="a1", ticker="AAPL", action=Action.BUY, shares=10.0, status=OrderStatus.APPROVED
    )
    # Zero or negative market price
    assert broker.execute_order(approved_order, 0.0) is None
    assert broker.execute_order(approved_order, -50.0) is None

    # Sell without position
    sell_empty = Order(
        order_id="s1", ticker="AAPL", action=Action.SELL, shares=10.0, status=OrderStatus.APPROVED
    )
    assert broker.execute_order(sell_empty, 100.0) is None

    # Buy exceeding available cash
    huge_order = Order(
        order_id="huge",
        ticker="AAPL",
        action=Action.BUY,
        shares=2000.0,  # $200k > $100k cash
        status=OrderStatus.APPROVED,
    )
    assert broker.execute_order(huge_order, 100.0) is None


@pytest.mark.issue_13
def test_mark_to_market_and_history(broker_settings: Settings) -> None:
    """mark_to_market updates unrealized PnL, equity, and appends state snapshot."""
    broker = PaperBroker(settings=broker_settings)

    # Buy 50 shares of AAPL at $100 (exec price = $100.05)
    order = Order(
        order_id="o1", ticker="AAPL", action=Action.BUY, shares=50.0, status=OrderStatus.APPROVED
    )
    broker.execute_order(order, market_price=100.0)

    # Mark to market with AAPL price at $120.0
    snapshot = broker.mark_to_market(current_prices={"AAPL": 120.0})

    pos = broker.positions["AAPL"]
    assert pos.current_price == 120.0
    expected_unrealized = 50.0 * (120.0 - 100.05)
    assert pos.unrealized_pnl == pytest.approx(expected_unrealized)
    assert broker.total_unrealized_pnl == pytest.approx(expected_unrealized)

    assert snapshot.total_equity == pytest.approx(broker.cash + 50.0 * 120.0)
    assert len(broker.history) == 2  # 1 from execute_order, 1 from mark_to_market


@pytest.mark.issue_13
def test_broker_reset(broker_settings: Settings) -> None:
    """Broker reset restores clean initial state."""
    broker = PaperBroker(settings=broker_settings)
    order = Order(
        order_id="o1", ticker="AAPL", action=Action.BUY, shares=10.0, status=OrderStatus.APPROVED
    )
    broker.execute_order(order, market_price=100.0)
    assert len(broker.positions) == 1

    broker.reset(initial_cash=50000.0)
    assert broker.cash == 50000.0
    assert len(broker.positions) == 0
    assert len(broker.fills) == 0
    assert len(broker.history) == 0
    assert broker.total_realized_pnl == 0.0
