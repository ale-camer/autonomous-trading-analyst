# Issue 21: Backtest Report & CLI

**Branch**: `feature/issue-21-backtest-report`
**Status**: Done
**PR**: opened by `make finish-issue` → `develop` (Closes #21)
**Milestone**: M4 - Evaluation & Backtesting (Closes M4)

## Objective
Implement quantitative reporting modules and a CLI entry point for backtesting in `evaluation/`. The reporting engine generates comprehensive Markdown comparison tables and machine-readable JSON reports evaluating the autonomous agent side-by-side against baseline strategies (`Buy & Hold` and `SMA Crossover`) across returns, Sharpe/Sortino/Calmar ratios, max drawdown, win rate, and LLM cost/tokens per decision. The CLI tool exposes an executable entry point (`backtest` / `python -m autonomous_trading_analyst.evaluation.cli`) allowing parameterized backtests from the terminal.

## Acceptance Criteria
- [x] `src/autonomous_trading_analyst/evaluation/report.py` implements `generate_markdown_report`, `generate_json_report`, and `export_report` formatting `BacktestResult` into comparative tables and JSON structures.
- [x] Markdown report displays side-by-side comparative metrics: Start/End Equity, Total Return, CAGR, Volatility, Sharpe, Sortino, Max Drawdown and Duration, Calmar, Total Trades, Win Rate, Profit Factor, Average Trade PnL, Total Decisions, Tokens, and Total/Average USD Cost.
- [x] `src/autonomous_trading_analyst/evaluation/cli.py` implements CLI argument parsing (`--watchlist`, `--start-date`, `--end-date`, `--initial-cash`, `--output`, `--format`, `--provider`), executes backtests, prints summaries, and exports reports.
- [x] `pyproject.toml` registers console script `backtest = "autonomous_trading_analyst.evaluation.cli:main"` and the `issue_21` pytest marker.
- [x] `src/autonomous_trading_analyst/evaluation/__init__.py` re-exports reporting functions.
- [x] `tests/unit/test_backtest_report.py` validates Markdown table formatting, JSON serialization/deserialization, file exports, and CLI argument parsing/execution (marked `@pytest.mark.issue_21`).
- [x] `make check` and `make test-issue ID=21` pass.

## Implementation Tasks

### 1. Preparation & Branching
```bash
make start-issue ID=21 NAME=backtest-report
```

### 2. Backtest Report Generation
- **File**: `src/autonomous_trading_analyst/evaluation/report.py`
- **Change**: Implement reporting functions:
  - `generate_markdown_report(result: BacktestResult) -> str`: creates formatted Markdown report with an executive comparison table (Agent vs Buy & Hold vs SMA Crossover), financial performance summary, trade statistics, and LLM cost/token efficiency analysis.
  - `generate_json_report(result: BacktestResult, indent: int = 2) -> str`: produces formatted JSON containing all metrics, configurations, timestamps, and equity curves.
  - `export_report(result: BacktestResult, output_path: str | Path, format: str = "markdown") -> Path`: writes generated Markdown or JSON report to disk.

### 3. Backtest CLI Entry Point
- **File**: `src/autonomous_trading_analyst/evaluation/cli.py`
- **Change**: Implement CLI script:
  - `parse_args(args: Sequence[str] | None = None) -> argparse.Namespace`: parses `--watchlist`, `--start-date`, `--end-date`, `--initial-cash`, `--output`, `--format`, `--provider`, `--risk-free-rate`.
  - `main(args: Sequence[str] | None = None) -> int`: orchestrates configuration, instantiates `create_backtest_engine`, executes backtest, prints summary to stdout, and optionally saves output files.
  - Supports `python -m autonomous_trading_analyst.evaluation.cli` execution.

### 4. Package Exports & CLI Console Script
- **File**: `src/autonomous_trading_analyst/evaluation/__init__.py`
- **Change**: Re-export `generate_markdown_report`, `generate_json_report`, `export_report`, and `cli_main`.
- **File**: `pyproject.toml`
- **Change**: Add `[project.scripts]` section registering `backtest = "autonomous_trading_analyst.evaluation.cli:main"`.

### 5. Unit & CLI Tests
- **File**: `tests/unit/test_backtest_report.py`
- **Change**: Write comprehensive tests:
  - Markdown report generation: checks table structure, presence of metrics for agent and baselines, percentage/currency formatting.
  - JSON report generation: validates JSON validity and schema completeness.
  - File exporting: validates saving `.md` and `.json` reports to temporary directories.
  - CLI execution: tests invocation with custom args, stdout reporting, file output generation, and error handling for invalid dates/parameters.
  Mark tests with `@pytest.mark.issue_21`.

### 6. Pytest Marker Registration
- **File**: `pyproject.toml`
- **Change**: Add `issue_21: Backtest report & CLI` marker under `[tool.pytest.ini_options]` `markers`.

### 7. Verification & Quality Gates
```bash
make test-issue ID=21
make check
```

### 8. Git & Issue Finish
```bash
make finish-issue ID=21 MSG="feat(evaluation): implement backtest comparative report and cli"
```

### 9. Milestone Finish (Closes M4)
```bash
make finish-milestone MILESTONE=M4
```

## Decisions
- Markdown reports format percentages and monetary amounts with standard rounding (e.g. 2 decimal places for currency, 2 decimal places for returns/volatility, 4 decimal places for Sharpe/Sortino/profit factor) to ensure clean readability across terminal viewers and markdown renderers.
- The CLI defaults to the deterministic fake market data provider unless explicitly overridden, ensuring fast, reproducible runs without external network dependencies.
- Both Markdown and JSON report formats are supported to enable human readability as well as programmatic ingestion by downstream visualization or CI systems.
