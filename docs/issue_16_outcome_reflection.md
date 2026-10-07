# Issue 16: Outcome Reflection

**Branch**: `feature/issue-16-outcome-reflection`
**Status**: Done
**PR**: opened by `make finish-issue` → `develop` (Closes #16)
**Milestone**: M3 - Risk, Paper Trading & Memory

## Objective
Implement an outcome reflection pipeline (`OutcomeReflector`) that evaluates past trading decisions over a configurable forward return horizon using historical market data. The system computes realized price returns, updates decision records in the relational database, and persists the outcomes into episodic memory so subsequent similarity recall operations inform the agent of empirical performance.

## Acceptance Criteria
- [x] `src/autonomous_trading_analyst/domain/reflection.py` defines domain models `ScoredOutcome` and `ReflectionReport`.
- [x] `src/autonomous_trading_analyst/config.py` defines reflection configuration settings (`reflection_horizon_days`, `reflection_batch_size`).
- [x] `src/autonomous_trading_analyst/persistence/repositories.py` extends `DecisionRepository` with `list_pending_reflection` to retrieve mature unscored decisions.
- [x] `src/autonomous_trading_analyst/memory/store.py` extends `EpisodicMemory` with `update_outcome_by_decision` to link and update episode outcomes by decision ID.
- [x] `src/autonomous_trading_analyst/memory/reflection.py` implements `OutcomeReflector` with `compute_forward_return` and `reflect` orchestration.
- [x] `src/autonomous_trading_analyst/memory/__init__.py` and `domain/__init__.py` re-export reflection domain and engine abstractions.
- [x] `tests/unit/test_reflection.py` covers forward return calculations (BUY/SELL/HOLD), horizon maturity filtering, missing data handling, and batch database/memory updates (marked `@pytest.mark.issue_16`).
- [x] `pyproject.toml` registers the `issue_16` marker.
- [x] `make check` and `make test-issue ID=16` pass.

## Implementation Tasks

### 1. Preparation & Branching
```bash
make start-issue ID=16 NAME=outcome-reflection
```

### 2. Reflection Domain Models
- **File**: `src/autonomous_trading_analyst/domain/reflection.py`
- **Change**: Define typed Pydantic models:
  - `ScoredOutcome`: `decision_id: str`, `ticker: str`, `action: Action`, `horizon_days: int`, `start_price: float`, `end_price: float`, `realized_return: float`, `evaluated_at: datetime`.
  - `ReflectionReport`: `total_candidates: int`, `scored_count: int`, `skipped_count: int`, `scored_outcomes: list[ScoredOutcome]`, `executed_at: datetime`.

### 3. Application Settings for Reflection
- **File**: `src/autonomous_trading_analyst/config.py`
- **Change**: Add `reflection_horizon_days: int = Field(default=5, ge=1)` and `reflection_batch_size: int = Field(default=50, ge=1)` to `Settings`.

### 4. Decision Repository Pending Queries
- **File**: `src/autonomous_trading_analyst/persistence/repositories.py`
- **Change**: Add `list_pending_reflection(as_of: datetime | None = None, horizon_days: int = 5, limit: int = 50) -> list[DecisionRecord]` to `DecisionRepository`, querying decisions where `realized_outcome IS NULL` and `created_at <= (as_of or now) - timedelta(days=horizon_days)`.

### 5. Episodic Memory Decision Outcome Updates
- **File**: `src/autonomous_trading_analyst/memory/store.py`
- **Change**: Add `update_outcome_by_decision(decision_id: str, outcome_return: float) -> int` to `EpisodicMemory`, updating `EpisodeModel.outcome_return` for any episode associated with `decision_id` and returning the count of rows updated.

### 6. Outcome Reflector Engine
- **File**: `src/autonomous_trading_analyst/memory/reflection.py`
- **Change**: Implement `OutcomeReflector`:
  - `compute_forward_return(ticker: str, action: Action | str, start_time: datetime, horizon_days: int, as_of: datetime | None = None) -> tuple[float, float, float] | None`:
    Retrieves OHLCV bars for the evaluation period via `MarketDataProvider.get_bars`, extracts start price and end price, and calculates directional return:
    - BUY: `(P_end - P_start) / P_start`
    - SELL: `(P_start - P_end) / P_start`
    - HOLD: `0.0`
  - `reflect(as_of: datetime | None = None, horizon_days: int | None = None, limit: int | None = None) -> ReflectionReport`:
    Fetches pending decisions that have reached horizon maturity, calculates forward returns, persists results via `DecisionRepository.update_outcome` and `EpisodicMemory.update_outcome_by_decision`, and returns a detailed `ReflectionReport`.

### 7. Package Exports
- **File**: `src/autonomous_trading_analyst/domain/__init__.py` and `src/autonomous_trading_analyst/memory/__init__.py`
- **Change**: Re-export `ScoredOutcome` and `ReflectionReport` in domain, and `OutcomeReflector` in memory.

### 8. Unit Tests
- **File**: `tests/unit/test_reflection.py`
- **Change**: Write comprehensive unit tests covering:
  - Directional forward return calculations for BUY, SELL, and HOLD setups.
  - Filtering and skipping decisions that have not reached horizon maturity.
  - Resilient handling of missing bars, empty market data, and holidays.
  - End-to-end batch reflection updating SQLite decisions and episodic vector store.
  - Verification that updated outcomes are reflected in subsequent `recall_similar` calls.
  Mark tests with `@pytest.mark.issue_16`.

### 9. Pytest Marker Registration
- **File**: `pyproject.toml`
- **Change**: Add `issue_16: Outcome reflection` marker under `[tool.pytest.ini_options]` `markers`.

### 10. Verification & Quality Gates
```bash
make test-issue ID=16
make check
```

### 11. Git & Issue Finish
```bash
make finish-issue ID=16 MSG="feat(memory): implement outcome reflection and episodic update"
```

## Decisions
- Forward return is calculated directionally with respect to the action: BUY gains from price appreciation `(P_end - P_start) / P_start`, while SELL gains from avoided decline `(P_start - P_end) / P_start`. HOLD is assigned a neutral baseline (0.0).
- The reflection engine evaluates decisions against historical OHLCV bars rather than real-time spot prices alone, allowing deterministic evaluation in backtests and offline testing by accepting an optional `as_of` timestamp.
- Reflection updates both the relational `decisions` table and the vector `episodes` table simultaneously to maintain data consistency between analytical tracking and agent semantic retrieval.
