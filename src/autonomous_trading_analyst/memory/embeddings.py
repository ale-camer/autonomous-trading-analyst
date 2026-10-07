"""Embedding client abstractions and provider implementations."""

import hashlib
from typing import Protocol

import numpy as np

from autonomous_trading_analyst.config import Settings, get_settings


class EmbeddingClient(Protocol):
    """Protocol defining the provider-agnostic interface for text embeddings."""

    async def embed_query(self, text: str) -> list[float]:
        """Generate vector embedding for a single search query."""
        ...

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Generate vector embeddings for multiple documents."""
        ...

    def embed_query_sync(self, text: str) -> list[float]:
        """Synchronously generate vector embedding for a query."""
        ...


class FakeEmbeddingClient(EmbeddingClient):
    """Deterministic, normalized fake embedding client for testing and offline execution."""

    def __init__(
        self,
        dim: int = 1536,
        fixed_embeddings: dict[str, list[float]] | None = None,
    ) -> None:
        self.dim = dim
        self.fixed_embeddings = dict(fixed_embeddings) if fixed_embeddings else {}

    def _generate(self, text: str) -> list[float]:
        if text in self.fixed_embeddings:
            return list(self.fixed_embeddings[text])

        seed = int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:8], 16)
        rng = np.random.default_rng(seed)
        vec = rng.standard_normal(self.dim)
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        return [float(x) for x in vec]

    async def embed_query(self, text: str) -> list[float]:
        return self._generate(text)

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._generate(t) for t in texts]

    def embed_query_sync(self, text: str) -> list[float]:
        return self._generate(text)


class OpenAIEmbeddingClient(EmbeddingClient):
    """OpenAI API implementation of EmbeddingClient."""

    def __init__(
        self,
        api_key: str,
        model: str = "text-embedding-3-small",
        dim: int = 1536,
    ) -> None:
        from openai import AsyncOpenAI, OpenAI

        self.model = model
        self.dim = dim
        self._async_client = AsyncOpenAI(api_key=api_key)
        self._sync_client = OpenAI(api_key=api_key)

    async def embed_query(self, text: str) -> list[float]:
        response = await self._async_client.embeddings.create(input=text, model=self.model)
        return list(response.data[0].embedding)

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        response = await self._async_client.embeddings.create(input=texts, model=self.model)
        return [list(item.embedding) for item in response.data]

    def embed_query_sync(self, text: str) -> list[float]:
        response = self._sync_client.embeddings.create(input=text, model=self.model)
        return list(response.data[0].embedding)


class GeminiEmbeddingClient(EmbeddingClient):
    """Google Gemini API implementation of EmbeddingClient."""

    def __init__(
        self,
        api_key: str,
        model: str = "text-embedding-004",
        dim: int = 768,
    ) -> None:
        from google import genai

        self.model = model
        self.dim = dim
        self._client = genai.Client(api_key=api_key)

    async def embed_query(self, text: str) -> list[float]:
        response = await self._client.aio.models.embed_content(
            model=self.model,
            contents=text,
        )
        if response.embeddings and response.embeddings[0].values:
            return [float(v) for v in response.embeddings[0].values]
        return [0.0] * self.dim

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        results: list[list[float]] = []
        for text in texts:
            vec = await self.embed_query(text)
            results.append(vec)
        return results

    def embed_query_sync(self, text: str) -> list[float]:
        response = self._client.models.embed_content(
            model=self.model,
            contents=text,
        )
        if response.embeddings and response.embeddings[0].values:
            return [float(v) for v in response.embeddings[0].values]
        return [0.0] * self.dim


def get_embedding_client(settings: Settings | None = None) -> EmbeddingClient:
    """Factory returning configured EmbeddingClient based on application settings."""
    cfg = settings if settings is not None else get_settings()

    if cfg.embedding_provider == "fake":
        return FakeEmbeddingClient(dim=cfg.embedding_dim)

    if cfg.embedding_provider == "openai":
        api_key = cfg.openai_api_key.get_secret_value() if cfg.openai_api_key else ""
        return OpenAIEmbeddingClient(
            api_key=api_key,
            model=cfg.embedding_model,
            dim=cfg.embedding_dim,
        )

    if cfg.embedding_provider == "gemini":
        api_key = cfg.google_api_key.get_secret_value() if cfg.google_api_key else ""
        return GeminiEmbeddingClient(
            api_key=api_key,
            model=cfg.embedding_model,
            dim=cfg.embedding_dim,
        )

    msg = f"Unknown embedding provider: {cfg.embedding_provider}"
    raise ValueError(msg)
