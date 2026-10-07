# Issue 4: Technical Indicators

**Branch**: `feature/issue-4-technical-indicators`
**Status**: Done
**PR**: opened by `make finish-issue` → `develop` (Closes #4)
**Milestone**: M1 - Foundations & Market Tools

## Objective
Implement a robust suite of technical indicators (SMA, EMA, RSI, MACD, Bollinger Bands, ATR) and an indicator snapshot generator built on pandas and numpy to supply deterministic quantitative signals to the ReAct agent.

## Acceptance Criteria
- [x] `src/autonomous_trading_analyst/tools/indicators/models.py` defines typed Pydantic models (`MACDResult`, `BollingerBandsResult`, `TechnicalIndicatorsSnapshot`)
- [x] `src/autonomous_trading_analyst/tools/indicators/calculations.py` implements SMA, EMA, RSI (Wilder's smoothing), MACD, Bollinger Bands, and ATR
- [x] `src/autonomous_trading_analyst/tools/indicators/__init__.py` exposes `compute_technical_indicators` and calculation functions
- [x] `tests/unit/test_indicators.py` validates mathematical accuracy, edge cases (insufficient bars, flat prices), and snapshot generation (marked `@pytest.mark.issue_4`)
- [x] `pyproject.toml` registers the `issue_4` marker
- [x] `make check` and `make test-issue ID=4` pass

## Implementation Tasks

### 1. Preparation & Branching
```bash
make start-issue ID=4 NAME=technical-indicators
```

### 2. Technical Indicators Data Models
- **File**: `src/autonomous_trading_analyst/tools/indicators/models.py`
- **Change**: Define typed Pydantic models: `MACDResult` (macd, signal, histogram), `BollingerBandsResult` (upper, middle, lower, bandwidth, percent_b), and `TechnicalIndicatorsSnapshot` containing latest calculated values (close, rsi_14, sma_20, sma_50, sma_200, ema_12, ema_26, macd, bollinger, atr_14) and timestamp.

### 3. Core Technical Indicator Calculations
- **File**: `src/autonomous_trading_analyst/tools/indicators/calculations.py`
- **Change**: Implement pure pandas/numpy functions for `compute_sma`, `compute_ema`, `compute_rsi` (Wilder's smoothing), `compute_macd`, `compute_bollinger_bands`, and `compute_atr`. Include input validation for required OHLCV columns and graceful handling of series with NaNs or insufficient length.

### 4. Snapshot Generator & Package Interface
- **File**: `src/autonomous_trading_analyst/tools/indicators/__init__.py`
- **Change**: Implement `compute_technical_indicators(df: pd.DataFrame) -> TechnicalIndicatorsSnapshot` and re-export all calculation functions and result models.

### 5. Unit Tests for Technical Indicators
- **File**: `tests/unit/test_indicators.py`
- **Change**: Implement unit tests verifying RSI values (0-100 range, overbought/oversold levels), MACD signals and crossovers, SMA/EMA accuracy, Bollinger Band envelope integrity, ATR volatility calculations, and edge cases (empty or short dataframes, all-equal prices). Mark with `@pytest.mark.issue_4`.

### 6. Pytest Marker Registration
- **File**: `pyproject.toml`
- **Change**: Register the `issue_4` marker (`issue_4: Technical indicators`) under `[tool.pytest.ini_options]` `markers`.

### 7. Verification & Quality Gates
```bash
make test-issue ID=4
make check
```

### 8. Git & Issue Finish
```bash
make finish-issue ID=4 MSG="feat(indicators): implement technical indicators suite and snapshot generator"
```

## Decisions
- Implement indicators using native pandas and numpy without external TA libraries to minimize dependencies and maintain full control over numerical accuracy and type safety.
- Use Wilder's exponential smoothing method for RSI and ATR, adhering to standard financial market convention.
- Provide a unified `TechnicalIndicatorsSnapshot` returning the latest scalar values for easy consumption by ReAct agent prompts and tools.
