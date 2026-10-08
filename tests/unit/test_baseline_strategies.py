"""Unit tests for baseline trading strategies and simulation runner."""

from datetime import UTC, datetime, timedelta

import pandas as pd
import pytest

from autonomous_trading_analyst.config import Settings
from autonomous_trading_analyst.domain.models import Action, PortfolioState, Position
from autonomous_trading_analyst.evaluation.baselines import (
    BuyAndHoldStrategy,
    SMACrossoverStrategy,
    run_baseline_simulation,
)
from autonomous_trading_analyst.evaluation.models import PerformanceMetrics
from autonomous_trading_analyst.risk.manager import RiskManager


@pytest.mark.issue_19
def test_buy_and_hold_parameter_validation_and_properties() -> None:
    """BuyAndHoldStrategy validates allocation fraction and reports correct name."""
    strategy = BuyAndHoldStrategy(allocation_pct=0.5)
    assert strategy.name == "buy_and_hold"
    assert strategy.allocation_pct == 0.5

    with pytest.raises(ValueError, match="allocation_pct must be between"):
        BuyAndHoldStrategy(allocation_pct=0.0)

    with pytest.raises(ValueError, match="allocation_pct must be between"):
        BuyAndHoldStrategy(allocation_pct=1.5)


@pytest.mark.issue_19
def test_buy_and_hold_signal_generation() -> None:
    """BuyAndHoldStrategy emits BUY when uninvested and HOLD when position is open."""
    strategy = BuyAndHoldStrategy(allocation_pct=1.0)
    now = datetime.now(UTC)

    # 1. Uninvested portfolio with cash -> BUY
    empty_portfolio = PortfolioState.create(cash=10000.0, positions={})
    sig1 = strategy.generate_signal("AAPL", 150.0, empty_portfolio, as_of=now)
    assert sig1.ticker == "AAPL"
    assert sig1.action == Action.BUY
    assert sig1.size == 1.0
    assert sig1.citations == ["baseline:buy_and_hold"]

    # 2. Portfolio already holding shares -> HOLD
    invested_portfolio = PortfolioState.create(
        cash=0.0,
        positions={
            "AAPL": Position(
                ticker="AAPL",
                shares=66.0,
                average_entry_price=150.0,
                current_price=150.0,
            )
        },
    )
    sig2 = strategy.generate_signal("AAPL", 155.0, invested_portfolio, as_of=now)
    assert sig2.action == Action.HOLD
    assert sig2.size == 0.0

    # 3. Uninvested but zero cash -> HOLD
    broke_portfolio = PortfolioState.create(cash=0.0, positions={})
    sig3 = strategy.generate_signal("AAPL", 150.0, broke_portfolio, as_of=now)
    assert sig3.action == Action.HOLD


@pytest.mark.issue_19
def test_sma_crossover_parameter_validation_and_properties() -> None:
    """SMACrossoverStrategy validates windows, position size, and reports name."""
    strategy = SMACrossoverStrategy(fast_period=5, slow_period=20, size=0.8)
    assert strategy.name == "sma_crossover"
    assert strategy.fast_period == 5
    assert strategy.slow_period == 20
    assert strategy.size == 0.8

    with pytest.raises(ValueError, match="fast_period must be positive"):
        SMACrossoverStrategy(fast_period=0, slow_period=20)

    with pytest.raises(ValueError, match=r"slow_period .* must be strictly greater"):
        SMACrossoverStrategy(fast_period=20, slow_period=20)

    with pytest.raises(ValueError, match="size must be between"):
        SMACrossoverStrategy(fast_period=5, slow_period=20, size=0.0)


@pytest.mark.issue_19
def test_sma_crossover_warmup_and_insufficient_history() -> None:
    """SMACrossoverStrategy emits HOLD when price history is shorter than slow_period."""
    strategy = SMACrossoverStrategy(fast_period=5, slow_period=10)
    portfolio = PortfolioState.create(cash=10000.0, positions={})

    # Only 5 bars provided (< 10 slow_period)
    prices = pd.Series([100.0, 101.0, 102.0, 103.0, 104.0])
    sig = strategy.generate_signal("AAPL", 104.0, portfolio, price_history=prices)

    assert sig.action == Action.HOLD
    assert sig.size == 0.0
    assert "Insufficient price history" in sig.rationale
    assert sig.citations == ["baseline:sma_crossover:warmup"]


@pytest.mark.issue_19
def test_sma_crossover_golden_and_death_cross() -> None:
    """SMACrossoverStrategy detects golden cross (BUY) and death cross (SELL)."""
    fast = 3
    slow = 6
    strategy = SMACrossoverStrategy(fast_period=fast, slow_period=slow)

    # 6 bars flat at 100.0 (warmup completed, fast=100, slow=100)
    warmup = [100.0] * 6
    # Ramp prices to trigger golden cross (fast SMA rises above slow SMA)
    bull_prices = pd.Series([*warmup, 110.0, 120.0])

    empty_port = PortfolioState.create(cash=10000.0, positions={})
    # Bar 7: price 110.0 -> fast SMA = (100+100+110)/3 = 103.33, slow SMA = 101.67 -> Golden cross
    sig_buy = strategy.generate_signal(
        "AAPL", 110.0, empty_port, price_history=bull_prices.iloc[:7]
    )

    assert sig_buy.action == Action.BUY
    assert sig_buy.size == 1.0
    assert "Golden cross detected" in sig_buy.rationale
    assert sig_buy.citations == ["baseline:sma_crossover:golden_cross"]

    # When already holding position and fast remains above slow -> HOLD
    long_port = PortfolioState.create(
        cash=0.0,
        positions={
            "AAPL": Position(
                ticker="AAPL",
                shares=10.0,
                average_entry_price=110.0,
                current_price=120.0,
            )
        },
    )
    sig_hold = strategy.generate_signal("AAPL", 120.0, long_port, price_history=bull_prices)
    assert sig_hold.action == Action.HOLD

    # Now drop prices sharply to trigger death cross (fast SMA drops below slow SMA)
    bear_prices = pd.Series([*list(bull_prices), 80.0, 70.0])
    # At 70.0: fast SMA is significantly below slow SMA
    sig_sell = strategy.generate_signal("AAPL", 70.0, long_port, price_history=bear_prices)

    assert sig_sell.action == Action.SELL
    assert sig_sell.size == 1.0
    assert "Death cross detected" in sig_sell.rationale
    assert sig_sell.citations == ["baseline:sma_crossover:death_cross"]


@pytest.mark.issue_19
def test_sma_crossover_point_in_time_safety() -> None:
    """Signal generation respects as_of timestamp and does not look ahead to future bars."""
    strategy = SMACrossoverStrategy(fast_period=3, slow_period=5)
    port = PortfolioState.create(cash=10000.0, positions={})

    base = datetime(2026, 1, 1, tzinfo=UTC)
    dates = [base + timedelta(days=i) for i in range(10)]
    # First 6 bars: flat at 100. Bar 7..9: massive pump to 200
    prices_data = [100.0] * 6 + [150.0, 180.0, 200.0, 220.0]
    full_series = pd.Series(prices_data, index=pd.DatetimeIndex(dates))

    # Evaluate at index 3 (4 bars) - should be warmup (< 5 bars)
    as_of_t3 = dates[3]
    sig_t3 = strategy.generate_signal(
        "AAPL",
        100.0,
        port,
        price_history=full_series,
        as_of=as_of_t3,
    )
    assert sig_t3.action == Action.HOLD
    assert "Insufficient price history" in sig_t3.rationale

    # Evaluate at index 4 (5 bars) - exactly 5 bars warmup completed, flat at 100
    as_of_t4 = dates[4]
    sig_t4 = strategy.generate_signal(
        "AAPL",
        100.0,
        port,
        price_history=full_series,
        as_of=as_of_t4,
    )
    assert sig_t4.action == Action.HOLD
    assert "No crossover" in sig_t4.rationale

    # Evaluate at index 6 (price 150) - golden cross detected point-in-time
    as_of_t6 = dates[6]
    sig_t6 = strategy.generate_signal(
        "AAPL",
        150.0,
        port,
        price_history=full_series,
        as_of=as_of_t6,
    )
    assert sig_t6.action == Action.BUY
    assert "Golden cross detected" in sig_t6.rationale


@pytest.mark.issue_19
def test_run_baseline_simulation_buy_and_hold() -> None:
    """Simulation runner executes Buy & Hold on PaperBroker, producing accurate metrics."""
    strategy = BuyAndHoldStrategy(allocation_pct=1.0)
    prices = [100.0, 105.0, 110.0, 115.0, 120.0]

    broker, metrics = run_baseline_simulation(
        strategy=strategy,
        ticker="AAPL",
        price_history=prices,
        initial_cash=10000.0,
    )

    assert isinstance(metrics, PerformanceMetrics)
    # Exactly one initial BUY fill
    assert len(broker.fills) == 1
    assert broker.fills[0].action == Action.BUY
    # Buy & hold didn't sell, so total closed round-trip trades is 0
    assert metrics.total_trades == 0
    assert metrics.total_return > 0.15  # ~20% price gain minus slippage/fees
    assert metrics.start_equity == 10000.0
    assert metrics.end_equity > 11500.0
    # Zero LLM costs
    assert metrics.total_decisions == 0
    assert metrics.total_cost_usd == 0.0
    assert metrics.total_tokens == 0


@pytest.mark.issue_19
def test_run_baseline_simulation_sma_crossover_roundtrip() -> None:
    """Simulation runner executes SMA crossover, closing a trade and recording metrics."""
    strategy = SMACrossoverStrategy(fast_period=3, slow_period=5)

    # 5 bars warmup (100) -> 3 bars pump (110, 120, 130) -> 3 bars dump (90, 80, 70)
    prices = [100.0, 100.0, 100.0, 100.0, 100.0, 110.0, 120.0, 130.0, 90.0, 80.0, 70.0]

    broker, metrics = run_baseline_simulation(
        strategy=strategy,
        ticker="TSLA",
        price_history=prices,
        initial_cash=10000.0,
    )

    # Should execute BUY on pump and SELL on dump
    assert len(broker.fills) == 2
    assert broker.fills[0].action == Action.BUY
    assert broker.fills[1].action == Action.SELL

    # Closed round-trip trade
    assert metrics.total_trades == 1
    assert metrics.total_decisions == 0
    assert metrics.total_cost_usd == 0.0


@pytest.mark.issue_19
def test_run_baseline_simulation_with_risk_manager() -> None:
    """Simulation adheres to RiskManager position size guardrails and settings."""
    settings = Settings(
        watchlist=["MSFT"],
        risk_max_position_pct=0.20,  # Max 20% allocation per position
    )
    risk_manager = RiskManager(settings=settings)
    strategy = BuyAndHoldStrategy(allocation_pct=1.0)
    prices = [100.0, 102.0, 104.0]

    broker, metrics = run_baseline_simulation(
        strategy=strategy,
        ticker="MSFT",
        price_history=prices,
        risk_manager=risk_manager,
        initial_cash=10000.0,
    )

    # Order should have been resized from 100% to max position size 20%
    assert len(broker.fills) == 1
    fill = broker.fills[0]
    # At $100 price, 20% of 10000 = $2000 -> approx 20 shares
    assert 19.0 <= fill.shares <= 20.5
    assert metrics.start_equity == 10000.0


@pytest.mark.issue_19
def test_run_baseline_simulation_empty_series() -> None:
    """Simulation runner handles empty price series gracefully."""
    strategy = BuyAndHoldStrategy()
    broker, metrics = run_baseline_simulation(
        strategy=strategy,
        ticker="AAPL",
        price_history=[],
        initial_cash=5000.0,
    )
    assert broker.cash == 5000.0
    assert metrics.start_equity == 0.0
    assert metrics.total_trades == 0
