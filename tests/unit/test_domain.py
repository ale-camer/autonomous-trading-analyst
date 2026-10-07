"""Unit tests for domain models."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from autonomous_trading_analyst.domain import (
    Action,
    DecisionRecord,
    Fill,
    Order,
    OrderStatus,
    PortfolioState,
    Position,
    Signal,
    TraceStep,
)


@pytest.mark.issue_2
def test_action_and_order_status_enums() -> None:
    """Enums have expected string values."""
    assert Action.BUY == "BUY"
    assert Action.SELL == "SELL"
    assert Action.HOLD == "HOLD"

    assert OrderStatus.PENDING == "PENDING"
    assert OrderStatus.APPROVED == "APPROVED"
    assert OrderStatus.RESIZED == "RESIZED"
    assert OrderStatus.REJECTED == "REJECTED"
    assert OrderStatus.FILLED == "FILLED"
    assert OrderStatus.CANCELLED == "CANCELLED"


@pytest.mark.issue_2
def test_signal_valid_and_normalized() -> None:
    """Valid signals are created and tickers are normalized to uppercase."""
    signal = Signal(
        ticker="aapl",
        action=Action.BUY,
        size=0.1,
        confidence=0.85,
        rationale="Strong RSI breakout supported by financial news",
        citations=["obs_1", "obs_2"],
    )
    assert signal.ticker == "AAPL"
    assert signal.size == 0.1
    assert signal.confidence == 0.85
    assert len(signal.citations) == 2


@pytest.mark.issue_2
def test_signal_requires_citations_for_active_trades() -> None:
    """Trade signals with non-zero size must cite observation IDs."""
    with pytest.raises(ValidationError, match="requires at least one observation citation"):
        Signal(
            ticker="AAPL",
            action=Action.BUY,
            size=0.1,
            confidence=0.9,
            rationale="Uncited recommendation",
            citations=[],
        )

    # HOLD signals do not require citations
    hold_signal = Signal(
        ticker="AAPL",
        action=Action.HOLD,
        size=0.0,
        confidence=0.5,
        rationale="Wait and see",
    )
    assert hold_signal.citations == []


@pytest.mark.issue_2
def test_signal_field_boundaries() -> None:
    """Signal validates size, confidence boundaries and non-empty ticker."""
    with pytest.raises(ValidationError):
        Signal(
            ticker="AAPL",
            action=Action.HOLD,
            confidence=1.5,
            rationale="Invalid confidence",
        )

    with pytest.raises(ValidationError):
        Signal(
            ticker="AAPL",
            action=Action.HOLD,
            size=-0.1,
            rationale="Invalid size",
        )

    with pytest.raises(ValidationError):
        Signal(
            ticker="   ",
            action=Action.HOLD,
            rationale="Empty ticker",
        )


@pytest.mark.issue_2
def test_order_and_fill_creation() -> None:
    """Order and Fill models enforce positive share counts and prices."""
    order = Order(
        order_id="ord-001",
        ticker="msft",
        action=Action.BUY,
        shares=10.0,
        limit_price=400.0,
    )
    assert order.ticker == "MSFT"
    assert order.status == OrderStatus.PENDING

    with pytest.raises(ValidationError):
        Order(
            order_id="ord-002",
            ticker="MSFT",
            action=Action.BUY,
            shares=0.0,
        )

    fill = Fill(
        fill_id="fill-001",
        order_id="ord-001",
        ticker="MSFT",
        action=Action.BUY,
        shares=10.0,
        price=399.5,
        commission=1.0,
        slippage=0.5,
    )
    assert fill.shares == 10.0
    assert fill.price == 399.5


@pytest.mark.issue_2
def test_position_and_portfolio_state_computations() -> None:
    """Position calculates market value; PortfolioState computes equity and exposure."""
    pos_aapl = Position(
        ticker="AAPL",
        shares=50.0,
        average_entry_price=150.0,
        current_price=200.0,
        unrealized_pnl=2500.0,
    )
    assert pos_aapl.market_value == 10000.0

    pos_msft = Position(
        ticker="MSFT",
        shares=25.0,
        average_entry_price=400.0,
        current_price=400.0,
    )
    assert pos_msft.market_value == 10000.0

    state = PortfolioState.create(
        cash=80000.0,
        positions={"AAPL": pos_aapl, "MSFT": pos_msft},
    )
    assert state.cash == 80000.0
    assert state.total_equity == 100000.0
    assert state.gross_exposure == pytest.approx(0.20)


@pytest.mark.issue_2
def test_trace_step_and_decision_record_serialization() -> None:
    """TraceStep and DecisionRecord can be created and serialized cleanly."""
    step = TraceStep(
        step_number=1,
        thought="I should check AAPL 14-day RSI first",
        action_name="get_technical_indicators",
        action_args={"ticker": "AAPL", "indicators": ["rsi"]},
        observation_id="obs_1",
        observation="RSI=28.5 (oversold)",
        tokens_used=150,
        cost_usd=0.0003,
    )
    assert step.step_number == 1
    assert step.observation_id == "obs_1"

    signal = Signal(
        ticker="AAPL",
        action=Action.BUY,
        size=0.05,
        confidence=0.8,
        rationale="RSI is oversold",
        citations=["obs_1"],
    )

    decision = DecisionRecord(
        decision_id="dec-123",
        ticker="AAPL",
        signal=signal,
        trace=[step],
        total_cost_usd=0.0003,
        total_tokens=150,
        created_at=datetime.now(UTC),
        realized_outcome=0.042,
    )
    assert decision.decision_id == "dec-123"
    assert decision.realized_outcome == 0.042

    json_str = decision.model_dump_json()
    assert "dec-123" in json_str
    assert "obs_1" in json_str
