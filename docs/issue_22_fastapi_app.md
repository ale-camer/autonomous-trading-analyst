# Issue 22: FastAPI Agent & Portfolio API

**Branch**: `feature/issue-22-fastapi-app`
**Status**: Done
**PR**: opened by `make finish-issue` → `develop` (Closes #22)
**Milestone**: M5 - Platform & Delivery

## Objective
Implement a production-grade, typed FastAPI application in `src/autonomous_trading_analyst/api/` exposing RESTful endpoints for the trading platform. The API enables clients (including the Airflow DAG scheduled in Issue 23) to trigger analysis cycles, query portfolio holdings and cash balances, list historical trading decisions, retrieve full reasoning traces for individual decisions, and inspect system health. The application is built with modular dependency injection to facilitate testing with offline fakes and in-memory databases.

## Acceptance Criteria
- [x] `src/autonomous_trading_analyst/api/schemas.py` defines typed Pydantic models for request payloads (`CycleRequest`) and health status responses (`HealthResponse`).
- [x] `src/autonomous_trading_analyst/api/dependencies.py` implements dependency providers for settings, SQLAlchemy sessionmaker, orchestrator, and domain repositories (`DecisionRepository`, `PortfolioRepository`).
- [x] `src/autonomous_trading_analyst/api/routes/health.py` implements `GET /health` verifying service liveness and database connectivity (`SELECT 1`), returning 200 on success or 503 on database failure.
- [x] `src/autonomous_trading_analyst/api/routes/cycles.py` implements `POST /cycles` accepting an optional watchlist and evaluation timestamp, executing `AnalysisCycleOrchestrator.run_cycle`, and returning `CycleSummary`.
- [x] `src/autonomous_trading_analyst/api/routes/portfolio.py` implements `GET /portfolio` returning the latest portfolio state (`PortfolioState`), falling back to initial broker state if no snapshot exists.
- [x] `src/autonomous_trading_analyst/api/routes/decisions.py` implements `GET /decisions` (supporting `limit` and `ticker` filter) and `GET /decisions/{id}` returning complete decision records with full reasoning traces (`trace: list[TraceStep]`) or 404 if not found.
- [x] `src/autonomous_trading_analyst/api/app.py` implements `create_app` factory and ASGI instance `app`.
- [x] `src/autonomous_trading_analyst/api/__init__.py` re-exports `create_app` and `app`.
- [x] `pyproject.toml` registers the `issue_22: FastAPI agent & portfolio API` pytest marker.
- [x] `tests/unit/test_api.py` verifies all endpoints, error conditions (404, 503), parameter validations, and dependency overrides with fake components (marked `@pytest.mark.issue_22`).
- [x] `make check` and `make test-issue ID=22` pass.

## Implementation Tasks

### 1. Preparation & Branching
```bash
make start-issue ID=22 NAME=fastapi-app
```

### 2. API Schemas & Request Models
- **File**: `src/autonomous_trading_analyst/api/schemas.py`
- **Change**: Define request/response Pydantic models:
  - `CycleRequest`: `watchlist: list[str] | None = None`, `as_of: datetime | None = None`.
  - `HealthResponse`: `status: str = "ok"`, `database: str = "connected"`, `app_env: str`, `timestamp: datetime`.
  - Re-use domain models `CycleSummary`, `PortfolioState`, and `DecisionRecord` for response typing.

### 3. Dependency Injection Layer
- **File**: `src/autonomous_trading_analyst/api/dependencies.py`
- **Change**: Implement FastAPI dependency providers:
  - `get_settings_dep() -> Settings`: retrieves application settings.
  - `get_session_factory_dep() -> sessionmaker[Session]`: provides thread-safe SQLAlchemy sessionmaker.
  - `get_orchestrator_dep(...) -> AnalysisCycleOrchestrator`: provides orchestrator assembled via `create_analysis_cycle`.
  - `get_decision_repo_dep(...) -> DecisionRepository`: provides `DecisionRepository`.
  - `get_portfolio_repo_dep(...) -> PortfolioRepository`: provides `PortfolioRepository`.

### 4. Route Handlers
- **File**: `src/autonomous_trading_analyst/api/routes/health.py`
  - `GET /health`: checks database connection (`session.execute(text("SELECT 1"))`), returns `HealthResponse` or raises `HTTPException(503)` if DB is unreachable.
- **File**: `src/autonomous_trading_analyst/api/routes/cycles.py`
  - `POST /cycles`: executes `await orchestrator.run_cycle(watchlist=body.watchlist, as_of=body.as_of)` and returns `CycleSummary`.
- **File**: `src/autonomous_trading_analyst/api/routes/portfolio.py`
  - `GET /portfolio`: retrieves latest snapshot from `portfolio_repo.get_latest()`. If none exists, returns initial portfolio state.
- **File**: `src/autonomous_trading_analyst/api/routes/decisions.py`
  - `GET /decisions`: returns list of decisions filtered by `ticker` and paginated by `limit`.
  - `GET /decisions/{id}`: returns full decision record with complete `trace` list; raises 404 if not found.

### 5. Application Factory & Package Exports
- **File**: `src/autonomous_trading_analyst/api/app.py`
  - Implement `create_app(settings: Settings | None = None) -> FastAPI`: mounts routes, configures OpenAPI title/metadata, and handles lifespan startup/shutdown.
  - Expose module-level `app = create_app()`.
- **File**: `src/autonomous_trading_analyst/api/__init__.py`
  - Re-export `app` and `create_app`.

### 6. Pytest Marker Registration
- **File**: `pyproject.toml`
- **Change**: Add `issue_22: FastAPI agent & portfolio API` marker under `[tool.pytest.ini_options]` `markers`.

### 7. Unit Tests with Dependency Injection Overrides
- **File**: `tests/unit/test_api.py`
- **Change**: Write comprehensive test suite using FastAPI `TestClient`:
  - `test_health_endpoint_ok`: verifies 200 OK and connected database.
  - `test_health_endpoint_db_failure`: overrides sessionmaker with failing connection, verifies 503 Service Unavailable.
  - `test_post_cycles_default_watchlist`: triggers cycle with default watchlist, verifies 200 and `CycleSummary` structure.
  - `test_post_cycles_custom_watchlist`: triggers cycle with custom watchlist and timestamp.
  - `test_get_portfolio_initial`: returns initial state when no snapshot is in DB.
  - `test_get_portfolio_after_cycle`: returns updated snapshot after a cycle run.
  - `test_get_decisions_list`: verifies decision pagination and ticker filtering.
  - `test_get_decision_by_id_found`: verifies full decision with all trace steps.
  - `test_get_decision_by_id_not_found`: verifies 404 response for non-existent decision ID.
  Mark tests with `@pytest.mark.issue_22`.

### 8. Verification & Quality Gates
```bash
make test-issue ID=22
make check
```

### 9. Git & Issue Finish
```bash
make finish-issue ID=22 MSG="feat(api): implement fastapi agent and portfolio api"
```

## Decisions
- **FastAPI `Depends` for stateful services**: All database sessionmakers, orchestrators, and repositories are injected via FastAPI dependencies, allowing tests to override components cleanly via `app.dependency_overrides` without modifying global state or disk files.
- **Domain model reuse for responses**: Domain models (`CycleSummary`, `PortfolioState`, `DecisionRecord`) are directly used as response models to ensure single-source-of-truth consistency and avoid redundant mapping layers.
- **Active health probe**: The `/health` endpoint performs an active `SELECT 1` query to verify real database connectivity, enabling reliable readiness probes in container environments (e.g. Docker Compose in Issue 24).
- **Graceful initial portfolio fallback**: When `GET /portfolio` is queried before any cycles have executed, it returns an initial state derived from settings cash (`paper_initial_cash`) with empty positions rather than returning 404 or failing.
