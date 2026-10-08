# Issue 23: Airflow Trading-Cycle DAG

**Branch**: `feature/issue-23-airflow-dag`
**Status**: Done
**PR**: opened by `make finish-issue` → `develop` (Closes #23)
**Milestone**: M5 - Platform & Delivery

## Objective
Implement an Apache Airflow DAG in `dags/` that schedules and triggers autonomous trading analysis cycles on weekdays via a thin HTTP trigger calling `POST /cycles` on the FastAPI application (`src/autonomous_trading_analyst/api/`). Business logic remains strictly decoupled within the package and API. The implementation includes health verification (`GET /health`), configurable execution timeouts, retries, and comprehensive DAG integrity and execution unit tests in `tests/unit/test_airflow_dag.py`.

## Acceptance Criteria
- [x] `dags/trading_cycle_dag.py` implements the `trading_cycle_dag` DAG scheduled on trading days (`0 21 * * 1-5`, UTC), with `catchup=False`.
- [x] The DAG implements sequential tasks:
  1. `check_api_health`: evaluates API and database readiness via `GET /health`.
  2. `trigger_trading_cycle`: dispatches `POST /cycles` to execute the analysis cycle with configurable timeouts and retries.
- [x] The DAG retrieves the target API base URL from the `AGENT_API_URL` environment variable (defaulting to `http://api:8080` in Compose or `http://localhost:8080` locally).
- [x] `pyproject.toml` registers the `issue_23: Airflow trading-cycle DAG` pytest marker and includes `dags` in ruff source analysis.
- [x] `tests/unit/test_airflow_dag.py` verifies DAG loading with `DagBag` (zero import errors), task graph topology (`check_api_health >> trigger_trading_cycle`), schedule configuration, and mocked HTTP execution of task callables for both success and failure cases (marked `@pytest.mark.issue_23`).
- [x] `make check` and `make test-issue ID=23` pass.

## Implementation Tasks

### 1. Preparation & Branching
```bash
make start-issue ID=23 NAME=airflow-dag
```

### 2. Airflow Trading-Cycle DAG
- **File**: `dags/trading_cycle_dag.py`
- **Change**: Define the DAG using Airflow SDK / TaskFlow:
  - DAG configuration:
    - `dag_id="trading_cycle_dag"`
    - `schedule="0 21 * * 1-5"` (weekdays at 21:00 UTC, after US market close)
    - `start_date=datetime(2026, 1, 1, tzinfo=timezone.utc)`
    - `catchup=False`
    - `tags=["trading", "autonomous-analyst", "m5"]`
    - `default_args`: `retries=2`, `retry_delay=timedelta(minutes=1)`
  - Task 1: `check_api_health`:
    - Sends `GET /health` with HTTPX (timeout 10s).
    - Validates HTTP 200 response and `"status": "ok"`.
    - Fails task on connection error or non-200 status code.
  - Task 2: `trigger_trading_cycle`:
    - Sends `POST /cycles` with HTTPX (timeout 300s for ReAct cycle execution).
    - Logs returned `CycleSummary` (cycle ID, decision count, orders count, portfolio equity).
    - Fails task on non-200 status code or network failure.
  - Dependency: `check_api_health >> trigger_trading_cycle`.

### 3. Pytest Marker & Ruff Configuration
- **File**: `pyproject.toml`
- **Change**:
  - Add `issue_23: Airflow trading-cycle DAG` to `[tool.pytest.ini_options]` `markers`.
  - Add `"dags"` to `[tool.ruff]` `src = ["src", "tests", "dags"]`.

### 4. DAG Integrity & Unit Tests
- **File**: `tests/unit/test_airflow_dag.py`
- **Change**: Write tests covering:
  - `test_dag_bag_import_errors`: verifies `DagBag(dag_folder="dags")` parses all DAGs with 0 import errors.
  - `test_dag_structure_and_metadata`: verifies `trading_cycle_dag` exists, schedule is `0 21 * * 1-5`, `catchup=False`, and tags match.
  - `test_dag_task_dependencies`: verifies tasks `check_api_health` and `trigger_trading_cycle` exist and downstream dependency is enforced.
  - `test_check_api_health_success_and_failure`: tests `check_api_health` with mocked HTTP 200 (success) and HTTP 503 / network exceptions (failure).
  - `test_trigger_trading_cycle_success_and_failure`: tests `trigger_trading_cycle` with mocked HTTP 200 returning cycle summary (success) and HTTP 500 / timeouts (failure).
  Mark tests with `@pytest.mark.issue_23`.

### 5. Verification & Quality Gates
```bash
make test-issue ID=23
make check
```

### 6. Git & Issue Finish
```bash
make finish-issue ID=23 MSG="feat(orchestration): implement airflow trading-cycle dag and integrity tests"
```

## Decisions
- **Thin HTTP trigger architecture**: The Airflow DAG only triggers the analysis cycle via HTTP; it does not import internal domain services or connect directly to PostgreSQL, preventing Airflow worker dependency bloat and maintaining clean architectural boundaries.
- **HTTPX client instead of extra provider package**: Core `httpx` is used for HTTP calls inside Python tasks rather than requiring `apache-airflow-providers-http`, keeping the dependency graph lightweight and avoiding version conflicts.
- **Pre-execution health check**: Running `check_api_health` before `trigger_trading_cycle` provides fast-fail visibility in Airflow monitoring, immediately isolating API/DB unavailability before triggering heavy agent reasoning loops.
- **Weekday schedule**: Scheduled for weekdays at 21:00 UTC (`0 21 * * 1-5`) after US equity markets close, allowing full end-of-day data availability.
