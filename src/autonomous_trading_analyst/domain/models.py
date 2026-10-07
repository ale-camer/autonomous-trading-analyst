"""Core domain models for autonomous trading analyst."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Action(StrEnum):
    """Trading action proposed by the agent or executed in the portfolio."""

    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


class OrderStatus(StrEnum):
    """Lifecycle status of a trading order."""

    PENDING = "PENDING"
    APPROVED = "APPROVED"
    RESIZED = "RESIZED"
    REJECTED = "REJECTED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"


class Signal(BaseModel):
    """Signal produced by the ReAct agent for a given ticker."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    ticker: str
    action: Action
    size: float = Field(default=0.0, ge=0.0, le=1.0)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    rationale: str
    citations: list[str] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("ticker")
    @classmethod
    def validate_ticker(cls, v: str) -> str:
        clean = v.strip().upper()
        if not clean:
            msg = "Ticker symbol cannot be empty"
            raise ValueError(msg)
        return clean

    @model_validator(mode="after")
    def validate_citations_on_trade(self) -> "Signal":
        if self.action in (Action.BUY, Action.SELL) and self.size > 0.0 and not self.citations:
            msg = f"Trade signal ({self.action}) requires at least one observation citation"
            raise ValueError(msg)
        return self


class Order(BaseModel):
    """Order submitted to or evaluated by the risk manager and paper broker."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    order_id: str
    ticker: str
    action: Action
    shares: float = Field(gt=0.0)
    limit_price: float | None = Field(default=None, gt=0.0)
    status: OrderStatus = OrderStatus.PENDING
    reason: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("ticker")
    @classmethod
    def validate_ticker(cls, v: str) -> str:
        clean = v.strip().upper()
        if not clean:
            msg = "Ticker symbol cannot be empty"
            raise ValueError(msg)
        return clean


class Fill(BaseModel):
    """Execution record of an order filled by the paper broker."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    fill_id: str
    order_id: str
    ticker: str
    action: Action
    shares: float = Field(gt=0.0)
    price: float = Field(gt=0.0)
    commission: float = Field(default=0.0, ge=0.0)
    slippage: float = Field(default=0.0, ge=0.0)
    executed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class Position(BaseModel):
    """An open position in an asset held by the paper portfolio."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    ticker: str
    shares: float = Field(ge=0.0)
    average_entry_price: float = Field(ge=0.0)
    current_price: float = Field(ge=0.0)
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0

    @property
    def market_value(self) -> float:
        """Current market value of the held position."""
        return self.shares * self.current_price


class PortfolioState(BaseModel):
    """Snapshot of portfolio cash, positions, and aggregate exposure."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    cash: float = Field(ge=0.0)
    positions: dict[str, Position] = Field(default_factory=dict)
    total_equity: float = Field(ge=0.0)
    gross_exposure: float = Field(default=0.0, ge=0.0)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @classmethod
    def create(
        cls,
        cash: float,
        positions: dict[str, Position],
        updated_at: datetime | None = None,
    ) -> "PortfolioState":
        """Factory method computing total_equity and gross_exposure automatically."""
        market_val = sum(pos.market_value for pos in positions.values())
        equity = cash + market_val
        gross = (market_val / equity) if equity > 0 else 0.0
        return cls(
            cash=cash,
            positions=positions,
            total_equity=equity,
            gross_exposure=gross,
            updated_at=updated_at or datetime.now(UTC),
        )


class TraceStep(BaseModel):
    """A single step in the ReAct agent's reasoning loop."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    step_number: int = Field(ge=1)
    thought: str
    action_name: str | None = None
    action_args: dict[str, Any] = Field(default_factory=dict)
    observation_id: str | None = None
    observation: str | None = None
    tokens_used: int = Field(default=0, ge=0)
    cost_usd: float = Field(default=0.0, ge=0.0)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class DecisionRecord(BaseModel):
    """Complete record of an agent decision, including full trace and realized outcome."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    decision_id: str
    ticker: str
    signal: Signal
    trace: list[TraceStep] = Field(default_factory=list)
    total_cost_usd: float = Field(default=0.0, ge=0.0)
    total_tokens: int = Field(default=0, ge=0)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    realized_outcome: float | None = None
