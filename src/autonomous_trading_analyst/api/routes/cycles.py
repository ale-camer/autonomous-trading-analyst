"""Trading analysis cycle execution endpoint."""

from typing import Annotated

from fastapi import APIRouter, Body, Depends

from autonomous_trading_analyst.api.dependencies import get_orchestrator_dep
from autonomous_trading_analyst.api.schemas import CycleRequest
from autonomous_trading_analyst.cycle import AnalysisCycleOrchestrator
from autonomous_trading_analyst.domain.cycle import CycleSummary

router = APIRouter(tags=["Cycles"])


@router.post("/cycles", response_model=CycleSummary)
async def trigger_cycle(
    orchestrator: Annotated[AnalysisCycleOrchestrator, Depends(get_orchestrator_dep)],
    request: Annotated[CycleRequest | None, Body()] = None,
) -> CycleSummary:
    """Execute an end-to-end trading analysis cycle on demand."""
    watchlist = request.watchlist if request else None
    as_of = request.as_of if request else None
    return await orchestrator.run_cycle(watchlist=watchlist, as_of=as_of)
