"""Domain models representing analysis cycle execution summaries."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from autonomous_trading_analyst.domain.models import (
    DecisionRecord,
    Fill,
    Order,
    PortfolioState,
)


class CycleSummary(BaseModel):
    """Immutable summary record of an end-to-end analysis cycle run."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    cycle_id: str
    timestamp: datetime
    watchlist: list[str]
    decisions: list[DecisionRecord] = Field(default_factory=list)
    orders: list[Order] = Field(default_factory=list)
    fills: list[Fill] = Field(default_factory=list)
    stop_loss_orders: list[Order] = Field(default_factory=list)
    portfolio_state: PortfolioState
    total_cost_usd: float = Field(default=0.0, ge=0.0)
    total_tokens: int = Field(default=0, ge=0)
    errors: dict[str, str] = Field(default_factory=dict)
