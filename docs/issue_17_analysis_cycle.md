# Issue 17: Analysis Cycle Orchestrator

**Branch**: `feature/issue-17-analysis-cycle`
**Status**: Done
**PR**: opened by `make finish-issue` → `develop` (Closes #17)
**Milestone**: M3 - Risk, Paper Trading & Memory

## Objective
Implement the end-to-end analysis cycle orchestrator (`AnalysisCycleOrchestrator`) that connects the entire trading pipeline: watchlist iteration, market data retrieval, stop-loss sweep, ReAct agent reasoning, deterministic risk guardrails, paper broker execution, relational persistence (decisions, traces, orders, fills, portfolio snapshots), and episodic vector memory storage. The cycle runs deterministically and fully offline in test environments using fakes.

## Acceptance Criteria
- [x] `src/autonomous_trading_analyst/domain/cycle.py` defines `CycleSummary` containing execution timestamp, watchlist, decisions, orders, fills, stop-loss orders, portfolio state, token/USD costs, and error tracking.
- [x] `src/autonomous_trading_analyst/cycle.py` implements `AnalysisCycleOrchestrator` providing `run_cycle` (async) and `run_cycle_sync`, coordinating market data, stop-loss sweep, agent analysis, risk evaluation, broker execution, persistence, and episodic memory.
- [x] `src/autonomous_trading_analyst/cycle.py` provides the `create_analysis_cycle` factory assembling all pipeline components with dependency injection and sensible defaults/fakes.
- [x] `src/autonomous_trading_analyst/__init__.py` and `domain/__init__.py` re-export cycle models and orchestrator functions.
- [x] `tests/unit/test_cycle.py` verifies full cycle execution offline with fakes, stop-loss sweeps, risk limits, complete relational persistence, episodic vector storage, and resilient error handling (marked `@pytest.mark.issue_17`).
- [x] `pyproject.toml` registers the `issue_17` marker.
- [x] `make check` and `make test-issue ID=17` pass.

## Implementation Tasks

### 1. Preparation & Branching
```bash
make start-issue ID=17 NAME=analysis-cycle
```

### 2. Cycle Domain Models
- **File**: `src/autonomous_trading_analyst/domain/cycle.py`
- **Change**: Define typed Pydantic models:
  - `CycleSummary`: `cycle_id: str`, `timestamp: datetime`, `watchlist: list[str]`, `decisions: list[DecisionRecord]`, `orders: list[Order]`, `fills: list[Fill]`, `stop_loss_orders: list[Order]`, `portfolio_state: PortfolioState`, `total_cost_usd: float`, `total_tokens: int`, `errors: dict[str, str]`.

### 3. Analysis Cycle Orchestrator
- **File**: `src/autonomous_trading_analyst/cycle.py`
- **Change**: Implement `AnalysisCycleOrchestrator` and factory `create_analysis_cycle`:
  - `run_cycle(watchlist: list[str] | None = None, as_of: datetime | None = None) -> CycleSummary`:
    1. Fetches current prices for all tickers.
    2. Runs stop-loss sweep via `RiskManager.check_stop_losses`, executes approved exits on `PaperBroker`, and records orders/fills.
    3. Iterates over watchlist running `ReActAgent.run(ticker)`.
    4. Converts scratchpad to domain `DecisionRecord` and `TraceStep`s, persisting to `DecisionRepository`.
    5. Stores decision context and vector embedding in `EpisodicMemory`.
    6. Evaluates signals with `RiskManager.evaluate_signal`.
    7. Submits approved/resized orders to `PaperBroker`, persisting orders and fills.
    8. Persists end-of-cycle portfolio snapshot to `PortfolioRepository`.
    9. Returns compiled `CycleSummary`.
  - `run_cycle_sync(watchlist: list[str] | None = None, as_of: datetime | None = None) -> CycleSummary`: synchronous execution wrapper.
  - `create_analysis_cycle(...)`: factory function constructing an orchestrator with all dependencies wired.

### 4. Package Exports
- **File**: `src/autonomous_trading_analyst/__init__.py` and `src/autonomous_trading_analyst/domain/__init__.py`
- **Change**: Re-export `AnalysisCycleOrchestrator`, `create_analysis_cycle`, and `CycleSummary`.

### 5. Unit & Integration Tests
- **File**: `tests/unit/test_cycle.py`
- **Change**: Write comprehensive tests:
  - End-to-end cycle execution with `FakeLLMClient`, `FakeMarketDataProvider`, and in-memory SQLite.
  - Verification of stop-loss sweep triggered by simulated price drops.
  - Risk guardrail enforcement during cycle (position sizing and limits).
  - Complete database verification: decisions, traces, orders, fills, and portfolio snapshot.
  - Episodic memory persistence and subsequent similarity recall.
  - Resilient ticker error handling (one ticker failure does not halt the entire cycle).
  Mark tests with `@pytest.mark.issue_17`.

### 6. Pytest Marker Registration
- **File**: `pyproject.toml`
- **Change**: Add `issue_17: Analysis cycle orchestrator` marker under `[tool.pytest.ini_options]` `markers`.

### 7. Verification & Quality Gates
```bash
make test-issue ID=17
make check
```

### 8. Git & Issue Finish
```bash
make finish-issue ID=17 MSG="feat(cycle): implement end-to-end analysis cycle orchestrator"
```

### 9. Milestone Finish (Closes M3)
```bash
make finish-milestone MILESTONE=M3
```

## Decisions
- The analysis cycle executes a stop-loss sweep before processing new agent buy/sell signals to ensure risk exits take priority and portfolio cash/capacity are updated before sizing new positions.
- Scratchpad thought and observation texts are compiled into rich context strings stored directly in episodic vector memory, guaranteeing semantic searchability of reasoning history.
- Ticker-level errors (e.g. LLM timeout or invalid payload) are captured in `CycleSummary.errors` without crashing the entire cycle, ensuring remaining watchlist tickers complete analysis.
