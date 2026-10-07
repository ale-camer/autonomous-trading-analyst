"""Episodic memory abstractions, vector stores, and recall tools."""

from autonomous_trading_analyst.memory.embeddings import (
    EmbeddingClient,
    FakeEmbeddingClient,
    GeminiEmbeddingClient,
    OpenAIEmbeddingClient,
    get_embedding_client,
)
from autonomous_trading_analyst.memory.models import EpisodeModel, EpisodeRecord
from autonomous_trading_analyst.memory.reflection import OutcomeReflector
from autonomous_trading_analyst.memory.store import EpisodicMemory
from autonomous_trading_analyst.memory.tool import (
    RecallMemoryArgs,
    build_recall_memory_tool,
    register_recall_memory_tool,
)

__all__ = [
    "EmbeddingClient",
    "EpisodeModel",
    "EpisodeRecord",
    "EpisodicMemory",
    "FakeEmbeddingClient",
    "GeminiEmbeddingClient",
    "OpenAIEmbeddingClient",
    "OutcomeReflector",
    "RecallMemoryArgs",
    "build_recall_memory_tool",
    "get_embedding_client",
    "register_recall_memory_tool",
]
