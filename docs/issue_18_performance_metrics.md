# Issue 18: Performance Metrics

**Branch**: `feature/issue-18-performance-metrics`
**Status**: Done
**PR**: opened by `make finish-issue` → `develop` (Closes #18)
**Milestone**: M4 - Evaluation & Backtesting

## Objective
Implement a quantitative performance metrics module in `evaluation/` to calculate standard financial and system metrics from equity curves, executed trade fills, and agent decisions. The module computes total return, annualized CAGR, volatility, Sharpe and Sortino ratios, maximum drawdown and duration, win rate, profit factor, and LLM cost/tokens per decision.

## Acceptance Criteria
- [x] `src/autonomous_trading_analyst/evaluation/models.py` defines `PerformanceMetrics` and `TradeRecord` typed domain models.
- [x] `src/autonomous_trading_analyst/evaluation/metrics.py` implements drawdown calculation, return series processing, trade extraction from fills, and full `compute_performance_metrics` calculation.
- [x] Supports inputs from pandas equity series, sequence of `PortfolioState` snapshots, list of `Fill` records, and list of `DecisionRecord` traces.
- [x] `src/autonomous_trading_analyst/evaluation/__init__.py` re-exports public metrics models and calculation functions.
- [x] `tests/unit/test_evaluation_metrics.py` validates flat, rising, declining, and volatile equity curves, trade win rate/profit factor calculations, edge cases (zero trades, zero volatility, single day), and LLM cost attribution (marked `@pytest.mark.issue_18`).
- [x] `pyproject.toml` registers the `issue_18` marker.
- [x] `make check` and `make test-issue ID=18` pass.

## Implementation Tasks

### 1. Preparation & Branching
```bash
make start-issue ID=18 NAME=performance-metrics
```

### 2. Evaluation Models
- **File**: `src/autonomous_trading_analyst/evaluation/models.py`
- **Change**: Define typed Pydantic models:
  - `TradeRecord`: `ticker: str`, `entry_time: datetime`, `exit_time: datetime`, `entry_price: float`, `exit_price: float`, `shares: float`, `pnl: float`, `return_pct: float`.
  - `PerformanceMetrics`: `start_equity: float`, `end_equity: float`, `total_return: float`, `annualized_return: float`, `annualized_volatility: float`, `sharpe_ratio: float`, `sortino_ratio: float`, `max_drawdown: float`, `max_drawdown_duration_days: int`, `calmar_ratio: float`, `total_trades: int`, `winning_trades: int`, `losing_trades: int`, `win_rate: float`, `profit_factor: float | None`, `average_trade_pnl: float`, `total_decisions: int`, `total_cost_usd: float`, `cost_per_decision: float`, `total_tokens: int`, `tokens_per_decision: float`.

### 3. Trade Extraction & Trade Metrics
- **File**: `src/autonomous_trading_analyst/evaluation/trades.py`
- **Change**: Implement:
  - `extract_trades_from_fills(fills: Sequence[Fill]) -> list[TradeRecord]`: parses BUY and SELL fills using FIFO matching per ticker to reconstruct closed round-trip trades with realized PnL and return percentages.
  - `compute_trade_statistics(trades: Sequence[TradeRecord]) -> dict[str, Any]`: computes win rate, profit factor, average win/loss, and trade counts.

### 4. Financial & System Metrics Calculation Engine
- **File**: `src/autonomous_trading_analyst/evaluation/metrics.py`
- **Change**: Implement:
  - `calculate_drawdowns(equity: pd.Series) -> tuple[pd.Series, float, int]`: computes high-water mark, drawdown series, peak maximum drawdown percentage, and longest drawdown duration in periods.
  - `compute_equity_metrics(equity: pd.Series | Sequence[PortfolioState] | Sequence[float], risk_free_rate: float = 0.0) -> dict[str, Any]`: calculates total return, annualized return (252 trading days), annualized volatility, Sharpe ratio, Sortino ratio, and Calmar ratio.
  - `compute_decision_metrics(decisions: Sequence[DecisionRecord]) -> dict[str, Any]`: calculates total decisions, total cost USD, average cost per decision, total tokens, and average tokens per decision.
  - `compute_performance_metrics(equity_curve: pd.Series | Sequence[PortfolioState] | Sequence[float], fills: Sequence[Fill] | None = None, decisions: Sequence[DecisionRecord] | None = None, risk_free_rate: float = 0.0) -> PerformanceMetrics`: unified orchestrator combining equity curve, trade history, and decision traces into a complete `PerformanceMetrics` object.

### 5. Package Exports
- **File**: `src/autonomous_trading_analyst/evaluation/__init__.py`
- **Change**: Re-export `PerformanceMetrics`, `TradeRecord`, `compute_performance_metrics`, `extract_trades_from_fills`, `calculate_drawdowns`.

### 6. Unit Tests
- **File**: `tests/unit/test_evaluation_metrics.py`
- **Change**: Write comprehensive unit tests covering:
  - Theoretical equity curves: constant growth (positive Sharpe), decline, volatile sideways, flat curve.
  - Drawdown calculation: peak-to-trough drop and recovery duration.
  - Trade matching from fills: single trade, multiple trades across tickers, partial executions, win rate and profit factor.
  - LLM cost and token aggregations across decision records.
  - Edge cases: empty fills, empty decisions, single-period equity, zero volatility (zero standard deviation).
  Mark tests with `@pytest.mark.issue_18`.

### 7. Pytest Marker Registration
- **File**: `pyproject.toml`
- **Change**: Add `issue_18: Performance metrics` marker under `[tool.pytest.ini_options]` `markers`.

### 8. Verification & Quality Gates
```bash
make test-issue ID=18
make check
```

### 9. Git & Issue Finish
```bash
make finish-issue ID=18 MSG="feat(evaluation): implement performance and risk metrics engine"
```

## Decisions
- Trade round-trips are extracted from fills using standard First-In-First-Out (FIFO) accounting per ticker, matching sell executions against previous open buy layers to calculate realized PnL per trade.
- Annualization assumes standard equity market calendar scaling (252 trading days per year) with compounding CAGR. When the evaluation series spans fewer than 2 periods or exhibits zero volatility, metrics default gracefully to 0.0 rather than raising division-by-zero exceptions.
- Profit factor is defined as gross profits divided by gross losses; if there are no losing trades, it returns `None` (or infinity representation) and is typed accordingly.
