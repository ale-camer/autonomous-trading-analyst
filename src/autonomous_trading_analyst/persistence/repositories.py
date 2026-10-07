"""Type-safe repository layer mapping domain entities to relational database models."""

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, sessionmaker

from autonomous_trading_analyst.domain.models import (
    Action,
    DecisionRecord,
    Fill,
    Order,
    OrderStatus,
    PortfolioState,
    Position,
    Signal,
    TraceStep,
)
from autonomous_trading_analyst.persistence.db import get_db_session
from autonomous_trading_analyst.persistence.models import (
    DecisionModel,
    FillModel,
    OrderModel,
    PortfolioSnapshotModel,
    TraceStepModel,
)


class DecisionRepository:
    """Repository managing persistence and retrieval of agent decisions and reasoning traces."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self.session_factory = session_factory

    def save(self, decision: DecisionRecord) -> None:
        """Persist a complete DecisionRecord and all associated trace steps."""
        with get_db_session(self.session_factory) as session:
            # Check if decision already exists to handle updates cleanly
            existing = session.get(DecisionModel, decision.decision_id)
            if existing:
                existing.ticker = decision.ticker
                existing.action = decision.signal.action.value
                existing.size = decision.signal.size
                existing.confidence = decision.signal.confidence
                existing.rationale = decision.signal.rationale
                existing.citations = list(decision.signal.citations)
                existing.signal_timestamp = decision.signal.timestamp
                existing.total_cost_usd = decision.total_cost_usd
                existing.total_tokens = decision.total_tokens
                existing.realized_outcome = decision.realized_outcome
                existing.created_at = decision.created_at

                existing.trace_steps.clear()
                for step in decision.trace:
                    existing.trace_steps.append(
                        TraceStepModel(
                            decision_id=decision.decision_id,
                            step_number=step.step_number,
                            thought=step.thought,
                            action_name=step.action_name,
                            action_args=dict(step.action_args),
                            observation_id=step.observation_id,
                            observation=step.observation,
                            tokens_used=step.tokens_used,
                            cost_usd=step.cost_usd,
                            timestamp=step.timestamp,
                        )
                    )
            else:
                model = DecisionModel(
                    decision_id=decision.decision_id,
                    ticker=decision.ticker,
                    action=decision.signal.action.value,
                    size=decision.signal.size,
                    confidence=decision.signal.confidence,
                    rationale=decision.signal.rationale,
                    citations=list(decision.signal.citations),
                    signal_timestamp=decision.signal.timestamp,
                    total_cost_usd=decision.total_cost_usd,
                    total_tokens=decision.total_tokens,
                    realized_outcome=decision.realized_outcome,
                    created_at=decision.created_at,
                    trace_steps=[
                        TraceStepModel(
                            step_number=step.step_number,
                            thought=step.thought,
                            action_name=step.action_name,
                            action_args=dict(step.action_args),
                            observation_id=step.observation_id,
                            observation=step.observation,
                            tokens_used=step.tokens_used,
                            cost_usd=step.cost_usd,
                            timestamp=step.timestamp,
                        )
                        for step in decision.trace
                    ],
                )
                session.add(model)

    def get(self, decision_id: str) -> DecisionRecord | None:
        """Fetch a DecisionRecord by ID with all trace steps loaded."""
        with get_db_session(self.session_factory) as session:
            stmt = (
                select(DecisionModel)
                .options(joinedload(DecisionModel.trace_steps))
                .where(DecisionModel.decision_id == decision_id)
            )
            model = session.scalars(stmt).unique().first()
            if not model:
                return None
            return self._to_domain(model)

    def list_recent(self, limit: int = 50) -> list[DecisionRecord]:
        """Return the most recent decisions ordered by creation timestamp."""
        with get_db_session(self.session_factory) as session:
            stmt = (
                select(DecisionModel)
                .options(joinedload(DecisionModel.trace_steps))
                .order_by(DecisionModel.created_at.desc())
                .limit(limit)
            )
            models = session.scalars(stmt).unique().all()
            return [self._to_domain(m) for m in models]

    def list_by_ticker(self, ticker: str, limit: int = 50) -> list[DecisionRecord]:
        """Return decisions for a specific ticker symbol."""
        clean_ticker = ticker.strip().upper()
        with get_db_session(self.session_factory) as session:
            stmt = (
                select(DecisionModel)
                .options(joinedload(DecisionModel.trace_steps))
                .where(DecisionModel.ticker == clean_ticker)
                .order_by(DecisionModel.created_at.desc())
                .limit(limit)
            )
            models = session.scalars(stmt).unique().all()
            return [self._to_domain(m) for m in models]

    def update_outcome(self, decision_id: str, realized_outcome: float) -> None:
        """Update the realized outcome for an existing decision."""
        with get_db_session(self.session_factory) as session:
            model = session.get(DecisionModel, decision_id)
            if model:
                model.realized_outcome = realized_outcome

    @staticmethod
    def _to_domain(model: DecisionModel) -> DecisionRecord:
        signal = Signal(
            ticker=model.ticker,
            action=Action(model.action),
            size=model.size,
            confidence=model.confidence,
            rationale=model.rationale,
            citations=list(model.citations),
            timestamp=model.signal_timestamp,
        )
        trace = [
            TraceStep(
                step_number=step.step_number,
                thought=step.thought,
                action_name=step.action_name,
                action_args=dict(step.action_args),
                observation_id=step.observation_id,
                observation=step.observation,
                tokens_used=step.tokens_used,
                cost_usd=step.cost_usd,
                timestamp=step.timestamp,
            )
            for step in model.trace_steps
        ]
        return DecisionRecord(
            decision_id=model.decision_id,
            ticker=model.ticker,
            signal=signal,
            trace=trace,
            total_cost_usd=model.total_cost_usd,
            total_tokens=model.total_tokens,
            created_at=model.created_at,
            realized_outcome=model.realized_outcome,
        )


class OrderRepository:
    """Repository managing persistence and retrieval of trading orders."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self.session_factory = session_factory

    def save(self, order: Order, decision_id: str | None = None) -> None:
        """Persist or update an Order record."""
        with get_db_session(self.session_factory) as session:
            existing = session.get(OrderModel, order.order_id)
            if existing:
                existing.ticker = order.ticker
                existing.action = order.action.value
                existing.shares = order.shares
                existing.limit_price = order.limit_price
                existing.status = order.status.value
                existing.reason = order.reason
                existing.created_at = order.created_at
                if decision_id is not None:
                    existing.decision_id = decision_id
            else:
                model = OrderModel(
                    order_id=order.order_id,
                    decision_id=decision_id,
                    ticker=order.ticker,
                    action=order.action.value,
                    shares=order.shares,
                    limit_price=order.limit_price,
                    status=order.status.value,
                    reason=order.reason,
                    created_at=order.created_at,
                )
                session.add(model)

    def get(self, order_id: str) -> Order | None:
        """Fetch an Order by ID."""
        with get_db_session(self.session_factory) as session:
            model = session.get(OrderModel, order_id)
            return self._to_domain(model) if model else None

    def update_status(
        self,
        order_id: str,
        status: OrderStatus,
        reason: str | None = None,
    ) -> None:
        """Update the lifecycle status and optional reason of an order."""
        with get_db_session(self.session_factory) as session:
            model = session.get(OrderModel, order_id)
            if model:
                model.status = status.value
                if reason is not None:
                    model.reason = reason

    def list_by_ticker(self, ticker: str, limit: int = 50) -> list[Order]:
        """Return orders for a given ticker symbol."""
        clean_ticker = ticker.strip().upper()
        with get_db_session(self.session_factory) as session:
            stmt = (
                select(OrderModel)
                .where(OrderModel.ticker == clean_ticker)
                .order_by(OrderModel.created_at.desc())
                .limit(limit)
            )
            models = session.scalars(stmt).all()
            return [self._to_domain(m) for m in models]

    def list_recent(self, limit: int = 50) -> list[Order]:
        """Return the most recent orders."""
        with get_db_session(self.session_factory) as session:
            stmt = select(OrderModel).order_by(OrderModel.created_at.desc()).limit(limit)
            models = session.scalars(stmt).all()
            return [self._to_domain(m) for m in models]

    @staticmethod
    def _to_domain(model: OrderModel) -> Order:
        return Order(
            order_id=model.order_id,
            ticker=model.ticker,
            action=Action(model.action),
            shares=model.shares,
            limit_price=model.limit_price,
            status=OrderStatus(model.status),
            reason=model.reason,
            created_at=model.created_at,
        )


class FillRepository:
    """Repository managing audit records of executed trade fills."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self.session_factory = session_factory

    def save(self, fill: Fill) -> None:
        """Persist a trade Fill execution record."""
        with get_db_session(self.session_factory) as session:
            existing = session.get(FillModel, fill.fill_id)
            if not existing:
                model = FillModel(
                    fill_id=fill.fill_id,
                    order_id=fill.order_id,
                    ticker=fill.ticker,
                    action=fill.action.value,
                    shares=fill.shares,
                    price=fill.price,
                    commission=fill.commission,
                    slippage=fill.slippage,
                    executed_at=fill.executed_at,
                )
                session.add(model)

    def get(self, fill_id: str) -> Fill | None:
        """Fetch a Fill by ID."""
        with get_db_session(self.session_factory) as session:
            model = session.get(FillModel, fill_id)
            return self._to_domain(model) if model else None

    def list_by_order(self, order_id: str) -> list[Fill]:
        """Return fills corresponding to a specific order ID."""
        with get_db_session(self.session_factory) as session:
            stmt = (
                select(FillModel)
                .where(FillModel.order_id == order_id)
                .order_by(FillModel.executed_at.asc())
            )
            models = session.scalars(stmt).all()
            return [self._to_domain(m) for m in models]

    def list_by_ticker(self, ticker: str, limit: int = 50) -> list[Fill]:
        """Return fills corresponding to a specific ticker symbol."""
        clean_ticker = ticker.strip().upper()
        with get_db_session(self.session_factory) as session:
            stmt = (
                select(FillModel)
                .where(FillModel.ticker == clean_ticker)
                .order_by(FillModel.executed_at.asc())
                .limit(limit)
            )
            models = session.scalars(stmt).all()
            return [self._to_domain(m) for m in models]

    def list_recent(self, limit: int = 50) -> list[Fill]:
        """Return the most recent fills."""
        with get_db_session(self.session_factory) as session:
            stmt = select(FillModel).order_by(FillModel.executed_at.desc()).limit(limit)
            models = session.scalars(stmt).all()
            return [self._to_domain(m) for m in models]

    @staticmethod
    def _to_domain(model: FillModel) -> Fill:
        return Fill(
            fill_id=model.fill_id,
            order_id=model.order_id,
            ticker=model.ticker,
            action=Action(model.action),
            shares=model.shares,
            price=model.price,
            commission=model.commission,
            slippage=model.slippage,
            executed_at=model.executed_at,
        )


class PortfolioRepository:
    """Repository managing periodic historical snapshots of portfolio state."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self.session_factory = session_factory

    def save(self, state: PortfolioState, snapshot_id: str | None = None) -> str:
        """Persist a PortfolioState snapshot and return its generated snapshot ID."""
        sid = snapshot_id or f"snap_{uuid.uuid4().hex[:8]}"
        serialized_positions: dict[str, Any] = {
            ticker: pos.model_dump(mode="json") for ticker, pos in state.positions.items()
        }

        with get_db_session(self.session_factory) as session:
            model = PortfolioSnapshotModel(
                snapshot_id=sid,
                cash=state.cash,
                positions=serialized_positions,
                total_equity=state.total_equity,
                gross_exposure=state.gross_exposure,
                created_at=state.updated_at,
            )
            session.add(model)

        return sid

    def get_latest(self) -> PortfolioState | None:
        """Return the most recent PortfolioState snapshot."""
        with get_db_session(self.session_factory) as session:
            stmt = (
                select(PortfolioSnapshotModel)
                .order_by(PortfolioSnapshotModel.created_at.desc())
                .limit(1)
            )
            model = session.scalars(stmt).first()
            return self._to_domain(model) if model else None

    def list_history(self, limit: int = 100) -> list[PortfolioState]:
        """Return chronological history of portfolio snapshots."""
        with get_db_session(self.session_factory) as session:
            stmt = (
                select(PortfolioSnapshotModel)
                .order_by(PortfolioSnapshotModel.created_at.asc())
                .limit(limit)
            )
            models = session.scalars(stmt).all()
            return [self._to_domain(m) for m in models]

    @staticmethod
    def _to_domain(model: PortfolioSnapshotModel) -> PortfolioState:
        positions: dict[str, Position] = {
            ticker: Position.model_validate(pos_data)
            for ticker, pos_data in model.positions.items()
        }
        return PortfolioState.create(
            cash=model.cash,
            positions=positions,
            updated_at=model.created_at,
        )
