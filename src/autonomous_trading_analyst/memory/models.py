"""SQLAlchemy ORM and domain models for vector episodic memory."""

from datetime import datetime

from pgvector.sqlalchemy import Vector
from pydantic import BaseModel, ConfigDict
from sqlalchemy import DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from autonomous_trading_analyst.persistence.models import Base


class EpisodeModel(Base):
    """Database record storing historical decision context, action, outcome, and embedding."""

    __tablename__ = "episodes"

    episode_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    decision_id: Mapped[str | None] = mapped_column(
        String(64),
        ForeignKey("decisions.decision_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    ticker: Mapped[str] = mapped_column(String(16), index=True, nullable=False)
    context_text: Mapped[str] = mapped_column(Text, nullable=False)
    action: Mapped[str] = mapped_column(String(16), nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    outcome_return: Mapped[float | None] = mapped_column(Float, nullable=True)
    embedding: Mapped[list[float]] = mapped_column(Vector(None), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), index=True, nullable=False
    )


class EpisodeRecord(BaseModel):
    """Immutable domain representation of a retrieved episodic memory record."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    episode_id: str
    ticker: str
    context_text: str
    action: str
    rationale: str
    decision_id: str | None = None
    outcome_return: float | None = None
    similarity_score: float | None = None
    created_at: datetime
