# Issue 3: Market Data Provider (Yahoo + Fake)

**Branch**: `feature/issue-3-market-data-provider`
**Status**: Done
**PR**: opened by `make finish-issue` → `develop` (Closes #3)
**Milestone**: M1 - Foundations & Market Tools

## Objective
Implement a unified market data abstraction (`MarketDataProvider`) with a live Yahoo Finance implementation (`yfinance`) and a deterministic, offline `FakeMarketDataProvider` for retrieving historical OHLCV price bars and latest price quotes.

## Acceptance Criteria
- [x] `src/autonomous_trading_analyst/tools/market_data/base.py` defines `Bar` model, exception classes, and abstract `MarketDataProvider` with `get_bars` and `get_latest_price`
- [x] `src/autonomous_trading_analyst/tools/market_data/fake.py` implements `FakeMarketDataProvider` supporting seeded bars and deterministic synthetic data for offline testing
- [x] `src/autonomous_trading_analyst/tools/market_data/yahoo.py` implements `YahooMarketDataProvider` with normalized lowercase columns, UTC timestamps, and error mapping
- [x] `src/autonomous_trading_analyst/tools/market_data/__init__.py` re-exports public models/providers and includes `get_market_data_provider` factory
- [x] `tests/unit/test_market_data.py` covers fake provider, mocked yahoo provider, and factory resolution (marked `@pytest.mark.issue_3`)
- [x] `pyproject.toml` registers the `issue_3` marker
- [x] `make check` and `make test-issue ID=3` pass

## Implementation Tasks

### 1. Preparation & Branching
```bash
make start-issue ID=3 NAME=market-data-provider
```

### 2. Market Data Interface and Data Models
- **File**: `src/autonomous_trading_analyst/tools/market_data/base.py`
- **Change**: Define `Bar` model (`timestamp`, `open`, `high`, `low`, `close`, `volume`), error classes (`MarketDataError`, `TickerNotFoundError`), and the abstract `MarketDataProvider` class defining abstract methods `get_bars(ticker: str, start: datetime | date, end: datetime | date, interval: str = "1d") -> pd.DataFrame` and `get_latest_price(ticker: str) -> float`.

### 3. Fake Market Data Provider
- **File**: `src/autonomous_trading_analyst/tools/market_data/fake.py`
- **Change**: Implement `FakeMarketDataProvider` adhering to `MarketDataProvider`. Support pre-seeding exact bars or latest prices for given tickers, and fallback to deterministic synthetic price generation (e.g. constant or linear trend) for arbitrary tickers when unseeded, enabling fully offline testing.

### 4. Yahoo Finance Market Data Provider
- **File**: `src/autonomous_trading_analyst/tools/market_data/yahoo.py`
- **Change**: Implement `YahooMarketDataProvider` using `yfinance` to download historical OHLCV data and fetch latest quotes. Normalize columns to lowercase (`open`, `high`, `low`, `close`, `volume`), ensure UTC index, and map missing data / upstream failures to `TickerNotFoundError` or `MarketDataError`.

### 5. Market Data Package Interface & Factory
- **File**: `src/autonomous_trading_analyst/tools/market_data/__init__.py`
- **Change**: Re-export `MarketDataProvider`, `YahooMarketDataProvider`, `FakeMarketDataProvider`, `Bar`, `MarketDataError`, and define factory `get_market_data_provider(provider_type: str | None = None)` that resolves provider based on `Settings.market_data_provider`.

### 6. Unit Tests for Market Data Providers
- **File**: `tests/unit/test_market_data.py`
- **Change**: Implement unit tests for `FakeMarketDataProvider` (custom seeded data, date range filtering, latest price) and `YahooMarketDataProvider` (mocked `yfinance` calls verifying column normalization, error handling, empty response detection). Test factory creation. Mark with `@pytest.mark.issue_3`.

### 7. Pytest Marker Registration
- **File**: `pyproject.toml`
- **Change**: Register the `issue_3` marker (`issue_3: Market data provider (Yahoo + fake)`) under `[tool.pytest.ini_options]` `markers`.

### 8. Verification & Quality Gates
```bash
make test-issue ID=3
make check
```

### 9. Git & Issue Finish
```bash
make finish-issue ID=3 MSG="feat(market-data): implement market data provider with yahoo and fake implementations"
```

## Decisions
- Standardize all OHLCV DataFrames with lowercase column names (`open`, `high`, `low`, `close`, `volume`) and UTC datetime index to guarantee compatibility across technical indicators and backtesting.
- `FakeMarketDataProvider` supports both explicit custom bar injection and deterministic synthetic data generation so tests can evaluate specific price scenarios (e.g. oversold dips, breakouts) without external dependencies.
- Unit tests for `YahooMarketDataProvider` use mocks to keep CI offline, fast, and deterministic.
- Add mypy overrides for `yfinance` and `pandas` (`ignore_missing_imports = true`) because neither library bundles PEP 561 `py.typed` markers in this environment.
