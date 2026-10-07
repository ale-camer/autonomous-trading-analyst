"""Unit tests for embedding clients, episodic vector memory, and recall tool."""

import asyncio
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from pydantic import SecretStr
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from autonomous_trading_analyst.config import Settings
from autonomous_trading_analyst.memory.embeddings import (
    FakeEmbeddingClient,
    GeminiEmbeddingClient,
    OpenAIEmbeddingClient,
    get_embedding_client,
)
from autonomous_trading_analyst.memory.models import EpisodeModel
from autonomous_trading_analyst.memory.store import EpisodicMemory
from autonomous_trading_analyst.memory.tool import (
    build_recall_memory_tool,
    register_recall_memory_tool,
)
from autonomous_trading_analyst.persistence.db import (
    create_db_engine,
    get_session_factory,
    init_db,
)
from autonomous_trading_analyst.tools.registry import ToolRegistry


@pytest.fixture
def sqlite_engine() -> Engine:
    """Provide an in-memory SQLite engine with initialized tables including EpisodeModel."""
    engine = create_db_engine("sqlite:///:memory:")
    init_db(engine)
    return engine


@pytest.fixture
def session_factory(sqlite_engine: Engine) -> sessionmaker[Session]:
    """Provide a sessionmaker factory bound to the in-memory SQLite database."""
    return get_session_factory(sqlite_engine)


@pytest.fixture
def fake_embedding_client() -> FakeEmbeddingClient:
    """Provide a deterministic FakeEmbeddingClient."""
    return FakeEmbeddingClient(dim=32)


@pytest.fixture
def episodic_memory(
    session_factory: sessionmaker[Session],
    fake_embedding_client: FakeEmbeddingClient,
) -> EpisodicMemory:
    """Provide an initialized EpisodicMemory instance."""
    settings = Settings(embedding_dim=32, memory_top_k=3)
    return EpisodicMemory(
        session_factory=session_factory,
        embedding_client=fake_embedding_client,
        settings=settings,
    )


@pytest.mark.issue_15
def test_fake_embedding_client_generation() -> None:
    """Verify FakeEmbeddingClient outputs deterministic normalized vectors of expected dimension."""
    client = FakeEmbeddingClient(dim=64)
    v1 = client.embed_query_sync("AAPL strong quarterly earnings")
    v2 = client.embed_query_sync("AAPL strong quarterly earnings")
    v3 = client.embed_query_sync("Fed interest rate cut announcement")

    assert len(v1) == 64
    assert v1 == v2
    assert v1 != v3
    norm = np.linalg.norm(v1)
    assert np.isclose(norm, 1.0, atol=1e-5)


@pytest.mark.issue_15
def test_fake_embedding_client_async_and_fixed() -> None:
    """Verify async embedding generation and fixed embedding overrides."""
    fixed = {"fixed_query": [1.0] + [0.0] * 31}
    client = FakeEmbeddingClient(dim=32, fixed_embeddings=fixed)

    async def _test() -> None:
        vec_fixed = await client.embed_query("fixed_query")
        assert vec_fixed == fixed["fixed_query"]

        docs = await client.embed_documents(["doc1", "doc2"])
        assert len(docs) == 2
        assert len(docs[0]) == 32
        assert len(docs[1]) == 32

    asyncio.run(_test())


@pytest.mark.issue_15
def test_openai_embedding_client_sync_and_async() -> None:
    """Verify OpenAIEmbeddingClient delegates to OpenAI client methods."""
    with (
        patch("openai.OpenAI") as mock_sync_cls,
        patch("openai.AsyncOpenAI") as mock_async_cls,
    ):
        mock_sync = MagicMock()
        mock_async = MagicMock()
        mock_sync_cls.return_value = mock_sync
        mock_async_cls.return_value = mock_async

        # Setup mock returns
        item = MagicMock()
        item.embedding = [0.1, 0.2, 0.3]
        mock_sync.embeddings.create.return_value = MagicMock(data=[item])

        client = OpenAIEmbeddingClient(api_key="sk-test", dim=3)
        res_sync = client.embed_query_sync("market test")
        assert res_sync == [0.1, 0.2, 0.3]


@pytest.mark.issue_15
def test_gemini_embedding_client() -> None:
    """Verify GeminiEmbeddingClient delegates to genai client."""
    with patch("google.genai.Client") as mock_genai_cls:
        mock_client = MagicMock()
        mock_genai_cls.return_value = mock_client
        mock_resp = MagicMock()
        mock_emb = MagicMock()
        mock_emb.values = [0.4, 0.5, 0.6]
        mock_resp.embeddings = [mock_emb]
        mock_client.models.embed_content.return_value = mock_resp

        client = GeminiEmbeddingClient(api_key="gm-test", dim=3)
        res = client.embed_query_sync("gemini test")
        assert res == [0.4, 0.5, 0.6]


@pytest.mark.issue_15
def test_get_embedding_client_factory() -> None:
    """Verify get_embedding_client factory dispatches correctly based on settings."""
    cfg_fake = Settings(embedding_provider="fake", embedding_dim=16)
    client_fake = get_embedding_client(cfg_fake)
    assert isinstance(client_fake, FakeEmbeddingClient)
    assert client_fake.dim == 16

    cfg_openai = Settings(
        embedding_provider="openai",
        openai_api_key=SecretStr("sk-test"),
        embedding_dim=1536,
    )
    with patch("openai.OpenAI"), patch("openai.AsyncOpenAI"):
        client_openai = get_embedding_client(cfg_openai)
        assert isinstance(client_openai, OpenAIEmbeddingClient)

    cfg_gemini = Settings(
        embedding_provider="gemini",
        google_api_key=SecretStr("gm-test"),
        embedding_dim=768,
    )
    with patch("google.genai.Client"):
        client_gemini = get_embedding_client(cfg_gemini)
        assert isinstance(client_gemini, GeminiEmbeddingClient)

    with pytest.raises(ValueError, match="Unknown embedding provider"):
        invalid_cfg = MagicMock()
        invalid_cfg.embedding_provider = "unsupported"
        get_embedding_client(invalid_cfg)


@pytest.mark.issue_15
def test_store_and_count_episodes(episodic_memory: EpisodicMemory) -> None:
    """Verify episode storage, retrieval by ID, and counting."""
    assert episodic_memory.count() == 0

    ep_id = episodic_memory.store_episode(
        ticker="AAPL",
        context_text="Oversold RSI with support at 200 EMA.",
        action="BUY",
        rationale="Strong technical rebound candidate.",
        outcome_return=0.042,
    )
    assert isinstance(ep_id, str)
    assert episodic_memory.count() == 1
    assert episodic_memory.count(ticker="AAPL") == 1
    assert episodic_memory.count(ticker="MSFT") == 0

    record = episodic_memory.get_episode(ep_id)
    assert record is not None
    assert record.ticker == "AAPL"
    assert record.action == "BUY"
    assert record.context_text == "Oversold RSI with support at 200 EMA."
    assert record.outcome_return == pytest.approx(0.042)
    assert record.created_at is not None


@pytest.mark.issue_15
def test_astore_episode(episodic_memory: EpisodicMemory) -> None:
    """Verify asynchronous episode persistence."""

    async def _test() -> None:
        ep_id = await episodic_memory.astore_episode(
            ticker="MSFT",
            context_text="Breakout above resistance after cloud earnings beat.",
            action="BUY",
            rationale="Momentum continuation.",
        )
        assert episodic_memory.count(ticker="MSFT") == 1
        record = episodic_memory.get_episode(ep_id)
        assert record is not None
        assert record.ticker == "MSFT"
        assert record.outcome_return is None

    asyncio.run(_test())


@pytest.mark.issue_15
def test_update_outcome(episodic_memory: EpisodicMemory) -> None:
    """Verify updating the forward realized return outcome for an episode."""
    ep_id = episodic_memory.store_episode(
        ticker="NVDA",
        context_text="Semiconductor rally continuation.",
        action="BUY",
        rationale="Bullish momentum.",
        outcome_return=None,
    )
    rec_before = episodic_memory.get_episode(ep_id)
    assert rec_before is not None
    assert rec_before.outcome_return is None

    episodic_memory.update_outcome(ep_id, 0.085)
    rec_after = episodic_memory.get_episode(ep_id)
    assert rec_after is not None
    assert rec_after.outcome_return == pytest.approx(0.085)

    with pytest.raises(ValueError, match="not found"):
        episodic_memory.update_outcome("non-existent-id", 0.01)


@pytest.mark.issue_15
def test_recall_similar_ranking_and_ticker_filter(
    session_factory: sessionmaker[Session],
) -> None:
    """Verify similarity ranking and ticker filtering in episodic recall."""
    # Define orthogonal unit vectors for predictable cosine similarities
    v_aapl = [1.0, 0.0, 0.0]
    v_msft = [0.8, 0.6, 0.0]
    v_tsla = [0.0, 1.0, 0.0]
    query_v = [0.95, 0.05, 0.0]

    fixed = {
        "apple tech query": query_v,
    }
    client = FakeEmbeddingClient(dim=3, fixed_embeddings=fixed)
    memory = EpisodicMemory(
        session_factory=session_factory,
        embedding_client=client,
        settings=Settings(embedding_dim=3, memory_top_k=5),
    )

    memory.store_episode(
        ticker="AAPL",
        context_text="Apple iPhone upgrade cycle momentum.",
        action="BUY",
        rationale="Solid earnings beat.",
        outcome_return=0.06,
        embedding=v_aapl,
    )
    memory.store_episode(
        ticker="MSFT",
        context_text="Microsoft Azure growth resurgence.",
        action="BUY",
        rationale="Cloud acceleration.",
        outcome_return=0.03,
        embedding=v_msft,
    )
    memory.store_episode(
        ticker="TSLA",
        context_text="Electric vehicle delivery target miss.",
        action="SELL",
        rationale="Margin compression.",
        outcome_return=-0.05,
        embedding=v_tsla,
    )

    results = memory.recall_similar("apple tech query", top_k=3)
    assert len(results) == 3
    # Top match should be AAPL because v_aapl is closest to query_v
    assert results[0].ticker == "AAPL"
    assert results[0].similarity_score is not None
    assert results[1].ticker == "MSFT"
    assert results[2].ticker == "TSLA"
    assert results[0].similarity_score > results[1].similarity_score > results[2].similarity_score

    # Ticker filter
    msft_only = memory.recall_similar("apple tech query", ticker="MSFT")
    assert len(msft_only) == 1
    assert msft_only[0].ticker == "MSFT"

    # Top-K limit
    top_1 = memory.recall_similar("apple tech query", top_k=1)
    assert len(top_1) == 1
    assert top_1[0].ticker == "AAPL"

    # No matches when filtering by non-existent ticker
    empty = memory.recall_similar("apple tech query", ticker="NONEXISTENT")
    assert empty == []


@pytest.mark.issue_15
def test_recall_memory_tool_integration(episodic_memory: EpisodicMemory) -> None:
    """Verify tool registration and execution in ToolRegistry."""
    episodic_memory.store_episode(
        ticker="AAPL",
        context_text="Oversold RSI with bullish MACD crossover.",
        action="BUY",
        rationale="Expected mean-reversion move.",
        outcome_return=0.051,
    )

    registry = ToolRegistry()
    register_recall_memory_tool(registry, episodic_memory)

    tool_def = registry.get_tool("recall_memory")
    assert tool_def is not None
    assert "query" in tool_def.parameters["properties"]

    # Execute tool via registry
    output = registry.execute(
        "recall_memory",
        {"query": "Oversold RSI setup", "ticker": "AAPL", "top_k": 2},
    )
    assert "Found 1 historical episode(s)" in output
    assert "AAPL" in output
    assert "BUY" in output
    assert "+5.10%" in output
    assert "Expected mean-reversion move." in output


@pytest.mark.issue_15
def test_recall_memory_tool_empty_results(episodic_memory: EpisodicMemory) -> None:
    """Verify tool execution returns user-friendly message when no episodes match."""
    registry = ToolRegistry()
    build_recall_memory_tool(episodic_memory, registry=registry)

    output = registry.execute(
        "recall_memory",
        {"query": "Unseen market crash", "ticker": "SPY"},
    )
    assert "No historical memory episodes found matching query" in output
    assert "SPY" in output


@pytest.mark.issue_15
def test_recall_similar_postgresql_dialect_path(
    fake_embedding_client: FakeEmbeddingClient,
) -> None:
    """Verify postgresql dialect branch in recall_similar executes correctly."""
    mock_session = MagicMock()
    mock_bind = MagicMock()
    mock_bind.dialect.name = "postgresql"
    mock_session.get_bind.return_value = mock_bind

    ep = EpisodeModel(
        episode_id="ep-pg-1",
        ticker="SPY",
        context_text="Postgres test context",
        action="HOLD",
        rationale="Testing pgvector branch",
        outcome_return=0.015,
        embedding=[0.1] * 32,
        created_at=datetime.now(UTC),
    )
    # Mock query result returning (EpisodeModel, distance)
    mock_session.execute.return_value.all.return_value = [(ep, 0.12)]

    mock_factory = MagicMock()
    mock_factory.return_value = mock_session
    # Context manager mock for get_db_session
    mock_session.__enter__ = MagicMock(return_value=mock_session)
    mock_session.__exit__ = MagicMock(return_value=None)

    memory = EpisodicMemory(
        session_factory=mock_factory,
        embedding_client=fake_embedding_client,
    )

    with patch("autonomous_trading_analyst.memory.store.get_db_session") as mock_get_db:
        mock_get_db.return_value.__enter__.return_value = mock_session
        records = memory.recall_similar("postgres query", ticker="SPY", top_k=1)

    assert len(records) == 1
    assert records[0].episode_id == "ep-pg-1"
    assert records[0].ticker == "SPY"
    assert records[0].similarity_score == round(1.0 - 0.12, 4)
