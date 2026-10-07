# Issue 14: Decision & Trace Persistence

**Branch**: `feature/issue-14-decision-persistence`
**Status**: To Do
**PR**: opened by `make finish-issue` → `develop` (Closes #14)
**Milestone**: M3 - Risk, Paper Trading & Memory

## Objective
Implement the relational database persistence layer using SQLAlchemy 2.0. The system must persist decisions, complete ReAct traces (thoughts, tool calls, observations, tokens, cost), orders, execution fills, and periodic portfolio state snapshots. Provide type-safe repository abstractions that map cleanly between domain models and database tables, supporting both PostgreSQL in production and fast SQLite in-memory for testing.

## Acceptance Criteria
- [x] `src/autonomous_trading_analyst/persistence/models.py` defines SQLAlchemy 2.0 mapped models for `decisions`, `trace_steps`, `orders`, `fills`, and `portfolio_snapshots`.
- [x] `src/autonomous_trading_analyst/persistence/db.py` provides engine configuration, session factories, and idempotent schema initialization (`init_db`).
- [x] `src/autonomous_trading_analyst/persistence/repositories.py` implements repositories for decisions, orders, fills, and portfolio state snapshots.
- [x] Repositories provide two-way translation between database records and domain entities (`DecisionRecord`, `Order`, `Fill`, `PortfolioState`).
- [x] `src/autonomous_trading_analyst/persistence/__init__.py` re-exports public database entities and repositories.
- [x] `tests/unit/test_persistence.py` covers engine creation, schema migration, and CRUD repository operations using SQLite in-memory (marked `@pytest.mark.issue_14`).
- [x] `pyproject.toml` registers the `issue_14` marker.
- [x] `make check` and `make test-issue ID=14` pass.

## Implementation Tasks

### 1. Preparation & Branching
```bash
make start-issue ID=14 NAME=decision-persistence
```

### 2. SQLAlchemy ORM Schema
- **File**: `src/autonomous_trading_analyst/persistence/models.py`
- **Change**: Define `Base(DeclarativeBase)` and ORM tables:
  - `DecisionModel`: `decision_id` (PK), `ticker`, `action`, `size`, `confidence`, `rationale`, `citations` (JSON), `total_cost_usd`, `total_tokens`, `created_at`, `realized_outcome`, relationship to `trace_steps`.
  - `TraceStepModel`: `id` (PK autoincrement), `decision_id` (FK to decisions), `step_number`, `thought`, `action_name`, `action_args` (JSON), `observation_id`, `observation`, `tokens_used`, `cost_usd`, `timestamp`.
  - `OrderModel`: `order_id` (PK), `decision_id` (nullable FK), `ticker`, `action`, `shares`, `limit_price`, `status`, `reason`, `created_at`, relationship to `fills`.
  - `FillModel`: `fill_id` (PK), `order_id` (FK to orders), `ticker`, `action`, `shares`, `price`, `commission`, `slippage`, `executed_at`.
  - `PortfolioSnapshotModel`: `snapshot_id` (PK), `cash`, `positions` (JSON), `total_equity`, `gross_exposure`, `created_at`.

### 3. Database Engine & Session Management
- **File**: `src/autonomous_trading_analyst/persistence/db.py`
- **Change**: Implement `create_db_engine(url)`, `get_session_factory(engine)`, and `init_db(engine)` to create tables idempotently.

### 4. Repository Layer
- **File**: `src/autonomous_trading_analyst/persistence/repositories.py`
- **Change**: Implement type-safe repositories:
  - `DecisionRepository`: `save(decision: DecisionRecord) -> None`, `get(decision_id: str) -> DecisionRecord | None`, `list_recent(limit: int = 50) -> list[DecisionRecord]`.
  - `OrderRepository`: `save(order: Order) -> None`, `get(order_id: str) -> Order | None`, `update_status(order_id: str, status: OrderStatus, reason: str | None = None) -> None`, `list_by_ticker(ticker: str) -> list[Order]`.
  - `FillRepository`: `save(fill: Fill) -> None`, `get(fill_id: str) -> Fill | None`, `list_by_order(order_id: str) -> list[Fill]`, `list_recent(limit: int = 50) -> list[Fill]`.
  - `PortfolioRepository`: `save(state: PortfolioState) -> str`, `get_latest() -> PortfolioState | None`, `list_history(limit: int = 100) -> list[PortfolioState]`.

### 5. Persistence Package Interface
- **File**: `src/autonomous_trading_analyst/persistence/__init__.py`
- **Change**: Re-export models, repositories, and engine/session helpers.

### 6. Unit Tests
- **File**: `tests/unit/test_persistence.py`
- **Change**: Write comprehensive unit tests using SQLite in-memory engine:
  - Schema creation and table initialization.
  - Decision persistence with full multi-step trace retrieval.
  - Order lifecycle persistence and status updates.
  - Fill recording and relationship linking.
  - Portfolio snapshot persistence and latest state retrieval.
  Mark tests with `@pytest.mark.issue_14`.

### 7. Pytest Marker Registration
- **File**: `pyproject.toml`
- **Change**: Add the `issue_14: Decision & trace persistence` marker under `[tool.pytest.ini_options]` `markers`.

### 8. Verification & Quality Gates
```bash
make test-issue ID=14
make check
```

### 9. Git & Issue Finish
```bash
make finish-issue ID=14 MSG="feat(persistence): implement decision, trace, order and portfolio persistence"
```

## Decisions
- Using SQLAlchemy 2.0 declarative syntax with `Mapped` and `mapped_column` ensures full mypy compatibility and strict type safety across all queries and model definitions.
- The repository layer decouples the application core and domain models from SQL details, allowing seamless execution against PostgreSQL in containerized/production environments and in-memory SQLite in testing.
- Decisions and trace steps are persisted relationally with cascading relationships, allowing efficient point queries on decisions as well as deep inspection of agent reasoning steps.
