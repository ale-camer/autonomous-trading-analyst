"""Unit and integration tests for the FastAPI trading and portfolio endpoints."""

from collections.abc import Generator
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from autonomous_trading_analyst.api import create_app
from autonomous_trading_analyst.api.dependencies import (
    get_orchestrator_dep,
    get_session_factory_dep,
)
from autonomous_trading_analyst.config import Settings
from autonomous_trading_analyst.cycle import (
    AnalysisCycleOrchestrator,
    create_analysis_cycle,
)
from autonomous_trading_analyst.domain.models import (
    Action,
    DecisionRecord,
    PortfolioState,
    Position,
    Signal,
    TraceStep,
)
from autonomous_trading_analyst.llm.fake import FakeLLMClient
from autonomous_trading_analyst.llm.messages import Message, Role, ToolCall
from autonomous_trading_analyst.memory.embeddings import FakeEmbeddingClient
from autonomous_trading_analyst.persistence.db import (
    get_session_factory,
    init_db,
)
from autonomous_trading_analyst.persistence.repositories import (
    DecisionRepository,
    PortfolioRepository,
)
from autonomous_trading_analyst.tools.market_data.fake import FakeMarketDataProvider


@pytest.fixture
def sqlite_engine() -> Engine:
    """Provide an in-memory SQLite database engine shared across threads."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    init_db(engine)
    return engine


@pytest.fixture
def session_factory(sqlite_engine: Engine) -> sessionmaker[Session]:
    """Provide a session factory bound to SQLite in-memory."""
    return get_session_factory(sqlite_engine)


@pytest.fixture
def test_orchestrator(session_factory: sessionmaker[Session]) -> AnalysisCycleOrchestrator:
    """Provide an AnalysisCycleOrchestrator wired with deterministic offline fakes."""
    fake_market = FakeMarketDataProvider(default_price=150.0)
    fake_market.seed_latest_price("AAPL", 150.0)
    fake_market.seed_latest_price("NVDA", 200.0)

    fake_llm = FakeLLMClient(
        responses=[
            Message(
                role=Role.ASSISTANT,
                content="Holding position.",
                tool_calls=[
                    ToolCall(
                        id="call_hold",
                        name="submit_signal",
                        arguments={
                            "action": "HOLD",
                            "confidence": 0.8,
                            "rationale": "Neutral market conditions, keeping position.",
                            "citations": [],
                        },
                    )
                ],
            )
        ]
    )
    fake_emb = FakeEmbeddingClient(dim=1536)

    return create_analysis_cycle(
        session_factory=session_factory,
        market_data_provider=fake_market,
        llm_client=fake_llm,
        embedding_client=fake_emb,
        settings=Settings(app_env="local", watchlist=["AAPL"]),
    )


@pytest.fixture
def client(
    session_factory: sessionmaker[Session],
    test_orchestrator: AnalysisCycleOrchestrator,
) -> Generator[TestClient, None, None]:
    """Provide a TestClient with overridden dependencies for testing."""
    app = create_app()
    app.dependency_overrides[get_session_factory_dep] = lambda: session_factory
    app.dependency_overrides[get_orchestrator_dep] = lambda: test_orchestrator

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


def _make_sample_decision(
    decision_id: str,
    ticker: str,
    created_at: datetime | None = None,
) -> DecisionRecord:
    """Helper creating a valid DecisionRecord with multiple trace steps."""
    ts = created_at or datetime.now(UTC)
    signal = Signal(
        ticker=ticker,
        action=Action.HOLD,
        size=0.0,
        confidence=0.75,
        rationale="RSI is neutral; maintain position.",
        citations=[],
        timestamp=ts,
    )
    trace = [
        TraceStep(
            step_number=1,
            thought="Inspecting RSI and MACD indicators for momentum.",
            action_name="get_rsi",
            action_args={"ticker": ticker},
            observation_id="obs_101",
            observation="RSI is 52.3 (neutral)",
            tokens_used=120,
            cost_usd=0.00015,
            timestamp=ts,
        ),
        TraceStep(
            step_number=2,
            thought="Checking news sentiment and market anomalies.",
            action_name="get_anomalies",
            action_args={"ticker": ticker},
            observation_id="obs_102",
            observation="No volume anomalies detected",
            tokens_used=140,
            cost_usd=0.00018,
            timestamp=ts,
        ),
    ]
    return DecisionRecord(
        decision_id=decision_id,
        ticker=ticker,
        signal=signal,
        trace=trace,
        total_cost_usd=0.00033,
        total_tokens=260,
        created_at=ts,
        realized_outcome=None,
    )


@pytest.mark.issue_22
def test_health_endpoint_ok(client: TestClient) -> None:
    """GET /health returns 200 OK and connected database status."""
    response = client.get("/health")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["status"] == "ok"
    assert data["database"] == "connected"
    assert data["app_env"] == "local"
    assert "timestamp" in data


@pytest.mark.issue_22
def test_health_endpoint_db_failure() -> None:
    """GET /health returns 503 Service Unavailable when DB is unreachable."""
    app = create_app()
    failing_factory = MagicMock(side_effect=RuntimeError("Connection refused"))
    app.dependency_overrides[get_session_factory_dep] = lambda: failing_factory

    with TestClient(app) as failing_client:
        response = failing_client.get("/health")
        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        data = response.json()
        assert "Database unreachable" in data["detail"]


@pytest.mark.issue_22
def test_get_portfolio_initial(client: TestClient) -> None:
    """GET /portfolio returns initial empty portfolio state when no snapshot exists."""
    response = client.get("/portfolio")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["cash"] == 100000.0
    assert data["positions"] == {}
    assert data["total_equity"] == 100000.0
    assert data["gross_exposure"] == 0.0
    assert "updated_at" in data


@pytest.mark.issue_22
def test_get_portfolio_persisted_snapshot(
    client: TestClient,
    session_factory: sessionmaker[Session],
) -> None:
    """GET /portfolio returns latest saved PortfolioSnapshotModel when available."""
    pos = Position(
        ticker="AAPL",
        shares=10.0,
        average_entry_price=140.0,
        current_price=150.0,
        unrealized_pnl=100.0,
        realized_pnl=0.0,
    )
    saved_state = PortfolioState.create(
        cash=90000.0,
        positions={"AAPL": pos},
        updated_at=datetime(2026, 1, 15, tzinfo=UTC),
    )
    repo = PortfolioRepository(session_factory)
    repo.save(saved_state)

    response = client.get("/portfolio")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["cash"] == 90000.0
    assert "AAPL" in data["positions"]
    assert data["positions"]["AAPL"]["shares"] == 10.0
    assert data["total_equity"] == 91500.0


@pytest.mark.issue_22
def test_get_decisions_empty(client: TestClient) -> None:
    """GET /decisions returns an empty list when no decisions exist."""
    response = client.get("/decisions")
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == []


@pytest.mark.issue_22
def test_get_decisions_list_and_filter(
    client: TestClient,
    session_factory: sessionmaker[Session],
) -> None:
    """GET /decisions supports ticker filtering and pagination limit."""
    repo = DecisionRepository(session_factory)
    d1 = _make_sample_decision("dec_1", "AAPL", datetime(2026, 1, 1, tzinfo=UTC))
    d2 = _make_sample_decision("dec_2", "MSFT", datetime(2026, 1, 2, tzinfo=UTC))
    d3 = _make_sample_decision("dec_3", "AAPL", datetime(2026, 1, 3, tzinfo=UTC))
    repo.save(d1)
    repo.save(d2)
    repo.save(d3)

    # All decisions
    res_all = client.get("/decisions")
    assert res_all.status_code == status.HTTP_200_OK
    data_all = res_all.json()
    assert len(data_all) == 3

    # Filter by ticker
    res_aapl = client.get("/decisions?ticker=AAPL")
    assert res_aapl.status_code == status.HTTP_200_OK
    data_aapl = res_aapl.json()
    assert len(data_aapl) == 2
    assert all(d["ticker"] == "AAPL" for d in data_aapl)

    # Limit query
    res_lim = client.get("/decisions?limit=1")
    assert res_lim.status_code == status.HTTP_200_OK
    assert len(res_lim.json()) == 1


@pytest.mark.issue_22
def test_get_decision_by_id_found(
    client: TestClient,
    session_factory: sessionmaker[Session],
) -> None:
    """GET /decisions/{id} returns full decision record including all trace steps."""
    repo = DecisionRepository(session_factory)
    d = _make_sample_decision("dec_trace_test", "AAPL")
    repo.save(d)

    response = client.get("/decisions/dec_trace_test")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["decision_id"] == "dec_trace_test"
    assert data["ticker"] == "AAPL"
    assert data["signal"]["action"] == "HOLD"
    assert len(data["trace"]) == 2
    assert data["trace"][0]["step_number"] == 1
    assert data["trace"][0]["action_name"] == "get_rsi"
    assert data["trace"][1]["step_number"] == 2
    assert data["trace"][1]["action_name"] == "get_anomalies"


@pytest.mark.issue_22
def test_get_decision_by_id_not_found(client: TestClient) -> None:
    """GET /decisions/{id} returns 404 when ID does not exist."""
    response = client.get("/decisions/unknown_id")
    assert response.status_code == status.HTTP_404_NOT_FOUND
    data = response.json()
    assert "Decision 'unknown_id' not found" in data["detail"]


@pytest.mark.issue_22
def test_post_cycles_default_payload(client: TestClient) -> None:
    """POST /cycles triggers analysis cycle with default settings when body is empty."""
    response = client.post("/cycles", json={})
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["cycle_id"].startswith("cycle_")
    assert data["watchlist"] == ["AAPL"]
    assert "portfolio_state" in data

    # Verify portfolio snapshot was persisted and is queryable
    port_res = client.get("/portfolio")
    assert port_res.status_code == status.HTTP_200_OK
    assert port_res.json()["cash"] == data["portfolio_state"]["cash"]


@pytest.mark.issue_22
def test_post_cycles_custom_parameters(client: TestClient) -> None:
    """POST /cycles triggers analysis cycle with custom watchlist and as_of timestamp."""
    payload = {
        "watchlist": ["nvda", " aapl "],
        "as_of": "2026-01-10T14:30:00Z",
    }
    response = client.post("/cycles", json=payload)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["watchlist"] == ["NVDA", "AAPL"]
    assert data["timestamp"] == "2026-01-10T14:30:00Z"


@pytest.mark.issue_22
def test_post_cycles_invalid_extra_field(client: TestClient) -> None:
    """POST /cycles returns 422 Unprocessable Entity when extra fields are supplied."""
    payload = {
        "watchlist": ["AAPL"],
        "unexpected_field": "disallowed",
    }
    response = client.post("/cycles", json=payload)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


@pytest.mark.issue_22
def test_cycle_request_normalization() -> None:
    """CycleRequest handles empty strings by normalizing to None."""
    from autonomous_trading_analyst.api.schemas import CycleRequest

    req_none = CycleRequest(watchlist=None)
    assert req_none.watchlist is None

    req_empty = CycleRequest(watchlist=["   ", ""])
    assert req_empty.watchlist is None


@pytest.mark.issue_22
def test_create_app_custom_settings(session_factory: sessionmaker[Session]) -> None:
    """create_app configures dependency overrides when settings parameter is provided."""
    custom_settings = Settings(app_env="staging")
    app = create_app(settings=custom_settings)
    app.dependency_overrides[get_session_factory_dep] = lambda: session_factory

    with TestClient(app) as test_client:
        res = test_client.get("/health")
        assert res.status_code == status.HTTP_200_OK
        assert res.json()["app_env"] == "staging"


@pytest.mark.issue_22
def test_dependency_providers_direct(
    session_factory: sessionmaker[Session],
) -> None:
    """Directly test default dependency helper functions."""
    from autonomous_trading_analyst.api.dependencies import (
        get_decision_repo_dep,
        get_orchestrator_dep,
        get_portfolio_repo_dep,
        get_settings_dep,
    )

    settings = get_settings_dep()
    assert isinstance(settings, Settings)

    dec_repo = get_decision_repo_dep(session_factory)
    assert isinstance(dec_repo, DecisionRepository)

    port_repo = get_portfolio_repo_dep(session_factory)
    assert isinstance(port_repo, PortfolioRepository)

    orch = get_orchestrator_dep(
        session_factory=session_factory,
        settings=Settings(app_env="local", market_data_provider="fake", llm_provider="fake"),
    )
    assert isinstance(orch, AnalysisCycleOrchestrator)
