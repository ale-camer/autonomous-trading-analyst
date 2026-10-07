"""Unit and integration tests for the end-to-end analysis cycle orchestrator."""

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from autonomous_trading_analyst.broker.paper import PaperBroker
from autonomous_trading_analyst.config import Settings
from autonomous_trading_analyst.cycle import (
    create_analysis_cycle,
)
from autonomous_trading_analyst.domain.cycle import CycleSummary
from autonomous_trading_analyst.domain.models import (
    Action,
    Order,
    OrderStatus,
    Position,
)
from autonomous_trading_analyst.llm.fake import FakeLLMClient
from autonomous_trading_analyst.llm.messages import Message, Role, ToolCall
from autonomous_trading_analyst.memory.embeddings import FakeEmbeddingClient
from autonomous_trading_analyst.memory.store import EpisodicMemory
from autonomous_trading_analyst.persistence.db import (
    create_db_engine,
    get_session_factory,
    init_db,
)
from autonomous_trading_analyst.persistence.repositories import (
    DecisionRepository,
    FillRepository,
    OrderRepository,
    PortfolioRepository,
)
from autonomous_trading_analyst.risk.manager import RiskManager
from autonomous_trading_analyst.tools.market_data.fake import FakeMarketDataProvider


@pytest.fixture
def sqlite_engine() -> Engine:
    """Fixture providing an in-memory SQLite database engine."""
    engine = create_db_engine("sqlite:///:memory:")
    init_db(engine)
    return engine


@pytest.fixture
def session_factory(sqlite_engine: Engine) -> sessionmaker[Session]:
    """Fixture providing a session factory bound to SQLite in-memory."""
    return get_session_factory(sqlite_engine)


@pytest.fixture
def fake_market_data() -> FakeMarketDataProvider:
    """Fixture providing a deterministic market data provider with default price 150.0."""
    return FakeMarketDataProvider(default_price=150.0)


def _build_scripted_llm_for_buy_and_hold() -> FakeLLMClient:
    """Script a FakeLLMClient returning a BUY for AAPL and a HOLD for MSFT."""
    responses = [
        # Call 1 for AAPL: inspect price
        Message(
            role=Role.ASSISTANT,
            content="Checking current price for AAPL.",
            tool_calls=[
                ToolCall(id="call_p1", name="get_latest_price", arguments={"ticker": "AAPL"}),
            ],
        ),
        # Call 2 for AAPL: submit BUY signal
        Message(
            role=Role.ASSISTANT,
            content="Price is attractive, submitting BUY signal.",
            tool_calls=[
                ToolCall(
                    id="call_s1",
                    name="submit_signal",
                    arguments={
                        "ticker": "AAPL",
                        "decision": "BUY",
                        "confidence": 0.85,
                        "rationale": "Breakout confirmed by price analysis.",
                    },
                ),
            ],
        ),
        # Call 3 for MSFT: submit HOLD signal directly
        Message(
            role=Role.ASSISTANT,
            content="No setup present, submitting HOLD.",
            tool_calls=[
                ToolCall(
                    id="call_s2",
                    name="submit_signal",
                    arguments={
                        "ticker": "MSFT",
                        "decision": "HOLD",
                        "confidence": 0.60,
                        "rationale": "Consolidation phase with low volume.",
                    },
                ),
            ],
        ),
    ]
    return FakeLLMClient(responses=responses)


@pytest.mark.issue_17
def test_end_to_end_cycle_execution(
    session_factory: sessionmaker[Session],
    fake_market_data: FakeMarketDataProvider,
) -> None:
    """Verify complete offline analysis cycle execution across watchlist, risk, and storage."""
    llm = _build_scripted_llm_for_buy_and_hold()
    emb = FakeEmbeddingClient(dim=16)
    settings = Settings(
        watchlist=["AAPL", "MSFT"],
        risk_max_position_pct=0.10,
        risk_stop_loss_pct=0.08,
        paper_initial_cash=100000.0,
    )

    orchestrator = create_analysis_cycle(
        session_factory=session_factory,
        market_data_provider=fake_market_data,
        llm_client=llm,
        embedding_client=emb,
        settings=settings,
    )

    summary: CycleSummary = orchestrator.run_cycle_sync(watchlist=["AAPL", "MSFT"])

    # 1. Summary assertions
    assert summary.watchlist == ["AAPL", "MSFT"]
    assert len(summary.decisions) == 2
    assert len(summary.orders) == 1  # Only AAPL produced an order (BUY)
    assert len(summary.fills) == 1
    assert summary.errors == {}
    assert summary.portfolio_state.cash < 100000.0
    assert "AAPL" in summary.portfolio_state.positions

    # 2. Database verification
    dec_repo = DecisionRepository(session_factory)
    ord_repo = OrderRepository(session_factory)
    fill_repo = FillRepository(session_factory)
    port_repo = PortfolioRepository(session_factory)

    # Decisions persisted with trace steps
    db_dec_aapl = dec_repo.get(summary.decisions[0].decision_id)
    assert db_dec_aapl is not None
    assert db_dec_aapl.ticker == "AAPL"
    assert db_dec_aapl.signal.action == Action.BUY
    assert len(db_dec_aapl.trace) >= 1

    # Order and Fill persisted
    order_aapl = summary.orders[0]
    db_order = ord_repo.get(order_aapl.order_id)
    assert db_order is not None
    assert db_order.status == OrderStatus.APPROVED

    fill_aapl = summary.fills[0]
    db_fill = fill_repo.get(fill_aapl.fill_id)
    assert db_fill is not None
    assert db_fill.ticker == "AAPL"

    # Latest portfolio snapshot
    latest_port = port_repo.get_latest()
    assert latest_port is not None
    assert "AAPL" in latest_port.positions

    # 3. Episodic Memory verification
    memory = EpisodicMemory(session_factory, embedding_client=emb, settings=settings)
    assert memory.count() == 2
    recalled = memory.recall_similar("Breakout confirmed by price analysis", ticker="AAPL")
    assert len(recalled) >= 1
    assert recalled[0].action == "BUY"


@pytest.mark.issue_17
def test_cycle_stop_loss_sweep(
    session_factory: sessionmaker[Session],
    fake_market_data: FakeMarketDataProvider,
) -> None:
    """Verify stop-loss sweep triggers approved exit orders when unrealized losses exceed limit."""
    broker = PaperBroker(initial_cash=50000.0)
    # Manually inject open position with entry price 200.0
    broker._positions["TSLA"] = Position(
        ticker="TSLA",
        shares=50.0,
        average_entry_price=200.0,
        current_price=200.0,
        unrealized_pnl=0.0,
        realized_pnl=0.0,
    )

    # Set current market price to 180.0 (loss of 10%, breaching default 8% stop loss)
    fake_market_data._default_price = 180.0

    # Script LLM to simply HOLD for SPY
    responses = [
        Message(
            role=Role.ASSISTANT,
            content="Holding SPY.",
            tool_calls=[
                ToolCall(
                    id="call_spy",
                    name="submit_signal",
                    arguments={"ticker": "SPY", "decision": "HOLD", "rationale": "Neutral."},
                ),
            ],
        ),
    ]
    llm = FakeLLMClient(responses=responses)
    settings = Settings(watchlist=["SPY"], risk_stop_loss_pct=0.08)

    orchestrator = create_analysis_cycle(
        session_factory=session_factory,
        market_data_provider=fake_market_data,
        llm_client=llm,
        paper_broker=broker,
        settings=settings,
    )

    summary = orchestrator.run_cycle_sync(watchlist=["SPY"])

    assert len(summary.stop_loss_orders) == 1
    stop_order = summary.stop_loss_orders[0]
    assert stop_order.ticker == "TSLA"
    assert stop_order.action == Action.SELL
    assert stop_order.status == OrderStatus.APPROVED
    assert "Stop-loss triggered" in (stop_order.reason or "")

    # Position in TSLA should now be closed
    assert "TSLA" not in summary.portfolio_state.positions


@pytest.mark.issue_17
def test_cycle_risk_rejection_on_daily_trades_limit(
    session_factory: sessionmaker[Session],
    fake_market_data: FakeMarketDataProvider,
) -> None:
    """Verify risk manager rejects orders when daily trades limit is breached."""
    # Script BUY for AAPL
    responses = [
        Message(
            role=Role.ASSISTANT,
            content="Buy AAPL.",
            tool_calls=[
                ToolCall(
                    id="call_1",
                    name="submit_signal",
                    arguments={"ticker": "AAPL", "decision": "BUY", "rationale": "Buy."},
                ),
            ],
        ),
    ]
    llm = FakeLLMClient(responses=responses)
    # Configure max 0 trades per day to force rejection
    settings = Settings(watchlist=["AAPL"], risk_max_trades_per_day=1)
    risk_manager = RiskManager(settings=settings)

    orchestrator = create_analysis_cycle(
        session_factory=session_factory,
        market_data_provider=fake_market_data,
        llm_client=llm,
        risk_manager=risk_manager,
        settings=settings,
    )

    # Pre-simulate 1 fill today so next order hits trades_today limit
    pre_fill = orchestrator.broker.execute_order(
        Order(
            order_id="ord_pre",
            ticker="AAPL",
            action=Action.BUY,
            shares=1.0,
            status=OrderStatus.APPROVED,
        ),
        market_price=150.0,
    )
    assert pre_fill is not None

    summary = orchestrator.run_cycle_sync(watchlist=["AAPL"])
    assert len(summary.orders) == 1
    rejected_order = summary.orders[0]
    assert rejected_order.status == OrderStatus.REJECTED
    assert "Daily trade limit reached" in (rejected_order.reason or "")
    assert len(summary.fills) == 0


@pytest.mark.issue_17
def test_cycle_agent_fallback_on_unsubmitted_signal(
    session_factory: sessionmaker[Session],
    fake_market_data: FakeMarketDataProvider,
) -> None:
    """Verify cycle gracefully creates a default HOLD signal if agent fails to call
    submit_signal.
    """
    # LLM outputs message without any tool calls or submit_signal
    responses = [
        Message(role=Role.ASSISTANT, content="Thinking endlessly without submitting signal.")
    ]
    llm = FakeLLMClient(responses=responses)
    settings = Settings(watchlist=["AAPL"], agent_max_steps=1)

    orchestrator = create_analysis_cycle(
        session_factory=session_factory,
        market_data_provider=fake_market_data,
        llm_client=llm,
        settings=settings,
    )

    summary = orchestrator.run_cycle_sync(watchlist=["AAPL"])
    assert len(summary.decisions) == 1
    dec = summary.decisions[0]
    assert dec.signal.action == Action.HOLD
    assert "without submitting" in dec.signal.rationale
    assert len(summary.orders) == 0


@pytest.mark.issue_17
def test_cycle_resilient_error_handling(
    session_factory: sessionmaker[Session],
    fake_market_data: FakeMarketDataProvider,
) -> None:
    """Verify error on one ticker does not halt processing of subsequent watchlist tickers."""

    class ErrorRaisingLLM(FakeLLMClient):
        def __init__(self) -> None:
            super().__init__(responses=[])

        async def generate(self, messages, tools=None):
            # Error on NVDA
            for m in messages:
                if "NVDA" in m.content:
                    msg = "Simulated API timeout for NVDA"
                    raise RuntimeError(msg)
            return (
                Message(
                    role=Role.ASSISTANT,
                    content="Hold AAPL.",
                    tool_calls=[
                        ToolCall(
                            id="call_ok",
                            name="submit_signal",
                            arguments={"ticker": "AAPL", "decision": "HOLD", "rationale": "Ok."},
                        ),
                    ],
                ),
                {"total_tokens": 10, "cost_usd": 0.001},
            )

    llm = ErrorRaisingLLM()
    settings = Settings(watchlist=["NVDA", "AAPL"])

    orchestrator = create_analysis_cycle(
        session_factory=session_factory,
        market_data_provider=fake_market_data,
        llm_client=llm,
        settings=settings,
    )

    summary = orchestrator.run_cycle_sync(watchlist=["NVDA", "AAPL"])
    assert "NVDA" in summary.errors
    assert "Simulated API timeout" in summary.errors["NVDA"]
    # AAPL succeeded despite NVDA error
    assert len(summary.decisions) == 1
    assert summary.decisions[0].ticker == "AAPL"
