"""SQLAlchemy 2.0 ORM models for trading decisions, traces, orders, and portfolio state."""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base declarative class for all persistence models."""


class DecisionModel(Base):
    """Database record for agent decision and trading thesis."""

    __tablename__ = "decisions"

    decision_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    ticker: Mapped[str] = mapped_column(String(16), index=True, nullable=False)
    action: Mapped[str] = mapped_column(String(16), nullable=False)
    size: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    rationale: Mapped[str] = mapped_column(String, nullable=False)
    citations: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    signal_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    total_cost_usd: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    realized_outcome: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), index=True, nullable=False
    )

    trace_steps: Mapped[list["TraceStepModel"]] = relationship(
        "TraceStepModel",
        back_populates="decision",
        cascade="all, delete-orphan",
        order_by="TraceStepModel.step_number",
    )


class TraceStepModel(Base):
    """Database record for an individual ReAct reasoning/action step within a decision."""

    __tablename__ = "trace_steps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    decision_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("decisions.decision_id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    step_number: Mapped[int] = mapped_column(Integer, nullable=False)
    thought: Mapped[str] = mapped_column(String, nullable=False)
    action_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    action_args: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    observation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    observation: Mapped[str | None] = mapped_column(String, nullable=True)
    tokens_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    decision: Mapped["DecisionModel"] = relationship("DecisionModel", back_populates="trace_steps")


class OrderModel(Base):
    """Database record for orders evaluated by risk manager and submitted to broker."""

    __tablename__ = "orders"

    order_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    decision_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    ticker: Mapped[str] = mapped_column(String(16), index=True, nullable=False)
    action: Mapped[str] = mapped_column(String(16), nullable=False)
    shares: Mapped[float] = mapped_column(Float, nullable=False)
    limit_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    reason: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), index=True, nullable=False
    )

    fills: Mapped[list["FillModel"]] = relationship(
        "FillModel",
        back_populates="order",
        cascade="all, delete-orphan",
    )


class FillModel(Base):
    """Database record for executed trade fills from paper broker."""

    __tablename__ = "fills"

    fill_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    order_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("orders.order_id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    ticker: Mapped[str] = mapped_column(String(16), index=True, nullable=False)
    action: Mapped[str] = mapped_column(String(16), nullable=False)
    shares: Mapped[float] = mapped_column(Float, nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    commission: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    slippage: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    executed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), index=True, nullable=False
    )

    order: Mapped["OrderModel"] = relationship("OrderModel", back_populates="fills")


class PortfolioSnapshotModel(Base):
    """Database record for periodic snapshots of cash, positions, equity, and exposure."""

    __tablename__ = "portfolio_snapshots"

    snapshot_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    cash: Mapped[float] = mapped_column(Float, nullable=False)
    positions: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    total_equity: Mapped[float] = mapped_column(Float, nullable=False)
    gross_exposure: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), index=True, nullable=False
    )
