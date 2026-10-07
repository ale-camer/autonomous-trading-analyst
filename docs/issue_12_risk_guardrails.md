# Issue 12: Deterministic Risk Guardrails

**Branch**: `feature/issue-12-risk-guardrails`
**Status**: To Do
**PR**: opened by `make finish-issue` → `develop` (Closes #12)
**Milestone**: M3 - Risk, Paper Trading & Memory

## Objective
Implement the deterministic `RiskManager` module outside the LLM. The risk manager acts as an unbypassable gatekeeper evaluating proposed trades against strict risk rules: maximum position size, maximum gross exposure, stop-loss threshold, daily trade frequency limit, watchlist restriction, and prohibition of shorting or leverage. It deterministically approves, resizes, or rejects orders with explicit audit reasons.

## Acceptance Criteria
- [x] `src/autonomous_trading_analyst/risk/manager.py` implements `RiskManager` with strict rule evaluation and explicit reason reporting.
- [x] Enforces `risk_max_position_pct` from `Settings` by resizing or rejecting BUY orders exceeding the ticker equity limit.
- [x] Enforces `risk_max_gross_exposure_pct` from `Settings` and prohibits leverage exceeding portfolio cash/equity bounds.
- [x] Prohibits shorting by rejecting SELL orders without positions and resizing SELL orders exceeding held shares.
- [x] Enforces watchlist restriction, rejecting any order for tickers not configured in `settings.watchlist`.
- [x] Enforces `risk_max_trades_per_day` from `Settings`, rejecting any order once the daily quota is reached.
- [x] Provides `check_stop_losses` generating exit SELL orders when unrealized losses breach `risk_stop_loss_pct`.
- [x] `src/autonomous_trading_analyst/risk/__init__.py` re-exports `RiskManager`.
- [x] `tests/unit/test_risk_manager.py` covers all guardrails (approval, resizing, rejection, stop-loss sweep) marked `@pytest.mark.issue_12`.
- [x] `pyproject.toml` registers the `issue_12` marker.
- [x] `make check` and `make test-issue ID=12` pass.

## Implementation Tasks

### 1. Preparation & Branching
```bash
make start-issue ID=12 NAME=risk-guardrails
```

### 2. Risk Manager Implementation
- **File**: `src/autonomous_trading_analyst/risk/manager.py`
- **Change**: Implement `RiskManager`:
  - `__init__(self, settings: Settings | None = None)`: Loads configured settings.
  - `evaluate_order(order: Order, portfolio: PortfolioState, current_price: float, trades_today: int = 0) -> Order`:
    - Checks watchlist inclusion: rejects if ticker is outside `settings.watchlist`.
    - Checks daily trade limits: rejects if `trades_today >= settings.risk_max_trades_per_day`.
    - Checks no-shorting: for `Action.SELL`, rejects if held shares is 0; resizes to `held_shares` if requested shares exceed holdings.
    - Checks position limit (`risk_max_position_pct`): for `Action.BUY`, resizes or rejects if proposed market value pushes position over limit.
    - Checks gross exposure limit (`risk_max_gross_exposure_pct`): for `Action.BUY`, resizes or rejects if proposed value pushes total gross exposure or cash beyond limits.
    - Returns updated `Order` with final `status` (`APPROVED`, `RESIZED`, `REJECTED`) and explanatory `reason`.
  - `evaluate_signal(signal: Signal | TradingSignal, portfolio: PortfolioState, current_price: float, trades_today: int = 0) -> Order | None`:
    - Translates an agent signal into a proposed `Order` and calls `evaluate_order`. Returns `None` for `HOLD`.
  - `check_stop_losses(portfolio: PortfolioState, current_prices: dict[str, float]) -> list[Order]`:
    - Inspects open positions; generates approved `SELL` orders for positions where unrealized loss breaches `settings.risk_stop_loss_pct`.

### 3. Risk Package Interface
- **File**: `src/autonomous_trading_analyst/risk/__init__.py`
- **Change**: Re-export `RiskManager`.

### 4. Unit Tests
- **File**: `tests/unit/test_risk_manager.py`
- **Change**: Write comprehensive unit tests:
  - Watchlist-only rejection.
  - Daily trade limit rejection.
  - No-shorting rejection and resizing to held shares.
  - Position size limit approval, resizing, and rejection.
  - Gross exposure and cash constraints.
  - Stop-loss detection and order generation.
  - Signal evaluation integration.
  Mark tests with `@pytest.mark.issue_12`.

### 5. Pytest Marker Registration
- **File**: `pyproject.toml`
- **Change**: Add the `issue_12: Deterministic risk guardrails` marker under `[tool.pytest.ini_options]` `markers`.

### 6. Verification & Quality Gates
```bash
make test-issue ID=12
make check
```

### 7. Git & Issue Finish
```bash
make finish-issue ID=12 MSG="feat(risk): implement deterministic risk manager and guardrails"
```

## Decisions
- The risk guardrails are strictly deterministic and isolated from the LLM prompt. The LLM agent can only propose signals, while `RiskManager` holds final execution authority, preventing hallucinations or prompt injections from executing illegal or dangerous trades.
- Orders are resized downward whenever possible instead of outright rejected, allowing the portfolio to capture partial allocations within approved risk parameters.
