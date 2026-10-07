"""Unit tests for the deterministic RiskManager and guardrails."""

import pytest

from autonomous_trading_analyst.agent.signal import SignalDecision, TradingSignal
from autonomous_trading_analyst.config import Settings
from autonomous_trading_analyst.domain import (
    Action,
    Order,
    OrderStatus,
    PortfolioState,
    Position,
    Signal,
)
from autonomous_trading_analyst.risk.manager import RiskManager


@pytest.fixture
def base_settings() -> Settings:
    """Fixture providing standard risk settings."""
    return Settings(
        watchlist=["AAPL", "MSFT", "NVDA", "SPY"],
        risk_max_position_pct=0.10,
        risk_max_gross_exposure_pct=0.80,
        risk_stop_loss_pct=0.08,
        risk_max_trades_per_day=5,
    )


@pytest.fixture
def empty_portfolio() -> PortfolioState:
    """Fixture providing an empty portfolio with 100k cash."""
    return PortfolioState.create(cash=100000.0, positions={})


@pytest.mark.issue_12
def test_watchlist_restriction(base_settings: Settings, empty_portfolio: PortfolioState) -> None:
    """Orders for symbols not in the watchlist must be rejected."""
    risk_manager = RiskManager(settings=base_settings)

    # TSLA is not in watchlist ["AAPL", "MSFT", "NVDA", "SPY"]
    order = Order(order_id="o1", ticker="TSLA", action=Action.BUY, shares=10.0)
    evaluated = risk_manager.evaluate_order(order, empty_portfolio, current_price=200.0)

    assert evaluated.status == OrderStatus.REJECTED
    assert "not in configured watchlist" in (evaluated.reason or "")

    # AAPL is allowed
    order_aapl = Order(order_id="o2", ticker="AAPL", action=Action.BUY, shares=10.0)
    evaluated_aapl = risk_manager.evaluate_order(order_aapl, empty_portfolio, current_price=150.0)
    assert evaluated_aapl.status == OrderStatus.APPROVED


@pytest.mark.issue_12
def test_daily_trades_limit(base_settings: Settings, empty_portfolio: PortfolioState) -> None:
    """Orders submitted after hitting the daily trade limit must be rejected."""
    risk_manager = RiskManager(settings=base_settings)
    order = Order(order_id="o1", ticker="AAPL", action=Action.BUY, shares=5.0)

    # Within limit
    eval_ok = risk_manager.evaluate_order(
        order, empty_portfolio, current_price=100.0, trades_today=4
    )
    assert eval_ok.status == OrderStatus.APPROVED

    # Reached limit
    eval_rejected = risk_manager.evaluate_order(
        order, empty_portfolio, current_price=100.0, trades_today=5
    )
    assert eval_rejected.status == OrderStatus.REJECTED
    assert "Daily trade limit reached" in (eval_rejected.reason or "")


@pytest.mark.issue_12
def test_no_shorting_rule(base_settings: Settings) -> None:
    """Short selling is forbidden: reject if zero shares, resize if requested > held."""
    risk_manager = RiskManager(settings=base_settings)

    # Case 1: No open position in AAPL
    portfolio_no_pos = PortfolioState.create(cash=50000.0, positions={})
    sell_order = Order(order_id="o1", ticker="AAPL", action=Action.SELL, shares=10.0)
    eval_no_pos = risk_manager.evaluate_order(sell_order, portfolio_no_pos, current_price=150.0)

    assert eval_no_pos.status == OrderStatus.REJECTED
    assert "Shorting is not permitted" in (eval_no_pos.reason or "")

    # Case 2: Open position with 20 shares, requested 35 shares -> resized to 20
    pos_aapl = Position(
        ticker="AAPL",
        shares=20.0,
        average_entry_price=140.0,
        current_price=150.0,
    )
    portfolio_with_pos = PortfolioState.create(cash=50000.0, positions={"AAPL": pos_aapl})
    sell_oversized = Order(order_id="o2", ticker="AAPL", action=Action.SELL, shares=35.0)
    eval_resized = risk_manager.evaluate_order(
        sell_oversized, portfolio_with_pos, current_price=150.0
    )

    assert eval_resized.status == OrderStatus.RESIZED
    assert eval_resized.shares == 20.0
    assert "Order resized from 35.0 to 20.0 shares to prevent shorting" in (
        eval_resized.reason or ""
    )

    # Case 3: Open position with 20 shares, requested 10 shares -> approved
    sell_valid = Order(order_id="o3", ticker="AAPL", action=Action.SELL, shares=10.0)
    eval_valid = risk_manager.evaluate_order(sell_valid, portfolio_with_pos, current_price=150.0)
    assert eval_valid.status == OrderStatus.APPROVED
    assert eval_valid.shares == 10.0


@pytest.mark.issue_12
def test_max_position_size_limit(base_settings: Settings) -> None:
    """Enforce max position size (10% of portfolio equity)."""
    risk_manager = RiskManager(settings=base_settings)
    # Equity = 100,000 USD; Max position = 10,000 USD
    # Current price = 100.0 USD -> max 100 shares
    portfolio = PortfolioState.create(cash=100000.0, positions={})

    # Submitting 150 shares -> resized to 100 shares
    order_oversized = Order(order_id="o1", ticker="AAPL", action=Action.BUY, shares=150.0)
    eval_resized = risk_manager.evaluate_order(order_oversized, portfolio, current_price=100.0)

    assert eval_resized.status == OrderStatus.RESIZED
    assert eval_resized.shares == pytest.approx(100.0)
    assert "max position size" in (eval_resized.reason or "")

    # Already holding 100 shares -> rejected
    pos_full = Position(
        ticker="AAPL",
        shares=100.0,
        average_entry_price=100.0,
        current_price=100.0,
    )
    portfolio_full = PortfolioState.create(cash=90000.0, positions={"AAPL": pos_full})
    order_more = Order(order_id="o2", ticker="AAPL", action=Action.BUY, shares=10.0)
    eval_full = risk_manager.evaluate_order(order_more, portfolio_full, current_price=100.0)

    assert eval_full.status == OrderStatus.REJECTED
    assert "Max position size limit" in (eval_full.reason or "")


@pytest.mark.issue_12
def test_max_gross_exposure_and_cash_constraints(base_settings: Settings) -> None:
    """Enforce max gross exposure (80% of equity) and cash constraint."""
    risk_manager = RiskManager(settings=base_settings)
    # Total equity = $100,000; Max gross exposure = $80,000
    # MSFT position = $75,000. Cash = $25,000.
    pos_msft = Position(
        ticker="MSFT",
        shares=187.5,
        average_entry_price=400.0,
        current_price=400.0,
    )
    portfolio = PortfolioState.create(cash=25000.0, positions={"MSFT": pos_msft})
    assert portfolio.total_equity == 100000.0

    # Remaining gross exposure = $80,000 - $75,000 = $5,000
    # At price $100, max allowed is 50 shares
    order = Order(order_id="o1", ticker="AAPL", action=Action.BUY, shares=80.0)
    eval_res = risk_manager.evaluate_order(order, portfolio, current_price=100.0)

    assert eval_res.status == OrderStatus.RESIZED
    assert eval_res.shares == pytest.approx(50.0)
    assert "max gross exposure" in (eval_res.reason or "")

    # If already at 80% exposure -> rejected
    pos_msft_80k = Position(
        ticker="MSFT",
        shares=200.0,
        average_entry_price=400.0,
        current_price=400.0,
    )
    portfolio_80k = PortfolioState.create(cash=20000.0, positions={"MSFT": pos_msft_80k})
    eval_max_exposure = risk_manager.evaluate_order(order, portfolio_80k, current_price=100.0)

    assert eval_max_exposure.status == OrderStatus.REJECTED
    assert "Max gross exposure limit" in (eval_max_exposure.reason or "")


@pytest.mark.issue_12
def test_stop_loss_sweep(base_settings: Settings) -> None:
    """Identify positions breaching stop loss (-8%) and generate exit orders."""
    risk_manager = RiskManager(settings=base_settings)

    # AAPL: entry $100, current $90 -> loss of 10% (breaches 8% threshold)
    pos_aapl = Position(
        ticker="AAPL",
        shares=50.0,
        average_entry_price=100.0,
        current_price=100.0,
    )
    # MSFT: entry $400, current $390 -> loss of 2.5% (safe)
    pos_msft = Position(
        ticker="MSFT",
        shares=20.0,
        average_entry_price=400.0,
        current_price=400.0,
    )
    portfolio = PortfolioState.create(
        cash=10000.0,
        positions={"AAPL": pos_aapl, "MSFT": pos_msft},
    )

    current_prices = {"AAPL": 90.0, "MSFT": 390.0}
    exit_orders = risk_manager.check_stop_losses(portfolio, current_prices)

    assert len(exit_orders) == 1
    assert exit_orders[0].ticker == "AAPL"
    assert exit_orders[0].action == Action.SELL
    assert exit_orders[0].shares == 50.0
    assert exit_orders[0].status == OrderStatus.APPROVED
    assert "Stop-loss triggered" in (exit_orders[0].reason or "")


@pytest.mark.issue_12
def test_evaluate_signal(base_settings: Settings, empty_portfolio: PortfolioState) -> None:
    """Evaluate signals from agent and domain models."""
    risk_manager = RiskManager(settings=base_settings)

    # HOLD signal produces no order
    trading_signal_hold = TradingSignal(
        ticker="AAPL",
        decision=SignalDecision.HOLD,
        confidence=0.5,
        rationale="Wait and see",
    )
    assert risk_manager.evaluate_signal(trading_signal_hold, empty_portfolio, 150.0) is None

    # BUY trading signal produces evaluated Order
    trading_signal_buy = TradingSignal(
        ticker="AAPL",
        decision=SignalDecision.BUY,
        confidence=0.9,
        rationale="Strong momentum",
    )
    order_buy = risk_manager.evaluate_signal(trading_signal_buy, empty_portfolio, 100.0)
    assert order_buy is not None
    assert order_buy.ticker == "AAPL"
    assert order_buy.action == Action.BUY
    assert order_buy.status == OrderStatus.APPROVED

    # Domain Signal with explicit size
    domain_signal = Signal(
        ticker="AAPL",
        action=Action.BUY,
        size=0.05,
        confidence=0.8,
        rationale="RSI oversold",
        citations=["obs_1"],
    )
    order_domain = risk_manager.evaluate_signal(domain_signal, empty_portfolio, 100.0)
    assert order_domain is not None
    assert order_domain.shares == pytest.approx(50.0)  # 5% of 100k = 5000 / 100 = 50
    assert order_domain.status == OrderStatus.APPROVED
