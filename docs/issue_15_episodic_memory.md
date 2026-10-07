# Issue 15: Episodic Memory with pgvector

**Branch**: `feature/issue-15-episodic-memory`
**Status**: Done
**PR**: opened by `make finish-issue` → `develop` (Closes #15)
**Milestone**: M3 - Risk, Paper Trading & Memory

## Objective
Implement vector-based episodic memory using `pgvector` and an embedding abstraction (`EmbeddingClient`). The episodic memory stores past market decisions, context, and their realized outcomes as vector embeddings. Implement similarity-based retrieval allowing the agent to recall similar historical trade setups during its ReAct loop via a dedicated `recall_memory` tool.

## Acceptance Criteria
- [x] `src/autonomous_trading_analyst/memory/embeddings.py` defines the `EmbeddingClient` protocol and implementations (`FakeEmbeddingClient`, `OpenAIEmbeddingClient`, `GeminiEmbeddingClient`) with factory `get_embedding_client`.
- [x] `src/autonomous_trading_analyst/memory/models.py` defines `EpisodeModel` with `pgvector.sqlalchemy.Vector` embedding column, storing ticker, context, action, rationale, outcome return, and timestamp.
- [x] `src/autonomous_trading_analyst/memory/store.py` implements `EpisodicMemory` providing `store_episode`, `recall_similar` (with PostgreSQL pgvector cosine distance and SQLite in-memory fallback), and `update_outcome`.
- [x] `src/autonomous_trading_analyst/memory/tool.py` implements the `recall_memory` tool for the agent, accepting search query, optional ticker filter, and top-k count.
- [x] `src/autonomous_trading_analyst/memory/__init__.py` re-exports the embedding clients, models, memory store, and tool factory.
- [x] `tests/unit/test_episodic_memory.py` tests embedding generation, episode persistence, similarity retrieval, and tool execution (marked `@pytest.mark.issue_15`).
- [x] `pyproject.toml` registers the `issue_15` marker.
- [x] `make check` and `make test-issue ID=15` pass.

## Implementation Tasks

### 1. Preparation & Branching
```bash
make start-issue ID=15 NAME=episodic-memory
```

### 2. Embedding Client Abstraction & Providers
- **File**: `src/autonomous_trading_analyst/memory/embeddings.py`
- **Change**: Define:
  - `EmbeddingClient(Protocol)` with `embed_query(text: str) -> list[float]` and `embed_documents(texts: list[str]) -> list[list[float]]`.
  - `FakeEmbeddingClient`: generates deterministic normalized embeddings of configurable dimension (`embedding_dim` from `Settings`).
  - `OpenAIEmbeddingClient`: integrates `openai.AsyncOpenAI` embeddings API (`text-embedding-3-small`).
  - `GeminiEmbeddingClient`: integrates Google GenAI embeddings API.
  - `get_embedding_client(settings: Settings | None = None) -> EmbeddingClient`: factory dispatching based on `settings.embedding_provider`.

### 3. Episodic Memory ORM Model
- **File**: `src/autonomous_trading_analyst/memory/models.py`
- **Change**: Define `EpisodeModel(Base)`:
  - `episode_id` (PK, str)
  - `decision_id` (nullable FK to decisions, str)
  - `ticker` (indexed, str)
  - `context_text` (str, the embedded text)
  - `action` (str: BUY, SELL, HOLD)
  - `rationale` (str)
  - `outcome_return` (nullable float, forward return populated later by reflection)
  - `embedding` (`Mapped[list[float]] = mapped_column(Vector(settings.embedding_dim))`)
  - `created_at` (datetime timezone-aware)

### 4. Episodic Memory Store & Retrieval
- **File**: `src/autonomous_trading_analyst/memory/store.py`
- **Change**: Implement `EpisodicMemory`:
  - `store_episode(...) -> str`: embeds context text, persists `EpisodeModel`, returns `episode_id`.
  - `recall_similar(query: str, ticker: str | None = None, top_k: int | None = None) -> list[EpisodeRecord]`:
    - Generates query embedding.
    - Queries episodes: uses pgvector cosine distance on PostgreSQL; falls back to numpy cosine similarity on SQLite.
    - Filters by ticker if provided. Returns top matches up to `settings.memory_top_k`.
  - `update_outcome(episode_id: str, outcome_return: float) -> None`: updates outcome return for an existing episode.

### 5. Agent Tool: `recall_memory`
- **File**: `src/autonomous_trading_analyst/memory/tool.py`
- **Change**: Implement `build_recall_memory_tool(memory: EpisodicMemory)` returning a registered tool handler with `RecallMemoryArgs(BaseModel)`:
  - Queries episodic memory for past setups matching current market conditions.
  - Formats results into structured text detailing past decisions, rationales, and realized return outcomes.

### 6. Memory Package Interface
- **File**: `src/autonomous_trading_analyst/memory/__init__.py`
- **Change**: Re-export `EmbeddingClient`, `FakeEmbeddingClient`, `OpenAIEmbeddingClient`, `GeminiEmbeddingClient`, `get_embedding_client`, `EpisodicMemory`, `EpisodeModel`, and `build_recall_memory_tool`.

### 7. Unit Tests
- **File**: `tests/unit/test_episodic_memory.py`
- **Change**: Write unit tests covering:
  - Embedding clients (fake generation, dimensionality, factory creation).
  - Storing episodes and embedding verification.
  - Similarity retrieval with ranking and ticker filtering.
  - Outcome return updating.
  - `recall_memory` tool invocation and output formatting.
  Mark tests with `@pytest.mark.issue_15`.

### 8. Pytest Marker Registration
- **File**: `pyproject.toml`
- **Change**: Add the `issue_15: Episodic memory with pgvector` marker under `[tool.pytest.ini_options]` `markers`.

### 9. Verification & Quality Gates
```bash
make test-issue ID=15
make check
```

### 10. Git & Issue Finish
```bash
make finish-issue ID=15 MSG="feat(memory): implement pgvector episodic memory and recall tool"
```

## Decisions
- Storing decision context as vector embeddings enables semantic retrieval: the agent can query "high inflation with declining earnings" or "oversold momentum bounce" and find past setups with their realized outcomes.
- Providing dual backend support (native pgvector in PostgreSQL and in-memory numpy cosine similarity in SQLite) allows testing episodic memory fast and offline without spinning up a Postgres container.
- Exposing episodic memory through a standard tool (`recall_memory`) integrates naturally into the ReAct loop without altering core prompt architecture.
