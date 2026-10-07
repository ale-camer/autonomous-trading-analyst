"""Domain models representing forward outcome scoring and reflection reports."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from autonomous_trading_analyst.domain.models import Action


class ScoredOutcome(BaseModel):
    """Realized outcome score for a historical trading decision over an evaluation horizon."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    decision_id: str
    ticker: str
    action: Action
    horizon_days: int
    start_price: float
    end_price: float
    realized_return: float
    evaluated_at: datetime


class ReflectionReport(BaseModel):
    """Summary report detailing the results of an outcome reflection run."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    total_candidates: int
    scored_count: int
    skipped_count: int
    scored_outcomes: list[ScoredOutcome] = Field(default_factory=list)
    executed_at: datetime
