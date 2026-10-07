# Issue 6: P-09 Research Client

**Branch**: `feature/issue-6-research-client`
**Status**: Done
**PR**: opened by `make finish-issue` → `develop` (Closes #6)
**Milestone**: M1 - Foundations & Market Tools

## Objective
Implement a client for the P-09 Financial Research Agent (`POST /research`) with an abstract interface (`ResearchClient`), a production HTTP implementation using `httpx`, and a deterministic `FakeResearchClient` for offline simulation and automated testing.

## Acceptance Criteria
- [x] `src/autonomous_trading_analyst/tools/research/models.py` defines `ResearchRequest`, `ResearchReport`, `Sentiment`, and exception classes (`ResearchError`, `ResearchTimeoutError`, `ResearchConnectionError`)
- [x] `src/autonomous_trading_analyst/tools/research/client.py` defines abstract `ResearchClient` and `HttpResearchClient` executing `POST /research` calls with timeout handling
- [x] `src/autonomous_trading_analyst/tools/research/fake.py` implements `FakeResearchClient` supporting seeded reports and deterministic synthetic research
- [x] `src/autonomous_trading_analyst/tools/research/__init__.py` re-exports public client classes, models, and `get_research_client` factory
- [x] `tests/unit/test_research_client.py` covers fake and mocked HTTP client routines (success, HTTP 500, timeouts, malformed responses) (marked `@pytest.mark.issue_6`)
- [x] `pyproject.toml` registers the `issue_6` marker
- [x] `make check` and `make test-issue ID=6` pass

## Implementation Tasks

### 1. Preparation & Branching
```bash
make start-issue ID=6 NAME=research-client
```

### 2. Research Client Data Models & Exceptions
- **File**: `src/autonomous_trading_analyst/tools/research/models.py`
- **Change**: Define `Sentiment` enum (BULLISH, BEARISH, NEUTRAL), `ResearchRequest`, `ResearchReport` (ticker, summary, sentiment, score between -1.0 and 1.0, key_findings, sources, timestamp), and custom exception hierarchy (`ResearchError`, `ResearchTimeoutError`, `ResearchConnectionError`).

### 3. Research Client Interface & HTTP Implementation
- **File**: `src/autonomous_trading_analyst/tools/research/client.py`
- **Change**: Define abstract `ResearchClient` interface (`get_research(ticker: str, query: str | None = None) -> ResearchReport`) and implement `HttpResearchClient` using `httpx.Client`. Handle HTTP request lifecycle, error responses (4xx/5xx), network timeouts, and JSON serialization.

### 4. Fake Research Client
- **File**: `src/autonomous_trading_analyst/tools/research/fake.py`
- **Change**: Implement `FakeResearchClient` adhering to `ResearchClient`. Provide methods to seed specific reports per ticker, simulate timeout/network errors on demand, and produce deterministic synthetic research summaries for unseeded tickers.

### 5. Research Package Interface & Factory
- **File**: `src/autonomous_trading_analyst/tools/research/__init__.py`
- **Change**: Re-export public models, client classes, and implement factory function `get_research_client(use_fake: bool = False, api_url: str | None = None, timeout: float | None = None)` reading defaults from `Settings`.

### 6. Unit Tests for Research Client
- **File**: `tests/unit/test_research_client.py`
- **Change**: Implement unit tests verifying `FakeResearchClient` (seeded reports, dynamic generation, error simulation), and `HttpResearchClient` (mocked `httpx` success, 4xx/5xx error conversion, network timeout translation, invalid JSON handling). Mark with `@pytest.mark.issue_6`.

### 7. Pytest Marker Registration
- **File**: `pyproject.toml`
- **Change**: Register the `issue_6` marker (`issue_6: P-09 research client`) under `[tool.pytest.ini_options]` `markers`.

### 8. Verification & Quality Gates
```bash
make test-issue ID=6
make check
```

### 9. Git & Issue Finish
```bash
make finish-issue ID=6 MSG="feat(research): implement P-09 financial research client and fake"
```

## Decisions
- Encapsulate all communication with the P-09 Financial Research Agent behind `ResearchClient` so tests and offline simulation run without external server dependencies.
- Score sentiment on a normalized scale `[-1.0, 1.0]` alongside a discrete `Sentiment` enum (BULLISH, BEARISH, NEUTRAL) for rich ReAct agent prompting and numerical validation.
- Unit tests for `HttpResearchClient` use standard unittest/monkeypatch mocking of `httpx` to guarantee completely offline and fast execution in CI.
