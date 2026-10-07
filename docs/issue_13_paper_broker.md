# Issue 13: Paper Broker & Portfolio Accounting

**Branch**: `feature/issue-13-paper-broker`
**Status**: To Do
**PR**: opened by `make finish-issue` → `develop` (Closes #13)
**Milestone**: M3 - Risk, Paper Trading & Memory

## Objective
Implement `PaperBroker`, the singular simulated execution venue for the system. The paper broker is responsible for executing approved or resized orders under realistic market conditions by applying configurable slippage and commission models. It manages cash, maintains open positions with weighted average entry prices, tracks realized and unrealized PnL, performs mark-to-market revaluations, and preserves an audit trail of fills and portfolio state snapshots.

## Acceptance Criteria
- [x] `src/autonomous_trading_analyst/broker/paper.py` implements `PaperBroker` managing cash, positions, order execution, and portfolio state snapshots.
- [x] Applies configured slippage (`paper_slippage_bps`) to execution prices (adverse to trader: higher on BUY, lower on SELL).
- [x] Applies configured commissions (`paper_commission_bps`) deducted from cash on every fill.
- [x] Updates weighted average entry price on BUY and calculates realized PnL on SELL.
- [x] Disallows executing unapproved or rejected orders (`PENDING`, `REJECTED`, `CANCELLED`).
- [x] Implements `mark_to_market(current_prices)` updating position current prices, unrealized PnL, total equity, and gross exposure.
- [x] Maintains historical records of all executed `Fill`s and `PortfolioState` snapshots.
- [x] `src/autonomous_trading_analyst/broker/__init__.py` re-exports `PaperBroker`.
- [x] `tests/unit/test_paper_broker.py` covers order execution (BUY, SELL, partial sell, position closure), slippage, commission, PnL accounting, and mark-to-market updates (marked `@pytest.mark.issue_13`).
- [x] `pyproject.toml` registers the `issue_13` marker.
- [x] `make check` and `make test-issue ID=13` pass.

## Implementation Tasks

### 1. Preparation & Branching
```bash
make start-issue ID=13 NAME=paper-broker
```

### 2. Paper Broker Core Implementation
- **File**: `src/autonomous_trading_analyst/broker/paper.py`
- **Change**: Implement `PaperBroker`:
  - `__init__(self, settings: Settings | None = None, initial_cash: float | None = None)`: Initializes cash balance (defaulting to `settings.paper_initial_cash`), positions map, and history.
  - `get_portfolio_state() -> PortfolioState`: Returns the current immutable snapshot of portfolio cash, positions, total equity, and gross exposure.
  - `execute_order(order: Order, market_price: float) -> Fill | None`:
    - Validates order eligibility: only `OrderStatus.APPROVED` and `OrderStatus.RESIZED` are executed. Returns `None` for invalid or rejected orders.
    - Computes execution price with slippage:
      - BUY: `market_price * (1 + slippage_bps / 10000)`
      - SELL: `market_price * (1 - slippage_bps / 10000)`
    - Computes commission: `shares * exec_price * (commission_bps / 10000)`.
    - Updates cash: debits `(shares * exec_price) + commission` on BUY; credits `(shares * exec_price) - commission` on SELL.
    - Updates `Position`:
      - BUY: updates shares and computes new weighted average entry price.
      - SELL: reduces shares, records realized PnL against cost basis, and removes position if shares reach zero.
    - Creates and records `Fill` with execution details and timestamp.
    - Returns the `Fill`.
  - `mark_to_market(current_prices: dict[str, float]) -> PortfolioState`:
    - Updates `current_price` and `unrealized_pnl` for all active positions based on latest prices.
    - Captures and records a new `PortfolioState` snapshot.
    - Returns the updated `PortfolioState`.
  - Properties & Queries: `cash`, `positions`, `fills`, `history`, `total_equity`, `realized_pnl`.

### 3. Broker Package Interface
- **File**: `src/autonomous_trading_analyst/broker/__init__.py`
- **Change**: Re-export `PaperBroker`.

### 4. Unit Tests
- **File**: `tests/unit/test_paper_broker.py`
- **Change**: Write comprehensive unit tests:
  - Initial state and portfolio equity.
  - BUY execution: cash deduction, position creation, weighted average entry calculation on repeated buys.
  - SELL execution: cash addition, realized PnL computation, position reduction and complete closure.
  - Commission and slippage verification against exact bps formulas.
  - Rejection of unapproved/rejected orders and non-positive prices.
  - Mark-to-market updates across multiple price ticks.
  Mark tests with `@pytest.mark.issue_13`.

### 5. Pytest Marker Registration
- **File**: `pyproject.toml`
- **Change**: Add the `issue_13: Paper broker & portfolio accounting` marker under `[tool.pytest.ini_options]` `markers`.

### 6. Verification & Quality Gates
```bash
make test-issue ID=13
make check
```

### 7. Git & Issue Finish
```bash
make finish-issue ID=13 MSG="feat(broker): implement paper broker and portfolio accounting"
```

## Decisions
- The paper broker is the only execution venue in the system; live exchange connections are deliberately omitted to ensure strict, safe simulation and backtesting parity.
- Slippage is modeled symmetrically adverse to the trader (higher on buys, lower on sells) in basis points, reflecting realistic bid/ask spread and market impact without external exchange dependencies.
- Realized PnL is tracked per position and across the broker, while commissions are treated as immediate transaction costs reducing net cash proceeds.
