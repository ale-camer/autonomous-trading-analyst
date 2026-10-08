"""FastAPI dependency providers for settings, persistence, and cycle orchestration."""

from typing import Annotated

from fastapi import Depends
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from autonomous_trading_analyst.config import Settings, get_settings
from autonomous_trading_analyst.cycle import (
    AnalysisCycleOrchestrator,
    create_analysis_cycle,
)
from autonomous_trading_analyst.persistence.db import (
    create_db_engine,
    get_session_factory,
    init_db,
)
from autonomous_trading_analyst.persistence.repositories import (
    DecisionRepository,
    PortfolioRepository,
)

_engine_instance: Engine | None = None
_session_factory_instance: sessionmaker[Session] | None = None


def get_settings_dep() -> Settings:
    """Dependency provider returning application Settings."""
    return get_settings()


def get_session_factory_dep(
    settings: Annotated[Settings, Depends(get_settings_dep)],
) -> sessionmaker[Session]:
    """Dependency provider returning thread-safe SQLAlchemy sessionmaker."""
    global _engine_instance, _session_factory_instance
    if _session_factory_instance is None:
        _engine_instance = create_db_engine(settings.database_url)
        init_db(_engine_instance)
        _session_factory_instance = get_session_factory(_engine_instance)
    return _session_factory_instance


def get_decision_repo_dep(
    session_factory: Annotated[sessionmaker[Session], Depends(get_session_factory_dep)],
) -> DecisionRepository:
    """Dependency provider returning DecisionRepository."""
    return DecisionRepository(session_factory)


def get_portfolio_repo_dep(
    session_factory: Annotated[sessionmaker[Session], Depends(get_session_factory_dep)],
) -> PortfolioRepository:
    """Dependency provider returning PortfolioRepository."""
    return PortfolioRepository(session_factory)


def get_orchestrator_dep(
    session_factory: Annotated[sessionmaker[Session], Depends(get_session_factory_dep)],
    settings: Annotated[Settings, Depends(get_settings_dep)],
) -> AnalysisCycleOrchestrator:
    """Dependency provider returning fully wired AnalysisCycleOrchestrator."""
    return create_analysis_cycle(
        session_factory=session_factory,
        settings=settings,
    )
