"""Unit tests for the relational persistence layer and repositories."""

from datetime import UTC, datetime

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

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
from autonomous_trading_analyst.persistence import (
    Base,
    DecisionRepository,
    FillRepository,
    OrderRepository,
    PortfolioRepository,
    create_db_engine,
    get_session_factory,
    init_db,
)


@pytest.fixture
def sqlite_engine() -> Engine:
    """Fixture providing an in-memory SQLite engine with initialized tables."""
    engine = create_db_engine("sqlite:///:memory:")
    init_db(engine)
    return engine


@pytest.fixture
def session_factory(sqlite_engine: Engine) -> sessionmaker[Session]:
    """Fixture providing a session factory bound to the in-memory SQLite engine."""
    return get_session_factory(sqlite_engine)


@pytest.mark.issue_14
def test_schema_initialization(sqlite_engine: Engine) -> None:
    """Verify tables are created in the database."""
    tables = Base.metadata.tables.keys()
    assert "decisions" in tables
    assert "trace_steps" in tables
    assert "orders" in tables
    assert "fills" in tables
    assert "portfolio_snapshots" in tables


@pytest.mark.issue_14
def test_decision_repository_save_and_get(session_factory: sessionmaker[Session]) -> None:
    """Persist a DecisionRecord with trace steps and retrieve with full fidelity."""
    repo = DecisionRepository(session_factory)

    signal = Signal(
        ticker="AAPL",
        action=Action.BUY,
        size=0.10,
        confidence=0.92,
        rationale="Strong earnings report and momentum",
        citations=["obs_price_1", "obs_rsi_2"],
        timestamp=datetime.now(UTC),
    )

    step1 = TraceStep(
        step_number=1,
        thought="Checking latest market price",
        action_name="get_latest_price",
        action_args={"ticker": "AAPL"},
        observation_id="obs_price_1",
        observation="AAPL price: 185.50",
        tokens_used=120,
        cost_usd=0.00015,
        timestamp=datetime.now(UTC),
    )

    step2 = TraceStep(
        step_number=2,
        thought="Checking technical indicators",
        action_name="get_technical_indicators",
        action_args={"ticker": "AAPL"},
        observation_id="obs_rsi_2",
        observation="RSI=32.0",
        tokens_used=150,
        cost_usd=0.00020,
        timestamp=datetime.now(UTC),
    )

    decision = DecisionRecord(
        decision_id="dec_test_1",
        ticker="AAPL",
        signal=signal,
        trace=[step1, step2],
        total_cost_usd=0.00035,
        total_tokens=270,
        created_at=datetime.now(UTC),
        realized_outcome=None,
    )

    repo.save(decision)

    retrieved = repo.get("dec_test_1")
    assert retrieved is not None
    assert retrieved.decision_id == "dec_test_1"
    assert retrieved.ticker == "AAPL"
    assert retrieved.signal.action == Action.BUY
    assert retrieved.signal.confidence == 0.92
    assert retrieved.signal.citations == ["obs_price_1", "obs_rsi_2"]
    assert retrieved.total_cost_usd == pytest.approx(0.00035)
    assert retrieved.total_tokens == 270

    # Trace steps
    assert len(retrieved.trace) == 2
    assert retrieved.trace[0].step_number == 1
    assert retrieved.trace[0].thought == "Checking latest market price"
    assert retrieved.trace[0].action_name == "get_latest_price"
    assert retrieved.trace[0].action_args == {"ticker": "AAPL"}
    assert retrieved.trace[1].step_number == 2
    assert retrieved.trace[1].observation_id == "obs_rsi_2"

    # Outcome reflection update
    repo.update_outcome("dec_test_1", realized_outcome=0.045)
    updated = repo.get("dec_test_1")
    assert updated is not None
    assert updated.realized_outcome == pytest.approx(0.045)

    # List queries
    recent = repo.list_recent(limit=10)
    assert len(recent) == 1
    assert recent[0].decision_id == "dec_test_1"

    by_ticker = repo.list_by_ticker("AAPL")
    assert len(by_ticker) == 1
    assert by_ticker[0].decision_id == "dec_test_1"

    empty_ticker = repo.list_by_ticker("MSFT")
    assert len(empty_ticker) == 0


@pytest.mark.issue_14
def test_order_repository_lifecycle(session_factory: sessionmaker[Session]) -> None:
    """Save order, update status, and query by ticker/recent."""
    repo = OrderRepository(session_factory)

    order = Order(
        order_id="ord_101",
        ticker="MSFT",
        action=Action.BUY,
        shares=25.0,
        limit_price=410.0,
        status=OrderStatus.PENDING,
        reason=None,
        created_at=datetime.now(UTC),
    )

    repo.save(order, decision_id="dec_test_1")

    retrieved = repo.get("ord_101")
    assert retrieved is not None
    assert retrieved.order_id == "ord_101"
    assert retrieved.ticker == "MSFT"
    assert retrieved.action == Action.BUY
    assert retrieved.shares == 25.0
    assert retrieved.status == OrderStatus.PENDING

    # Update lifecycle status
    repo.update_status("ord_101", OrderStatus.APPROVED, reason="Within risk boundaries")
    updated = repo.get("ord_101")
    assert updated is not None
    assert updated.status == OrderStatus.APPROVED
    assert updated.reason == "Within risk boundaries"

    orders = repo.list_by_ticker("MSFT")
    assert len(orders) == 1
    assert orders[0].order_id == "ord_101"

    recent = repo.list_recent()
    assert len(recent) == 1


@pytest.mark.issue_14
def test_fill_repository_crud(session_factory: sessionmaker[Session]) -> None:
    """Save fill executions and query by order ID or ticker."""
    order_repo = OrderRepository(session_factory)
    fill_repo = FillRepository(session_factory)

    # First persist parent order
    order = Order(
        order_id="ord_parent",
        ticker="NVDA",
        action=Action.BUY,
        shares=50.0,
        status=OrderStatus.APPROVED,
    )
    order_repo.save(order)

    fill1 = Fill(
        fill_id="fill_001",
        order_id="ord_parent",
        ticker="NVDA",
        action=Action.BUY,
        shares=30.0,
        price=120.05,
        commission=0.36,
        slippage=0.06,
        executed_at=datetime.now(UTC),
    )

    fill2 = Fill(
        fill_id="fill_002",
        order_id="ord_parent",
        ticker="NVDA",
        action=Action.BUY,
        shares=20.0,
        price=120.10,
        commission=0.24,
        slippage=0.04,
        executed_at=datetime.now(UTC),
    )

    fill_repo.save(fill1)
    fill_repo.save(fill2)

    retrieved = fill_repo.get("fill_001")
    assert retrieved is not None
    assert retrieved.fill_id == "fill_001"
    assert retrieved.shares == 30.0
    assert retrieved.price == pytest.approx(120.05)

    order_fills = fill_repo.list_by_order("ord_parent")
    assert len(order_fills) == 2
    assert [f.fill_id for f in order_fills] == ["fill_001", "fill_002"]

    ticker_fills = fill_repo.list_by_ticker("NVDA")
    assert len(ticker_fills) == 2


@pytest.mark.issue_14
def test_portfolio_repository_snapshots(session_factory: sessionmaker[Session]) -> None:
    """Persist portfolio snapshots and retrieve latest state and historical timeline."""
    repo = PortfolioRepository(session_factory)

    pos_aapl = Position(
        ticker="AAPL",
        shares=100.0,
        average_entry_price=180.0,
        current_price=185.0,
        unrealized_pnl=500.0,
        realized_pnl=150.0,
    )
    pos_msft = Position(
        ticker="MSFT",
        shares=50.0,
        average_entry_price=400.0,
        current_price=395.0,
        unrealized_pnl=-250.0,
        realized_pnl=0.0,
    )

    state1 = PortfolioState.create(
        cash=80000.0,
        positions={"AAPL": pos_aapl, "MSFT": pos_msft},
        updated_at=datetime(2026, 1, 1, 10, 0, tzinfo=UTC),
    )

    sid1 = repo.save(state1, snapshot_id="snap_1")
    assert sid1 == "snap_1"

    latest = repo.get_latest()
    assert latest is not None
    assert latest.cash == 80000.0
    assert "AAPL" in latest.positions
    assert "MSFT" in latest.positions
    assert latest.positions["AAPL"].shares == 100.0
    assert latest.positions["AAPL"].current_price == 185.0
    assert latest.positions["AAPL"].unrealized_pnl == 500.0

    # Save a second snapshot with higher equity
    state2 = PortfolioState.create(
        cash=90000.0,
        positions={"AAPL": pos_aapl},
        updated_at=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
    )
    repo.save(state2, snapshot_id="snap_2")

    latest2 = repo.get_latest()
    assert latest2 is not None
    assert latest2.cash == 90000.0
    assert len(latest2.positions) == 1

    history = repo.list_history()
    assert len(history) == 2
    assert history[0].cash == 80000.0
    assert history[1].cash == 90000.0
