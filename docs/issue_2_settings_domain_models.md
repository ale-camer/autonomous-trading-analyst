# Issue 2: Settings & Domain Models

**Branch**: `feature/issue-2-settings-domain-models`
**Status**: Done
**PR**: opened by `make finish-issue` → `develop` (Closes #2)
**Milestone**: M1 - Foundations & Market Tools

## Objective
Implement typed application configuration (`Settings`) using `pydantic-settings` strictly enforcing paper trading mode, and define the core domain models (`Action`, `Signal`, `Order`, `OrderStatus`, `Fill`, `Position`, `PortfolioState`, `TraceStep`, `DecisionRecord`) that form the foundation for market tools, ReAct reasoning, and paper broker execution.

## Acceptance Criteria
- [x] `src/autonomous_trading_analyst/config.py` defines typed `Settings` matching `.env.example`, strictly enforcing `TRADING_MODE="paper"`, and exposes `get_settings()`
- [x] `src/autonomous_trading_analyst/domain/models.py` defines all core domain models (`Action`, `Signal`, `Order`, `OrderStatus`, `Fill`, `Position`, `PortfolioState`, `TraceStep`, `DecisionRecord`) with validation rules
- [x] `src/autonomous_trading_analyst/domain/__init__.py` re-exports public domain entities
- [x] `tests/unit/test_config.py` validates default values, watchlist parsing, and rejection of invalid `TRADING_MODE` values (marked `@pytest.mark.issue_2`)
- [x] `tests/unit/test_domain.py` validates creation, constraints, and serialization of all domain models (marked `@pytest.mark.issue_2`)
- [x] `pyproject.toml` registers the `issue_2` marker
- [x] `make check` and `make test-issue ID=2` pass

## Implementation Tasks

### 1. Preparation & Branching
```bash
make start-issue ID=2 NAME=settings-domain-models
```

### 2. Typed Application Settings
- **File**: `src/autonomous_trading_analyst/config.py`
- **Change**: Define `Settings` using `pydantic-settings` (`BaseSettings`) modeling all environment variables from `.env.example` (runtime, LLM, embeddings, database, agent tools, risk limits, paper broker, agent budgets, GCP, orchestration). Enforce invariant `TRADING_MODE="paper"` via validator/Literal. Provide `get_settings()` helper.

### 3. Core Domain Models
- **File**: `src/autonomous_trading_analyst/domain/models.py`
- **Change**: Implement domain models using Pydantic: `Action` enum (BUY, SELL, HOLD), `Signal` (ticker, action, size, confidence, rationale, citations), `OrderStatus` enum, `Order`, `Fill`, `Position`, `PortfolioState`, `TraceStep`, and `DecisionRecord`. Enforce value validations (confidence between 0 and 1, size between 0 and 1, citation presence for active signals).

### 4. Domain Package Interface
- **File**: `src/autonomous_trading_analyst/domain/__init__.py`
- **Change**: Re-export all domain models (`Action`, `Signal`, `Order`, `OrderStatus`, `Fill`, `Position`, `PortfolioState`, `TraceStep`, `DecisionRecord`) for clean imports across the package.

### 5. Settings Unit Tests
- **File**: `tests/unit/test_config.py`
- **Change**: Implement tests covering default settings, parsing comma-separated watchlists, environment variable overrides, secret string masking, and validation error on invalid `TRADING_MODE`. Mark with `@pytest.mark.issue_2`.

### 6. Domain Models Unit Tests
- **File**: `tests/unit/test_domain.py`
- **Change**: Implement tests verifying creation, field constraints (confidence ranges, action types, non-empty citations for trade signals, valid calculations) and JSON serialization for all domain models. Mark with `@pytest.mark.issue_2`.

### 7. Pytest Marker Registration
- **File**: `pyproject.toml`
- **Change**: Register the `issue_2` marker (`issue_2: Settings and domain models`) under `[tool.pytest.ini_options]` `markers`.

### 8. Verification & Quality Gates
```bash
make test-issue ID=2
make check
```

### 9. Git & Issue Finish
```bash
make finish-issue ID=2 MSG="feat(domain): implement typed settings and core domain models"
```

## Decisions
- Enforce `TRADING_MODE="paper"` via `Literal["paper"]` in `Settings` to structurally guarantee at runtime and typecheck time that live trading cannot be configured.
- Place domain models in `domain/models.py` and expose them through `domain/__init__.py` to provide a clean single entry point for imports throughout the codebase.
- Parse `WATCHLIST` from comma-separated string or list in Pydantic to support both `.env` string format and programmatic list overrides.
