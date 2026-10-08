# Issue 20: Point-in-Time Backtest Engine

**Branch**: `feature/issue-20-backtest-engine`
**Status**: Done
**PR**: opened by `make finish-issue` → `develop` (Closes #20)
**Milestone**: M4 - Evaluation & Backtesting

## Objective
Implement a point-in-time backtesting engine (`BacktestEngine`) that replays historical evaluation dates chronologically without look-ahead bias. The engine executes the autonomous agent (via `AnalysisCycleOrchestrator` with real or fake LLM) and baseline strategies (`BuyAndHoldStrategy`, `SMACrossoverStrategy`) side-by-side under identical risk limits, transaction costs, and portfolio constraints, collecting synchronized equity curves, trade logs, and LLM decision costs into a structured `BacktestResult`.

## Acceptance Criteria
- [x] `src/autonomous_trading_analyst/evaluation/models.py` defines `BacktestConfig` and `BacktestResult` typed domain models.
- [x] `src/autonomous_trading_analyst/evaluation/backtest.py` implements `PointInTimeMarketDataProvider` wrapping any `MarketDataProvider` to enforce strict historical clamping (`<= as_of`) and prevent look-ahead bias across indicators and agent tools.
- [x] `src/autonomous_trading_analyst/evaluation/backtest.py` implements `BacktestEngine` providing `run` and `run_async` methods that replay historical trading dates chronologically, orchestrating the agent and baselines under identical risk guardrails and paper broker accounting.
- [x] `src/autonomous_trading_analyst/evaluation/backtest.py` provides the `create_backtest_engine` factory for assembling backtest environments with dependency injection and sensible fakes for offline testing.
- [x] `src/autonomous_trading_analyst/evaluation/__init__.py` re-exports `BacktestConfig`, `BacktestResult`, `BacktestEngine`, `PointInTimeMarketDataProvider`, and `create_backtest_engine`.
- [x] `tests/unit/test_backtest_engine.py` validates point-in-time data isolation, multi-date historical replay, synchronized agent and baseline execution under shared risk limits, equity curve collection, and cost attribution (marked `@pytest.mark.issue_20`).
- [x] `pyproject.toml` registers the `issue_20` marker.
- [x] `make check` and `make test-issue ID=20` pass.

## Implementation Tasks

### 1. Preparation & Branching
```bash
make start-issue ID=20 NAME=backtest-engine
```

### 2. Backtest Data Models
- **File**: `src/autonomous_trading_analyst/evaluation/models.py`
- **Change**: Define typed Pydantic models:
  - `BacktestConfig`: `watchlist: list[str]`, `start_date: datetime`, `end_date: datetime`, `initial_cash: float = 100000.0`, `risk_free_rate: float = 0.0`.
  - `BacktestResult`: `config: BacktestConfig`, `timestamps: list[datetime]`, `agent_metrics: PerformanceMetrics`, `agent_equity: list[float]`, `baseline_metrics: dict[str, PerformanceMetrics]`, `baseline_equities: dict[str, list[float]]`, `total_cycles: int`.

### 3. Point-in-Time Market Data Isolation
- **File**: `src/autonomous_trading_analyst/evaluation/backtest.py`
- **Change**: Implement `PointInTimeMarketDataProvider(MarketDataProvider)`:
  - Wraps an underlying `MarketDataProvider` and tracks current simulation date `current_as_of`.
  - `get_bars(ticker, start, end, interval)`: clamps `end` strictly to `min(end, self.current_as_of)` and discards any subsequent bars.
  - `get_latest_price(ticker)`: retrieves the latest closing price at or immediately preceding `current_as_of`.
  - `set_as_of(as_of: datetime)`: advances the simulation timestamp.

### 4. Point-in-Time Backtest Engine
- **File**: `src/autonomous_trading_analyst/evaluation/backtest.py`
- **Change**: Implement `BacktestEngine` and factory `create_backtest_engine`:
  - `run_async() -> BacktestResult` and `run() -> BacktestResult`:
    1. Extracts trading dates between `config.start_date` and `config.end_date`.
    2. Initializes dedicated `PaperBroker`s with identical initial cash and settings for the agent and each baseline strategy.
    3. Iterates chronologically through each date `as_of`:
       - Updates `PointInTimeMarketDataProvider.set_as_of(as_of)`.
       - If agent orchestrator is provided: executes `orchestrator.run_cycle(watchlist, as_of=as_of)` and records agent equity and decisions.
       - For each baseline strategy: generates signals with historical price slices up to `as_of`, evaluates signals through `RiskManager` (identical limits), executes orders on baseline's broker, marks to market, and records equity.
    4. Computes `PerformanceMetrics` for the agent (including LLM costs/tokens) and each baseline (zero LLM costs).
    5. Returns compiled `BacktestResult`.
  - `create_backtest_engine(...)`: wires in-memory session factory, fake LLM/embeddings, risk manager, and market data provider for offline backtesting.

### 5. Package Exports
- **File**: `src/autonomous_trading_analyst/evaluation/__init__.py`
- **Change**: Re-export `BacktestConfig`, `BacktestResult`, `BacktestEngine`, `PointInTimeMarketDataProvider`, and `create_backtest_engine`.

### 6. Unit Tests
- **File**: `tests/unit/test_backtest_engine.py`
- **Change**: Write comprehensive unit tests covering:
  - `PointInTimeMarketDataProvider`: verification that bars and prices after `as_of` are strictly inaccessible.
  - Multi-day historical date replay with `FakeMarketDataProvider` and `FakeLLMClient`.
  - Shared risk guardrails: confirming baselines and agent are bounded by identical position limits.
  - Comparative metrics: verifying agent vs Buy & Hold vs SMA Crossover metrics in `BacktestResult`.
  - Pydantic serialization of `BacktestResult` (`model_dump()` / `model_dump_json()`).
  Mark tests with `@pytest.mark.issue_20`.

### 7. Pytest Marker Registration
- **File**: `pyproject.toml`
- **Change**: Add `issue_20: Point-in-time backtest engine` marker under `[tool.pytest.ini_options]` `markers`.

### 8. Verification & Quality Gates
```bash
make test-issue ID=20
make check
```

### 9. Git & Issue Finish
```bash
make finish-issue ID=20 MSG="feat(evaluation): implement point-in-time backtest engine"
```

## Decisions
- A dedicated `PointInTimeMarketDataProvider` decorator wraps the market data provider passed to tools and orchestrators, making it physically impossible for indicators, anomaly detectors, or agents to access price bars ahead of `as_of`.
- The agent and each baseline operate on independent `PaperBroker` instances initialized with identical cash and transaction fee models, but evaluated under the exact same `RiskManager` rules (watchlist restrictions, max position size pct, gross exposure pct).
- `BacktestResult` stores timestamps and equity series as standard lists of primitive floats and datetimes rather than complex objects, guaranteeing seamless JSON serialization for Issue 21's reporting and CLI tool.
