"""Episodic memory store providing vector persistence and similarity-based retrieval."""

import uuid
from datetime import UTC, datetime

import numpy as np
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from autonomous_trading_analyst.config import Settings, get_settings
from autonomous_trading_analyst.memory.embeddings import (
    EmbeddingClient,
    get_embedding_client,
)
from autonomous_trading_analyst.memory.models import EpisodeModel, EpisodeRecord
from autonomous_trading_analyst.persistence.db import get_db_session


class EpisodicMemory:
    """Store and semantic retrieval engine for historical trading episodes."""

    def __init__(
        self,
        session_factory: sessionmaker[Session],
        embedding_client: EmbeddingClient | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.session_factory = session_factory
        self.settings = settings if settings is not None else get_settings()
        self.embedding_client = (
            embedding_client
            if embedding_client is not None
            else get_embedding_client(self.settings)
        )

    def store_episode(
        self,
        ticker: str,
        context_text: str,
        action: str,
        rationale: str,
        decision_id: str | None = None,
        outcome_return: float | None = None,
        embedding: list[float] | None = None,
        created_at: datetime | None = None,
        episode_id: str | None = None,
    ) -> str:
        """Embed and persist a trading episode record, returning its unique episode ID."""
        clean_ticker = ticker.strip().upper()
        clean_action = action.strip().upper()
        now = created_at if created_at is not None else datetime.now(UTC)
        assigned_id = episode_id if episode_id is not None else str(uuid.uuid4())

        vector = (
            list(embedding)
            if embedding is not None
            else self.embedding_client.embed_query_sync(context_text)
        )

        model = EpisodeModel(
            episode_id=assigned_id,
            decision_id=decision_id,
            ticker=clean_ticker,
            context_text=context_text,
            action=clean_action,
            rationale=rationale,
            outcome_return=outcome_return,
            embedding=vector,
            created_at=now,
        )

        with get_db_session(self.session_factory) as session:
            session.add(model)

        return assigned_id

    async def astore_episode(
        self,
        ticker: str,
        context_text: str,
        action: str,
        rationale: str,
        decision_id: str | None = None,
        outcome_return: float | None = None,
        embedding: list[float] | None = None,
        created_at: datetime | None = None,
        episode_id: str | None = None,
    ) -> str:
        """Asynchronously embed and persist a trading episode record."""
        vector = (
            list(embedding)
            if embedding is not None
            else await self.embedding_client.embed_query(context_text)
        )
        return self.store_episode(
            ticker=ticker,
            context_text=context_text,
            action=action,
            rationale=rationale,
            decision_id=decision_id,
            outcome_return=outcome_return,
            embedding=vector,
            created_at=created_at,
            episode_id=episode_id,
        )

    def recall_similar(
        self,
        query: str,
        ticker: str | None = None,
        top_k: int | None = None,
    ) -> list[EpisodeRecord]:
        """Query episodic memory by semantic similarity with optional ticker filtering."""
        limit = top_k if top_k is not None else self.settings.memory_top_k
        query_vector = self.embedding_client.embed_query_sync(query)
        clean_ticker = ticker.strip().upper() if ticker else None

        with get_db_session(self.session_factory) as session:
            dialect_name = session.get_bind().dialect.name

            if dialect_name == "postgresql":
                distance_col = EpisodeModel.embedding.cosine_distance(query_vector).label(
                    "distance"
                )
                stmt = select(EpisodeModel, distance_col)
                if clean_ticker:
                    stmt = stmt.where(EpisodeModel.ticker == clean_ticker)
                stmt = stmt.order_by(distance_col.asc()).limit(limit)

                rows = session.execute(stmt).all()
                results: list[EpisodeRecord] = []
                for ep, dist in rows:
                    score = 1.0 - float(dist) if dist is not None else 0.0
                    results.append(
                        EpisodeRecord(
                            episode_id=ep.episode_id,
                            decision_id=ep.decision_id,
                            ticker=ep.ticker,
                            context_text=ep.context_text,
                            action=ep.action,
                            rationale=ep.rationale,
                            outcome_return=ep.outcome_return,
                            similarity_score=round(score, 4),
                            created_at=ep.created_at,
                        )
                    )
                return results

            # Dialect fallback (SQLite / test in-memory environments):
            stmt_fallback = select(EpisodeModel)
            if clean_ticker:
                stmt_fallback = stmt_fallback.where(EpisodeModel.ticker == clean_ticker)

            episodes = list(session.scalars(stmt_fallback).all())
            if not episodes:
                return []

            query_arr = np.asarray(query_vector, dtype=float)
            query_norm = float(np.linalg.norm(query_arr))

            scored: list[tuple[float, EpisodeModel]] = []
            for ep in episodes:
                ep_arr = np.asarray(ep.embedding, dtype=float)
                ep_norm = float(np.linalg.norm(ep_arr))
                if query_norm > 0 and ep_norm > 0:
                    sim = float(np.dot(query_arr, ep_arr) / (query_norm * ep_norm))
                else:
                    sim = 0.0
                scored.append((sim, ep))

            scored.sort(key=lambda item: item[0], reverse=True)
            top_episodes = scored[:limit]

            return [
                EpisodeRecord(
                    episode_id=ep.episode_id,
                    decision_id=ep.decision_id,
                    ticker=ep.ticker,
                    context_text=ep.context_text,
                    action=ep.action,
                    rationale=ep.rationale,
                    outcome_return=ep.outcome_return,
                    similarity_score=round(sim, 4),
                    created_at=ep.created_at,
                )
                for sim, ep in top_episodes
            ]

    async def arecall_similar(
        self,
        query: str,
        ticker: str | None = None,
        top_k: int | None = None,
    ) -> list[EpisodeRecord]:
        """Asynchronously query episodic memory by semantic similarity."""
        return self.recall_similar(query=query, ticker=ticker, top_k=top_k)

    def update_outcome(self, episode_id: str, outcome_return: float) -> None:
        """Update realized forward return outcome for an existing episode."""
        with get_db_session(self.session_factory) as session:
            ep = session.get(EpisodeModel, episode_id)
            if ep is None:
                msg = f"Episode with id '{episode_id}' not found."
                raise ValueError(msg)
            ep.outcome_return = float(outcome_return)

    def get_episode(self, episode_id: str) -> EpisodeRecord | None:
        """Retrieve a single episode record by ID."""
        with get_db_session(self.session_factory) as session:
            ep = session.get(EpisodeModel, episode_id)
            if ep is None:
                return None
            return EpisodeRecord(
                episode_id=ep.episode_id,
                decision_id=ep.decision_id,
                ticker=ep.ticker,
                context_text=ep.context_text,
                action=ep.action,
                rationale=ep.rationale,
                outcome_return=ep.outcome_return,
                created_at=ep.created_at,
            )

    def count(self, ticker: str | None = None) -> int:
        """Count total stored episodes, optionally filtered by ticker."""
        clean_ticker = ticker.strip().upper() if ticker else None
        with get_db_session(self.session_factory) as session:
            stmt = select(func.count(EpisodeModel.episode_id))
            if clean_ticker:
                stmt = stmt.where(EpisodeModel.ticker == clean_ticker)
            return int(session.scalar(stmt) or 0)
