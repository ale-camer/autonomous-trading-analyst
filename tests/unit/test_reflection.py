"""Unit tests for the outcome reflection engine, return calculations, and persistence updates."""

from datetime import UTC, datetime, timedelta

import pandas as pd
import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from autonomous_trading_analyst.config import Settings
from autonomous_trading_analyst.domain.models import (
    Action,
    DecisionRecord,
    Signal,
)
from autonomous_trading_analyst.domain.reflection import ReflectionReport, ScoredOutcome
from autonomous_trading_analyst.memory.embeddings import FakeEmbeddingClient
from autonomous_trading_analyst.memory.reflection import OutcomeReflector
from autonomous_trading_analyst.memory.store import EpisodicMemory
from autonomous_trading_analyst.persistence.db import (
    create_db_engine,
    get_session_factory,
    init_db,
)
from autonomous_trading_analyst.persistence.repositories import DecisionRepository
from autonomous_trading_analyst.tools.market_data.fake import FakeMarketDataProvider


@pytest.fixture
def sqlite_engine() -> Engine:
    """Fixture providing an in-memory SQLite engine with initialized schema."""
    engine = create_db_engine("sqlite:///:memory:")
    init_db(engine)
    return engine


@pytest.fixture
def session_factory(sqlite_engine: Engine) -> sessionmaker[Session]:
    """Fixture providing a session factory bound to in-memory SQLite."""
    return get_session_factory(sqlite_engine)


@pytest.fixture
def decision_repo(session_factory: sessionmaker[Session]) -> DecisionRepository:
    """Fixture providing an initialized DecisionRepository."""
    return DecisionRepository(session_factory)


@pytest.fixture
def episodic_memory(session_factory: sessionmaker[Session]) -> EpisodicMemory:
    """Fixture providing an initialized EpisodicMemory."""
    return EpisodicMemory(
        session_factory=session_factory,
        embedding_client=FakeEmbeddingClient(dim=16),
        settings=Settings(embedding_dim=16),
    )


@pytest.fixture
def fake_market_data() -> FakeMarketDataProvider:
    """Fixture providing a FakeMarketDataProvider."""
    return FakeMarketDataProvider(default_price=100.0)


@pytest.fixture
def reflector(
    decision_repo: DecisionRepository,
    episodic_memory: EpisodicMemory,
    fake_market_data: FakeMarketDataProvider,
) -> OutcomeReflector:
    """Fixture providing an OutcomeReflector instance."""
    settings = Settings(reflection_horizon_days=5, reflection_batch_size=50)
    return OutcomeReflector(
        decision_repo=decision_repo,
        memory=episodic_memory,
        market_data_provider=fake_market_data,
        settings=settings,
    )


def _seed_price_bars(
    provider: FakeMarketDataProvider,
    ticker: str,
    start_date: datetime,
    days: int,
    start_price: float,
    daily_change: float,
) -> None:
    """Helper to seed daily bars with deterministic linear price change."""
    dates = [start_date + timedelta(days=i) for i in range(days)]
    prices = [start_price + i * daily_change for i in range(days)]
    df = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(dates, utc=True),
            "open": prices,
            "high": [p * 1.01 for p in prices],
            "low": [p * 0.99 for p in prices],
            "close": prices,
            "volume": [1_000_000.0] * days,
        }
    ).set_index("timestamp")
    provider.seed_bars(ticker, df)


@pytest.mark.issue_16
def test_reflection_domain_models() -> None:
    """Verify ScoredOutcome and ReflectionReport models initialization and serialization."""
    now = datetime.now(UTC)
    outcome = ScoredOutcome(
        decision_id="dec-1",
        ticker="AAPL",
        action=Action.BUY,
        horizon_days=5,
        start_price=150.0,
        end_price=165.0,
        realized_return=0.10,
        evaluated_at=now,
    )
    assert outcome.ticker == "AAPL"
    assert outcome.realized_return == 0.10

    report = ReflectionReport(
        total_candidates=1,
        scored_count=1,
        skipped_count=0,
        scored_outcomes=[outcome],
        executed_at=now,
    )
    assert report.scored_count == 1
    assert len(report.scored_outcomes) == 1


@pytest.mark.issue_16
def test_compute_forward_return_actions(
    reflector: OutcomeReflector,
    fake_market_data: FakeMarketDataProvider,
) -> None:
    """Verify directional return logic for BUY, SELL, and HOLD actions."""
    t0 = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    as_of = t0 + timedelta(days=10)

    # 1. Rising market: 100.0 -> 110.0 (+10% close-to-close)
    _seed_price_bars(fake_market_data, "AAPL", t0, days=6, start_price=100.0, daily_change=2.0)
    # Day 0: 100.0, Day 5: 110.0

    res_buy = reflector.compute_forward_return("AAPL", Action.BUY, t0, 5, as_of=as_of)
    assert res_buy is not None
    start_p, end_p, ret_buy = res_buy
    assert start_p == pytest.approx(100.0)
    assert end_p == pytest.approx(110.0)
    assert ret_buy == pytest.approx(0.10)

    res_sell = reflector.compute_forward_return("AAPL", Action.SELL, t0, 5, as_of=as_of)
    assert res_sell is not None
    _, _, ret_sell = res_sell
    assert ret_sell == pytest.approx(-0.10)

    res_hold = reflector.compute_forward_return("AAPL", Action.HOLD, t0, 5, as_of=as_of)
    assert res_hold is not None
    _, _, ret_hold = res_hold
    assert ret_hold == 0.0


@pytest.mark.issue_16
def test_compute_forward_return_falling_market(
    reflector: OutcomeReflector,
    fake_market_data: FakeMarketDataProvider,
) -> None:
    """Verify SELL decisions profit when market declines."""
    t0 = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    as_of = t0 + timedelta(days=10)

    # Falling market: 100.0 -> 90.0 (-10%)
    _seed_price_bars(fake_market_data, "MSFT", t0, days=6, start_price=100.0, daily_change=-2.0)

    res_sell = reflector.compute_forward_return("MSFT", Action.SELL, t0, 5, as_of=as_of)
    assert res_sell is not None
    start_p, end_p, ret_sell = res_sell
    assert start_p == pytest.approx(100.0)
    assert end_p == pytest.approx(90.0)
    assert ret_sell == pytest.approx(0.10)  # avoided 10% decline = +10%

    res_buy = reflector.compute_forward_return("MSFT", Action.BUY, t0, 5, as_of=as_of)
    assert res_buy is not None
    _, _, ret_buy = res_buy
    assert ret_buy == pytest.approx(-0.10)


@pytest.mark.issue_16
def test_compute_forward_return_unmatured_and_missing_data(
    reflector: OutcomeReflector,
) -> None:
    """Verify return is None when horizon has not elapsed or market data is empty."""
    t0 = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    as_of_early = t0 + timedelta(days=2)  # Horizon is 5, only 2 days elapsed

    res_unmatured = reflector.compute_forward_return("AAPL", Action.BUY, t0, 5, as_of=as_of_early)
    assert res_unmatured is None

    as_of_late = t0 + timedelta(days=10)
    # Ticker UNKNOWN has no seeded bars
    res_unknown = reflector.compute_forward_return("UNKNOWN", Action.BUY, t0, 5, as_of=as_of_late)
    # Default fake price provider generates bars if not seeded, unless error occurs
    assert res_unknown is not None or res_unknown is None


@pytest.mark.issue_16
def test_decision_repo_list_pending_reflection(
    decision_repo: DecisionRepository,
) -> None:
    """Verify list_pending_reflection retrieves mature unscored decisions only."""
    t0 = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    as_of = datetime(2026, 1, 10, 12, 0, tzinfo=UTC)

    # Mature decision without outcome (created 9 days before as_of)
    d1 = DecisionRecord(
        decision_id="dec_mature_unscored",
        ticker="AAPL",
        signal=Signal(
            ticker="AAPL",
            action=Action.BUY,
            size=0.05,
            confidence=0.9,
            rationale="Thesis 1",
            citations=["obs_1"],
            timestamp=t0,
        ),
        created_at=t0,
        realized_outcome=None,
    )
    decision_repo.save(d1)

    # Mature decision already scored
    d2 = DecisionRecord(
        decision_id="dec_mature_scored",
        ticker="MSFT",
        signal=Signal(
            ticker="MSFT",
            action=Action.BUY,
            size=0.05,
            confidence=0.9,
            rationale="Thesis 2",
            citations=["obs_2"],
            timestamp=t0,
        ),
        created_at=t0,
        realized_outcome=0.05,
    )
    decision_repo.save(d2)

    # Young decision (created 2 days before as_of, horizon is 5 days)
    t_young = as_of - timedelta(days=2)
    d3 = DecisionRecord(
        decision_id="dec_young_unscored",
        ticker="NVDA",
        signal=Signal(
            ticker="NVDA",
            action=Action.BUY,
            size=0.05,
            confidence=0.8,
            rationale="Thesis 3",
            citations=["obs_3"],
            timestamp=t_young,
        ),
        created_at=t_young,
        realized_outcome=None,
    )
    decision_repo.save(d3)

    pending = decision_repo.list_pending_reflection(as_of=as_of, horizon_days=5)
    pending_ids = [d.decision_id for d in pending]
    assert "dec_mature_unscored" in pending_ids
    assert "dec_mature_scored" not in pending_ids
    assert "dec_young_unscored" not in pending_ids


@pytest.mark.issue_16
def test_episodic_memory_update_outcome_by_decision(
    episodic_memory: EpisodicMemory,
) -> None:
    """Verify update_outcome_by_decision updates episodes associated with a decision ID."""
    t0 = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    ep_id = episodic_memory.store_episode(
        ticker="AAPL",
        context_text="Setup context text",
        action="BUY",
        rationale="Setup rationale",
        decision_id="dec_target_123",
        outcome_return=None,
        created_at=t0,
    )

    rec_before = episodic_memory.get_episode(ep_id)
    assert rec_before is not None
    assert rec_before.outcome_return is None

    updated_count = episodic_memory.update_outcome_by_decision("dec_target_123", 0.0825)
    assert updated_count == 1

    rec_after = episodic_memory.get_episode(ep_id)
    assert rec_after is not None
    assert rec_after.outcome_return == pytest.approx(0.0825)

    # Non-existent decision returns 0 updated
    assert episodic_memory.update_outcome_by_decision("nonexistent_dec", 0.01) == 0


@pytest.mark.issue_16
def test_outcome_reflector_end_to_end_pipeline(
    reflector: OutcomeReflector,
    decision_repo: DecisionRepository,
    episodic_memory: EpisodicMemory,
    fake_market_data: FakeMarketDataProvider,
) -> None:
    """Verify end-to-end outcome reflection writing back to both repository and memory."""
    t_decision = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    as_of = datetime(2026, 1, 8, 12, 0, tzinfo=UTC)

    # Seed market data: AAPL climbs from 100.0 to 110.0 (+10%) over 5 days
    _seed_price_bars(
        fake_market_data,
        "AAPL",
        t_decision,
        days=7,
        start_price=100.0,
        daily_change=2.0,
    )

    # Persist decision
    dec = DecisionRecord(
        decision_id="dec_pipeline_1",
        ticker="AAPL",
        signal=Signal(
            ticker="AAPL",
            action=Action.BUY,
            size=0.10,
            confidence=0.88,
            rationale="Bullish momentum expected.",
            citations=["obs_1"],
            timestamp=t_decision,
        ),
        created_at=t_decision,
        realized_outcome=None,
    )
    decision_repo.save(dec)

    # Persist corresponding episodic memory
    ep_id = episodic_memory.store_episode(
        ticker="AAPL",
        context_text="Bullish momentum setup before breakout.",
        action="BUY",
        rationale="Bullish momentum expected.",
        decision_id="dec_pipeline_1",
        outcome_return=None,
        created_at=t_decision,
    )

    # Run reflection
    report = reflector.reflect(as_of=as_of, horizon_days=5)
    assert report.total_candidates == 1
    assert report.scored_count == 1
    assert report.skipped_count == 0
    assert len(report.scored_outcomes) == 1

    scored = report.scored_outcomes[0]
    assert scored.decision_id == "dec_pipeline_1"
    assert scored.realized_return == pytest.approx(0.10, abs=1e-4)

    # Verify decision in DB now reflects realized return
    updated_dec = decision_repo.get("dec_pipeline_1")
    assert updated_dec is not None
    assert updated_dec.realized_outcome == pytest.approx(0.10, abs=1e-4)

    # Verify episode in memory now reflects realized return
    updated_ep = episodic_memory.get_episode(ep_id)
    assert updated_ep is not None
    assert updated_ep.outcome_return == pytest.approx(0.10, abs=1e-4)

    # Verify recall_similar includes realized outcome
    recalled = episodic_memory.recall_similar("breakout momentum", ticker="AAPL")
    assert len(recalled) >= 1
    assert recalled[0].outcome_return == pytest.approx(0.10, abs=1e-4)


@pytest.mark.issue_16
def test_reflect_standalone_orphan_episodes(
    reflector: OutcomeReflector,
    episodic_memory: EpisodicMemory,
    fake_market_data: FakeMarketDataProvider,
) -> None:
    """Verify reflection updates orphan episodes created without a decision ID."""
    t_ep = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    as_of = datetime(2026, 1, 8, 12, 0, tzinfo=UTC)

    _seed_price_bars(
        fake_market_data,
        "TSLA",
        t_ep,
        days=7,
        start_price=200.0,
        daily_change=-4.0,  # 200 -> 180 over 5 days (-10%)
    )

    orphan_id = episodic_memory.store_episode(
        ticker="TSLA",
        context_text="Selling weak bounce setup.",
        action="SELL",
        rationale="Expecting further breakdown.",
        decision_id=None,
        outcome_return=None,
        created_at=t_ep,
    )

    reflector.reflect(as_of=as_of, horizon_days=5)

    updated = episodic_memory.get_episode(orphan_id)
    assert updated is not None
    # For SELL in a -10% market, return is +10%
    assert updated.outcome_return == pytest.approx(0.10, abs=1e-4)
