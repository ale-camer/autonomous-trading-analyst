# Issue 5: Anomaly Signals (P-06 Style)

**Branch**: `feature/issue-5-anomaly-signals`
**Status**: Done
**PR**: opened by `make finish-issue` → `develop` (Closes #5)
**Milestone**: M1 - Foundations & Market Tools

## Objective
Implement statistical market anomaly detection (P-06 style) for volume spikes, extreme price jumps, and volatility expansions to equip the ReAct agent with quantitative outlier detection tools.

## Acceptance Criteria
- [x] `src/autonomous_trading_analyst/tools/anomalies/models.py` defines typed Pydantic models (`AnomalyType`, `AnomalySeverity`, `AnomalyEvent`, `AnomalyReport`)
- [x] `src/autonomous_trading_analyst/tools/anomalies/detector.py` implements `AnomalyDetector` detecting volume spikes, return jumps, and volatility expansions via rolling z-scores and ATR multiples
- [x] `src/autonomous_trading_analyst/tools/anomalies/__init__.py` re-exports anomaly detector, helper routines, and data models
- [x] `tests/unit/test_anomalies.py` validates detection across normal conditions, volume surges, sudden price shocks, volatility expansions, and edge cases (marked `@pytest.mark.issue_5`)
- [x] `pyproject.toml` registers the `issue_5` marker
- [x] `make check` and `make test-issue ID=5` pass

## Implementation Tasks

### 1. Preparation & Branching
```bash
make start-issue ID=5 NAME=anomaly-signals
```

### 2. Anomaly Signal Data Models
- **File**: `src/autonomous_trading_analyst/tools/anomalies/models.py`
- **Change**: Define typed Pydantic models: `AnomalyType` (VOLUME_SPIKE, PRICE_JUMP, VOLATILITY_EXPANSION), `AnomalySeverity` (LOW, MEDIUM, HIGH), `AnomalyEvent` (type, score, threshold, severity, description), and `AnomalyReport` (ticker, timestamp, is_anomaly, anomalies, summary).

### 3. Statistical Anomaly Detector
- **File**: `src/autonomous_trading_analyst/tools/anomalies/detector.py`
- **Change**: Implement `AnomalyDetector` class with configurable lookback windows and z-score thresholds (volume z-score, return z-score, range vs ATR expansion). Include `detect_anomalies(df: pd.DataFrame, ticker: str = "") -> AnomalyReport` convenience function with input validation.

### 4. Anomaly Package Interface
- **File**: `src/autonomous_trading_analyst/tools/anomalies/__init__.py`
- **Change**: Re-export `AnomalyType`, `AnomalySeverity`, `AnomalyEvent`, `AnomalyReport`, `AnomalyDetector`, and `detect_anomalies`.

### 5. Unit Tests for Anomaly Signals
- **File**: `tests/unit/test_anomalies.py`
- **Change**: Implement unit tests verifying baseline behavior on normal series, positive anomaly detection on injected volume surges, extreme return jumps, volatility expansions, threshold customizability, and empty/insufficient data handling. Mark with `@pytest.mark.issue_5`.

### 6. Pytest Marker Registration
- **File**: `pyproject.toml`
- **Change**: Register the `issue_5` marker (`issue_5: Anomaly signals (P-06 style)`) under `[tool.pytest.ini_options]` `markers`.

### 7. Verification & Quality Gates
```bash
make test-issue ID=5
make check
```

### 8. Git & Issue Finish
```bash
make finish-issue ID=5 MSG="feat(anomalies): implement statistical anomaly signal detector"
```

## Decisions
- Use rolling statistical z-scores (lookback window = 20) for volume and returns, alongside true range vs ATR ratios for volatility, providing normalized, asset-agnostic anomaly signals.
- Assign severity ratings (LOW: z > 2.0, MEDIUM: z > 3.0, HIGH: z > 4.0) to allow the ReAct agent to gauge statistical urgency and risk.
- Return clean `AnomalyReport` containing a human-readable summary so the agent can directly quote observation rationale (e.g., "Volume spike detected: z=3.8").
