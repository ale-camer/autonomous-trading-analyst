"""Decision records and execution reasoning trace endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from autonomous_trading_analyst.api.dependencies import get_decision_repo_dep
from autonomous_trading_analyst.domain.models import DecisionRecord
from autonomous_trading_analyst.persistence.repositories import DecisionRepository

router = APIRouter(tags=["Decisions"])


@router.get("/decisions", response_model=list[DecisionRecord])
def list_decisions(
    decision_repo: Annotated[DecisionRepository, Depends(get_decision_repo_dep)],
    limit: Annotated[
        int, Query(ge=1, le=200, description="Maximum number of decisions to return")
    ] = 50,
    ticker: Annotated[
        str | None, Query(description="Filter decisions by specific ticker symbol")
    ] = None,
) -> list[DecisionRecord]:
    """List historical trading decisions, ordered chronologically descending."""
    if ticker:
        return decision_repo.list_by_ticker(ticker=ticker, limit=limit)
    return decision_repo.list_recent(limit=limit)


@router.get("/decisions/{decision_id}", response_model=DecisionRecord)
def get_decision(
    decision_id: str,
    decision_repo: Annotated[DecisionRepository, Depends(get_decision_repo_dep)],
) -> DecisionRecord:
    """Retrieve a specific decision including its complete ReAct execution trace."""
    decision = decision_repo.get(decision_id=decision_id)
    if decision is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Decision '{decision_id}' not found",
        )
    return decision
