# Issue 24: Docker & Compose Stack

**Branch**: `feature/issue-24-docker-compose`
**Status**: Done
**PR**: opened by `make finish-issue` → `develop` (Closes #24)
**Milestone**: M5 - Platform & Delivery

## Objective
Implement containerization and orchestration for the trading platform, providing a production-grade `Dockerfile` for the application and a `docker-compose.yml` stack connecting PostgreSQL with pgvector (`db`), the FastAPI agent & portfolio service (`api`), and the Apache Airflow orchestrator (`airflow`). The stack configures reliable healthchecks, dependency sequencing (`depends_on` with `condition: service_healthy`), volume persistence, non-root security boundaries (`UID 50000`), and centralized environment variable loading from `.env`.

## Acceptance Criteria
- [x] `Dockerfile` builds a lightweight, secure container image based on `python:3.12-slim`, creating non-root user `trader` (`UID 50000`), installing `.[all]`, exposing port 8080, and including a container `HEALTHCHECK` probing `GET /health`.
- [x] `.dockerignore` excludes caches (`.venv`, `__pycache__`, `.mypy_cache`, `.pytest_cache`, `.ruff_cache`), git metadata, test coverage artifacts, and local SQLite/env files.
- [x] `infra/init-db.sql` initializes PostgreSQL on first boot, enabling the `vector` extension and provisioning databases for `trading` and `airflow`.
- [x] `docker-compose.yml` orchestrates:
  1. `db`: `pgvector/pgvector:pg16` with persistent volume `postgres_data` and `pg_isready` healthcheck.
  2. `api`: built from root `Dockerfile`, dependent on `db` healthy, exposing port `8080`, with HTTP healthcheck on `/health`.
  3. `airflow`: running `airflow standalone`, mounting `dags/` and volume `airflow_data`, dependent on `api` healthy, exposing port `8081` (mapped to Airflow webserver).
- [x] All services load configuration via `env_file: .env` with sensible defaults when `.env` is absent.
- [x] `pyproject.toml` registers the `issue_24: Docker & Compose stack` pytest marker.
- [x] `tests/unit/test_docker_compose.py` validates `Dockerfile`, `docker-compose.yml`, `infra/init-db.sql`, and `.dockerignore` structural integrity, healthcheck configurations, port allocations, and service dependencies (marked `@pytest.mark.issue_24`).
- [x] `make check` and `make test-issue ID=24` pass.

## Implementation Tasks

### 1. Preparation & Branching
```bash
make start-issue ID=24 NAME=docker-compose
```

### 2. Dockerfile & .dockerignore
- **File**: `Dockerfile`
  - Base: `python:3.12-slim`.
  - Packages: `curl`, `gcc`, `libpq-dev`.
  - User: creates group/user `trader` with UID 50000 (matching `AIRFLOW_UID=50000`).
  - Installation: installs package with `pip install --no-cache-dir .[all]`.
  - Expose: `8080`.
  - Healthcheck: `HEALTHCHECK --interval=10s --timeout=5s --start-period=10s --retries=5 CMD curl -f http://localhost:8080/health || exit 1`.
  - Command: `CMD ["uvicorn", "autonomous_trading_analyst.api:app", "--host", "0.0.0.0", "--port", "8080"]`.
- **File**: `.dockerignore`
  - Ignores `.venv`, `__pycache__`, `.git`, `.coverage`, caches, temporary files.

### 3. Database Initialization Script
- **File**: `infra/init-db.sql`
  - `CREATE EXTENSION IF NOT EXISTS vector;`
  - `CREATE DATABASE airflow;`
  - `GRANT ALL PRIVILEGES ON DATABASE airflow TO trader;`

### 4. Docker Compose Stack
- **File**: `docker-compose.yml`
  - `services`:
    - `db`:
      - image: `pgvector/pgvector:pg16`
      - environment: `POSTGRES_USER=trader`, `POSTGRES_PASSWORD=trader`, `POSTGRES_DB=trading`
      - volumes: `postgres_data:/var/lib/postgresql/data`, `./infra/init-db.sql:/docker-entrypoint-initdb.d/init-db.sql:ro`
      - ports: `5432:5432`
      - healthcheck: `pg_isready -U trader -d trading`
    - `api`:
      - build: `context: .`, `dockerfile: Dockerfile`
      - depends_on: `db: condition: service_healthy`
      - ports: `8080:8080`
      - environment: `DATABASE_URL=postgresql+psycopg://trader:trader@db:5432/trading`
      - env_file: `.env`
      - healthcheck: `curl -f http://localhost:8080/health`
    - `airflow`:
      - build: `context: .`, `dockerfile: Dockerfile`
      - command: `airflow standalone`
      - depends_on: `api: condition: service_healthy`, `db: condition: service_healthy`
      - ports: `8081:8080`
      - environment:
        - `AIRFLOW__CORE__DAGS_FOLDER=/app/dags`
        - `AIRFLOW__CORE__LOAD_EXAMPLES=False`
        - `AIRFLOW__DATABASE__SQL_ALCHEMY_CONN=postgresql+psycopg://trader:trader@db:5432/airflow`
        - `AGENT_API_URL=http://api:8080`
      - volumes: `./dags:/app/dags:ro`, `airflow_data:/home/trader/airflow`
      - env_file: `.env`
      - healthcheck: `curl -f http://localhost:8080/health || exit 1` (or `airflow version`)
  - `volumes`: `postgres_data`, `airflow_data`

### 5. Pytest Marker Registration
- **File**: `pyproject.toml`
- **Change**: Add `issue_24: Docker & Compose stack` to `[tool.pytest.ini_options]` `markers`.

### 6. Validation Unit Tests
- **File**: `tests/unit/test_docker_compose.py`
- **Change**: Write comprehensive test suite:
  - `test_dockerfile_syntax_and_best_practices`: validates base image, non-root user creation and usage, expose 8080, healthcheck directive, and Uvicorn entrypoint.
  - `test_dockerignore_coverage`: checks that `.venv`, `__pycache__`, `.git`, `.pytest_cache`, and SQLite files are excluded.
  - `test_init_db_sql`: validates presence of `vector` extension and `airflow` database provisioning.
  - `test_docker_compose_schema_and_services`: parses `docker-compose.yml` with PyYAML, verifying `db`, `api`, and `airflow` services exist.
  - `test_docker_compose_healthchecks`: validates healthcheck commands and intervals across all services.
  - `test_docker_compose_dependencies`: validates `api` depends on `db` healthy, and `airflow` depends on `api` healthy.
  - `test_docker_compose_port_mappings`: validates no port collision on host (`5432`, `8080`, `8081`).
  - `test_docker_compose_volumes`: validates persistent volumes `postgres_data` and `airflow_data`.
  Mark tests with `@pytest.mark.issue_24`.

### 7. Verification & Quality Gates
```bash
make test-issue ID=24
make check
```

### 8. Git & Issue Finish
```bash
make finish-issue ID=24 MSG="feat(platform): implement dockerfile and docker compose stack"
```

## Decisions
- **Shared unified application image**: Both `api` and `airflow` build from the same root `Dockerfile` using `.[all]`, avoiding duplicate container definitions and guaranteeing exact version parity for dependencies across API and DAG execution environments.
- **Port deconfliction on host**: The API binds host port `8080:8080`, while Airflow binds host port `8081:8080`, preventing port collision while allowing concurrent access to both the OpenAPI swagger docs (`http://localhost:8080/docs`) and the Airflow Web UI (`http://localhost:8081`).
- **Database separation in single container**: The PostgreSQL container initializes `trading` as the default application DB and provisions a distinct `airflow` DB via `infra/init-db.sql`, keeping Airflow metadata cleanly isolated from trading repository tables without requiring a second database container.
- **Service dependency conditioning**: Services use `condition: service_healthy` rather than standard `depends_on`, preventing premature API launch before Postgres is accepting connections and ensuring Airflow only triggers after the API health probe returns 200 OK.
