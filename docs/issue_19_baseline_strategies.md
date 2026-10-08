# Issue 19: Baseline Strategies

**Branch**: `feature/issue-19-baseline-strategies`
**Status**: Done
**PR**: opened by `make finish-issue` → `develop` (Closes #19)
**Milestone**: M4 - Evaluation & Backtesting

## Objective
Implement baseline benchmark trading strategies (`BuyAndHoldStrategy` and `SMACrossoverStrategy`) in `evaluation/` operating on the same `PaperBroker` and deterministic `RiskManager` guardrails as the autonomous agent. These baselines serve as standard non-LLM control benchmarks for quantitative backtesting without look-ahead bias, tracking identical transaction costs, slippage, and portfolio equity metrics with zero token expenditure.

## Acceptance Criteria
- [x] `src/autonomous_trading_analyst/evaluation/baselines.py` defines abstract `BaselineStrategy` with unified `generate_signal` interface.
- [x] `BuyAndHoldStrategy` executes initial target entry on first available opportunity and maintains position (`HOLD`) across subsequent periods.
- [x] `SMACrossoverStrategy` implements point-in-time moving average calculation, triggering `BUY` signals on golden crosses (fast SMA crosses above slow SMA) and `SELL` signals on death crosses (fast SMA crosses below slow SMA).
- [x] `run_baseline_simulation` runs point-in-time chronological replay over price series on `PaperBroker`, applying `RiskManager` constraints and returning `PerformanceMetrics`.
- [x] `src/autonomous_trading_analyst/evaluation/__init__.py` re-exports baseline strategies and simulation runners.
- [x] `tests/unit/test_baseline_strategies.py` validates signal transitions, golden/death cross detection, point-in-time safety, risk limit adherence, zero token cost attribution, and simulation metric calculation (marked `@pytest.mark.issue_19`).
- [x] `pyproject.toml` registers the `issue_19` marker.
- [x] `make check` and `make test-issue ID=19` pass.

## Implementation Tasks

### 1. Preparation & Branching
```bash
make start-issue ID=19 NAME=baseline-strategies
```

### 2. Baseline Strategy Protocol & Base Class
- **File**: `src/autonomous_trading_analyst/evaluation/baselines.py`
- **Change**: Define `BaselineStrategy(ABC)`:
  - `name: str` property identifying strategy name.
  - `generate_signal(ticker: str, current_price: float, portfolio: PortfolioState, price_history: pd.Series | None = None, as_of: datetime | None = None) -> Signal`: pure decision function emitting a validated domain `Signal`.

### 3. Buy & Hold Strategy
- **File**: `src/autonomous_trading_analyst/evaluation/baselines.py`
- **Change**: Implement `BuyAndHoldStrategy(BaselineStrategy)`:
  - Configurable `allocation_pct: float = 1.0` (fraction of allowable portfolio position size).
  - Emits `Action.BUY` when flat or uninvested with `citations=["baseline:buy_and_hold"]`.
  - Emits `Action.HOLD` once position is established or when no investable cash remains.

### 4. SMA Crossover Strategy
- **File**: `src/autonomous_trading_analyst/evaluation/baselines.py`
- **Change**: Implement `SMACrossoverStrategy(BaselineStrategy)`:
  - Parameters: `fast_period: int = 10` (or 20), `slow_period: int = 50`, `size: float = 1.0`.
  - Calculates moving averages on `price_history` strictly up to current timestamp without future data leakage.
  - Detects golden cross (fast crosses above slow): emits `Action.BUY` with `citations=["baseline:sma_crossover:golden_cross"]`.
  - Detects death cross (fast crosses below slow): emits `Action.SELL` with `citations=["baseline:sma_crossover:death_cross"]`.
  - Emits `Action.HOLD` when insufficient warmup data (< `slow_period` bars) or when trend continues without cross.

### 5. Baseline Simulation Runner
- **File**: `src/autonomous_trading_analyst/evaluation/baselines.py`
- **Change**: Implement `run_baseline_simulation`:
  - Iterates chronologically over historical price series.
  - Evaluates signal via `strategy.generate_signal`.
  - Evaluates order through `RiskManager` (if provided) and executes on `PaperBroker`.
  - Marks broker to market at each bar close and aggregates snapshots.
  - Returns `(PaperBroker, PerformanceMetrics)` using Issue 18's `compute_performance_metrics`.

### 6. Package Exports
- **File**: `src/autonomous_trading_analyst/evaluation/__init__.py`
- **Change**: Re-export `BaselineStrategy`, `BuyAndHoldStrategy`, `SMACrossoverStrategy`, and `run_baseline_simulation`.

### 7. Unit Tests
- **File**: `tests/unit/test_baseline_strategies.py`
- **Change**: Write comprehensive unit tests covering:
  - Buy & Hold: initial purchase, subsequent holds, zero cash behavior.
  - SMA Crossover: warmup period handling, synthetic prices triggering golden cross, synthetic prices triggering death cross, sideways noise.
  - Point-in-time safety: verifying future bars in series are strictly excluded from moving average inputs at time `t`.
  - Broker & risk integration: position sizing limits, commission deductions, slippage impacts.
  - `run_baseline_simulation`: equity curve computation, trade extraction, Sharpe/drawdown calculation, and zero LLM cost verification.
  Mark tests with `@pytest.mark.issue_19`.

### 8. Pytest Marker Registration
- **File**: `pyproject.toml`
- **Change**: Add `issue_19: Baseline strategies` marker under `[tool.pytest.ini_options]` `markers`.

### 9. Verification & Quality Gates
```bash
make test-issue ID=19
make check
```

### 10. Git & Issue Finish
```bash
make finish-issue ID=19 MSG="feat(evaluation): implement buy & hold and sma crossover baseline strategies"
```

## Decisions
- Baseline strategies output the standard domain `Signal` model with baseline citations, allowing them to pass through identical `RiskManager` rules and `PaperBroker` execution as the ReAct agent without branching logic.
- Moving averages are calculated strictly on trailing close prices available up to bar `t`, strictly preserving point-in-time causality without look-ahead bias.
- Baseline runs record zero LLM tokens and $0.00 cost, providing a cost-normalized baseline comparison for the agent.
