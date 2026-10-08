"""Portfolio status and positions endpoint."""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends

from autonomous_trading_analyst.api.dependencies import (
    get_portfolio_repo_dep,
    get_settings_dep,
)
from autonomous_trading_analyst.config import Settings
from autonomous_trading_analyst.domain.models import PortfolioState
from autonomous_trading_analyst.persistence.repositories import PortfolioRepository

router = APIRouter(tags=["Portfolio"])


@router.get("/portfolio", response_model=PortfolioState)
def get_portfolio(
    portfolio_repo: Annotated[PortfolioRepository, Depends(get_portfolio_repo_dep)],
    settings: Annotated[Settings, Depends(get_settings_dep)],
) -> PortfolioState:
    """Retrieve the latest portfolio state, cash balance, and open positions."""
    latest = portfolio_repo.get_latest()
    if latest is not None:
        return latest

    # Return default initial state if no cycle snapshot has been persisted yet
    return PortfolioState.create(
        cash=settings.paper_initial_cash,
        positions={},
        updated_at=datetime.now(UTC),
    )
