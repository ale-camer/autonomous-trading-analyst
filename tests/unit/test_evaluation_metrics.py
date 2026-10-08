"""Unit tests for evaluation performance metrics and trade extraction engine."""

from datetime import UTC, datetime, timedelta

import pandas as pd
import pytest
from pydantic import ValidationError

from autonomous_trading_analyst.domain.models import (
    Action,
    DecisionRecord,
    Fill,
    PortfolioState,
    Signal,
    TraceStep,
)
from autonomous_trading_analyst.evaluation import (
    PerformanceMetrics,
    TradeRecord,
    calculate_drawdowns,
    compute_decision_metrics,
    compute_equity_metrics,
    compute_performance_metrics,
    compute_trade_statistics,
    extract_trades_from_fills,
)


@pytest.mark.issue_18
def test_trade_record_and_performance_metrics_immutability() -> None:
    """Evaluation models are immutable and reject unmapped fields."""
    now = datetime.now(UTC)
    record = TradeRecord(
        ticker="AAPL",
        entry_time=now,
        exit_time=now + timedelta(hours=1),
        entry_price=150.0,
        exit_price=155.0,
        shares=10.0,
        pnl=50.0,
        return_pct=0.0333,
        commission=1.0,
    )
    assert record.ticker == "AAPL"
    with pytest.raises(ValidationError):
        record.pnl = 100.0  # type: ignore[misc]

    with pytest.raises(ValidationError):
        TradeRecord(
            ticker="AAPL",
            entry_time=now,
            exit_time=now,
            entry_price=10.0,
            exit_price=11.0,
            shares=1.0,
            pnl=1.0,
            return_pct=0.1,
            extra_field="invalid",  # type: ignore[call-arg]
        )


@pytest.mark.issue_18
def test_calculate_drawdowns_peak_trough_and_duration() -> None:
    """Calculate high-water mark, drawdown percentages, and max drawdown duration."""
    equity = pd.Series([100.0, 120.0, 90.0, 110.0, 130.0])
    dd_series, max_dd, duration = calculate_drawdowns(equity)

    assert len(dd_series) == 5
    # Peak is 120.0, trough is 90.0 -> max_dd = (120 - 90) / 120 = 0.25 (25%)
    assert max_dd == 0.25
    # Below peak at index 2 (90.0) and index 3 (110.0), recovered at index 4 (130.0)
    assert duration == 2


@pytest.mark.issue_18
def test_calculate_drawdowns_empty_and_single_point() -> None:
    """Edge cases for empty or single-point equity curves handle gracefully."""
    empty_series = pd.Series(dtype=float)
    dd_empty, max_dd_empty, dur_empty = calculate_drawdowns(empty_series)
    assert dd_empty.empty
    assert max_dd_empty == 0.0
    assert dur_empty == 0

    single_series = pd.Series([1000.0])
    dd_single, max_dd_single, dur_single = calculate_drawdowns(single_series)
    assert len(dd_single) == 1
    assert max_dd_single == 0.0
    assert dur_single == 0


@pytest.mark.issue_18
def test_compute_equity_metrics_monotonic_growth() -> None:
    """Monotonic positive equity curve yields positive Sharpe and zero drawdown."""
    equity = [100.0, 102.0, 104.0, 106.0, 108.0, 110.0]
    metrics = compute_equity_metrics(equity)

    assert metrics["start_equity"] == 100.0
    assert metrics["end_equity"] == 110.0
    assert metrics["total_return"] == 0.10
    assert metrics["annualized_return"] > 0.0
    assert metrics["annualized_volatility"] > 0.0
    assert metrics["sharpe_ratio"] > 0.0
    assert metrics["sortino_ratio"] >= metrics["sharpe_ratio"]
    assert metrics["max_drawdown"] == 0.0
    assert metrics["max_drawdown_duration_days"] == 0


@pytest.mark.issue_18
def test_compute_equity_metrics_monotonic_decline() -> None:
    """Monotonic declining equity curve yields negative returns and non-zero drawdown."""
    equity = [100.0, 95.0, 90.0, 85.0]
    metrics = compute_equity_metrics(equity)

    assert metrics["total_return"] == -0.15
    assert metrics["annualized_return"] < 0.0
    assert metrics["sharpe_ratio"] < 0.0
    assert metrics["max_drawdown"] == 0.15
    assert metrics["max_drawdown_duration_days"] == 3


@pytest.mark.issue_18
def test_compute_equity_metrics_flat_curve() -> None:
    """Flat equity curve exhibits zero volatility without division-by-zero errors."""
    equity = [100.0, 100.0, 100.0, 100.0]
    metrics = compute_equity_metrics(equity)

    assert metrics["total_return"] == 0.0
    assert metrics["annualized_return"] == 0.0
    assert metrics["annualized_volatility"] == 0.0
    assert metrics["sharpe_ratio"] == 0.0
    assert metrics["sortino_ratio"] == 0.0
    assert metrics["max_drawdown"] == 0.0
    assert metrics["calmar_ratio"] == 0.0


@pytest.mark.issue_18
def test_compute_equity_metrics_empty_and_single() -> None:
    """Empty and single-period series return valid zeroed metric dictionaries."""
    empty_res = compute_equity_metrics([])
    assert empty_res["start_equity"] == 0.0
    assert empty_res["total_return"] == 0.0

    single_res = compute_equity_metrics([500.0])
    assert single_res["start_equity"] == 500.0
    assert single_res["end_equity"] == 500.0
    assert single_res["total_return"] == 0.0
    assert single_res["sharpe_ratio"] == 0.0


@pytest.mark.issue_18
def test_compute_equity_metrics_with_portfolio_states() -> None:
    """Accepts sequence of PortfolioState snapshots and parses datetime indices."""
    t0 = datetime(2026, 1, 1, tzinfo=UTC)
    t1 = datetime(2026, 1, 2, tzinfo=UTC)
    t2 = datetime(2026, 1, 3, tzinfo=UTC)

    states = [
        PortfolioState.create(cash=10000.0, positions={}, updated_at=t0),
        PortfolioState.create(cash=10200.0, positions={}, updated_at=t1),
        PortfolioState.create(cash=10500.0, positions={}, updated_at=t2),
    ]

    metrics = compute_equity_metrics(states)
    assert metrics["start_equity"] == 10000.0
    assert metrics["end_equity"] == 10500.0
    assert metrics["total_return"] == 0.05


@pytest.mark.issue_18
def test_extract_trades_fifo_matching_and_partial_lots() -> None:
    """FIFO matching parses partial layers, per-share commissions, and realized returns."""
    base_time = datetime(2026, 1, 1, 10, 0, tzinfo=UTC)
    fills = [
        # Buy 10 AAPL @ 150 (comm 1.50 -> 0.15/sh)
        Fill(
            fill_id="f1",
            order_id="o1",
            ticker="AAPL",
            action=Action.BUY,
            shares=10.0,
            price=150.0,
            commission=1.5,
            executed_at=base_time,
        ),
        # Buy 10 AAPL @ 160 (comm 1.50 -> 0.15/sh)
        Fill(
            fill_id="f2",
            order_id="o2",
            ticker="AAPL",
            action=Action.BUY,
            shares=10.0,
            price=160.0,
            commission=1.5,
            executed_at=base_time + timedelta(hours=1),
        ),
        # Sell 15 AAPL @ 170 (comm 3.00 -> 0.20/sh)
        Fill(
            fill_id="f3",
            order_id="o3",
            ticker="AAPL",
            action=Action.SELL,
            shares=15.0,
            price=170.0,
            commission=3.0,
            executed_at=base_time + timedelta(hours=2),
        ),
    ]

    trades = extract_trades_from_fills(fills)
    assert len(trades) == 2

    # First closed trade: all 10 shares from 1st buy @ 150 sold @ 170
    t1 = trades[0]
    assert t1.ticker == "AAPL"
    assert t1.shares == 10.0
    assert t1.entry_price == 150.0
    assert t1.exit_price == 170.0
    # Commission: (0.15 + 0.20) * 10 = 3.50
    assert t1.commission == 3.5
    # PnL: (170 - 150) * 10 - 3.5 = 196.5
    assert t1.pnl == 196.5
    # Return pct: 196.5 / 1500.0 = 0.131
    assert t1.return_pct == 0.131

    # Second closed trade: 5 shares from 2nd buy @ 160 sold @ 170
    t2 = trades[1]
    assert t2.ticker == "AAPL"
    assert t2.shares == 5.0
    assert t2.entry_price == 160.0
    assert t2.exit_price == 170.0
    # Commission: (0.15 + 0.20) * 5 = 1.75
    assert t2.commission == 1.75
    # PnL: (170 - 160) * 5 - 1.75 = 48.25
    assert t2.pnl == 48.25
    # Return pct: 48.25 / 800.0 = 0.060312 or ~0.060313
    assert round(t2.return_pct, 4) == 0.0603


@pytest.mark.issue_18
def test_extract_trades_multiple_symbols_and_unrealized_positions() -> None:
    """Interleaved fills across tickers are partitioned and unrealized shares ignored."""
    now = datetime.now(UTC)
    fills = [
        Fill(
            fill_id="f1",
            order_id="o1",
            ticker="NVDA",
            action=Action.BUY,
            shares=5.0,
            price=100.0,
            executed_at=now,
        ),
        Fill(
            fill_id="f2",
            order_id="o2",
            ticker="MSFT",
            action=Action.BUY,
            shares=10.0,
            price=300.0,
            executed_at=now + timedelta(minutes=1),
        ),
        Fill(
            fill_id="f3",
            order_id="o3",
            ticker="NVDA",
            action=Action.SELL,
            shares=5.0,
            price=110.0,
            executed_at=now + timedelta(minutes=2),
        ),
    ]

    trades = extract_trades_from_fills(fills)
    assert len(trades) == 1
    assert trades[0].ticker == "NVDA"
    assert trades[0].pnl == 50.0

    # Empty fills return empty list
    assert extract_trades_from_fills([]) == []


@pytest.mark.issue_18
def test_compute_trade_statistics_win_loss_and_profit_factor() -> None:
    """Calculates trade stats, win rate, and profit factor correctly."""
    now = datetime.now(UTC)
    trades = [
        TradeRecord(
            ticker="AAPL",
            entry_time=now,
            exit_time=now,
            entry_price=100.0,
            exit_price=120.0,
            shares=10.0,
            pnl=200.0,
            return_pct=0.20,
        ),
        TradeRecord(
            ticker="MSFT",
            entry_time=now,
            exit_time=now,
            entry_price=200.0,
            exit_price=210.0,
            shares=10.0,
            pnl=100.0,
            return_pct=0.05,
        ),
        TradeRecord(
            ticker="TSLA",
            entry_time=now,
            exit_time=now,
            entry_price=150.0,
            exit_price=135.0,
            shares=10.0,
            pnl=-150.0,
            return_pct=-0.10,
        ),
    ]

    stats = compute_trade_statistics(trades)
    assert stats["total_trades"] == 3
    assert stats["winning_trades"] == 2
    assert stats["losing_trades"] == 1
    assert stats["win_rate"] == round(2 / 3, 4)
    # Gross profit = 300, gross loss = 150 -> profit_factor = 300 / 150 = 2.0
    assert stats["profit_factor"] == 2.0
    assert stats["average_trade_pnl"] == 50.0
    assert stats["average_win_pnl"] == 150.0
    assert stats["average_loss_pnl"] == -150.0


@pytest.mark.issue_18
def test_compute_trade_statistics_zero_losses_and_empty() -> None:
    """When there are no losing trades or empty trades, stats handle gracefully."""
    now = datetime.now(UTC)
    trades = [
        TradeRecord(
            ticker="AAPL",
            entry_time=now,
            exit_time=now,
            entry_price=100.0,
            exit_price=110.0,
            shares=10.0,
            pnl=100.0,
            return_pct=0.10,
        )
    ]
    stats = compute_trade_statistics(trades)
    assert stats["profit_factor"] is None
    assert stats["win_rate"] == 1.0

    empty_stats = compute_trade_statistics([])
    assert empty_stats["total_trades"] == 0
    assert empty_stats["profit_factor"] is None
    assert empty_stats["win_rate"] == 0.0


@pytest.mark.issue_18
def test_compute_decision_metrics_aggregation() -> None:
    """Sums tokens and cost across decision records."""
    now = datetime.now(UTC)
    sig = Signal(
        ticker="AAPL",
        action=Action.HOLD,
        size=0.0,
        confidence=0.5,
        rationale="Wait",
    )
    decisions = [
        DecisionRecord(
            decision_id="d1",
            ticker="AAPL",
            signal=sig,
            trace=[
                TraceStep(
                    step_number=1,
                    thought="test",
                    tokens_used=500,
                    cost_usd=0.002,
                )
            ],
            total_cost_usd=0.002,
            total_tokens=500,
            created_at=now,
        ),
        DecisionRecord(
            decision_id="d2",
            ticker="MSFT",
            signal=sig,
            trace=[],
            total_cost_usd=0.004,
            total_tokens=1500,
            created_at=now,
        ),
    ]

    metrics = compute_decision_metrics(decisions)
    assert metrics["total_decisions"] == 2
    assert metrics["total_cost_usd"] == 0.006
    assert metrics["cost_per_decision"] == 0.003
    assert metrics["total_tokens"] == 2000
    assert metrics["tokens_per_decision"] == 1000.0

    empty_metrics = compute_decision_metrics([])
    assert empty_metrics["total_decisions"] == 0
    assert empty_metrics["total_cost_usd"] == 0.0


@pytest.mark.issue_18
def test_compute_performance_metrics_unified_orchestration() -> None:
    """Full end-to-end integration combining equity, fills, and decisions."""
    equity = [10000.0, 10200.0, 10100.0, 10500.0]
    now = datetime.now(UTC)
    fills = [
        Fill(
            fill_id="f1",
            order_id="o1",
            ticker="AAPL",
            action=Action.BUY,
            shares=10.0,
            price=150.0,
            executed_at=now,
        ),
        Fill(
            fill_id="f2",
            order_id="o2",
            ticker="AAPL",
            action=Action.SELL,
            shares=10.0,
            price=160.0,
            executed_at=now + timedelta(hours=1),
        ),
    ]

    sig = Signal(
        ticker="AAPL",
        action=Action.BUY,
        size=0.1,
        confidence=0.8,
        rationale="Strong RSI",
        citations=["obs1"],
    )
    decisions = [
        DecisionRecord(
            decision_id="d1",
            ticker="AAPL",
            signal=sig,
            total_cost_usd=0.005,
            total_tokens=1000,
            created_at=now,
        )
    ]

    perf = compute_performance_metrics(equity, fills=fills, decisions=decisions)

    assert isinstance(perf, PerformanceMetrics)
    assert perf.start_equity == 10000.0
    assert perf.end_equity == 10500.0
    assert perf.total_return == 0.05
    assert perf.total_trades == 1
    assert perf.winning_trades == 1
    assert perf.win_rate == 1.0
    assert perf.profit_factor is None
    assert perf.total_decisions == 1
    assert perf.total_cost_usd == 0.005
    assert perf.total_tokens == 1000
    assert perf.tokens_per_decision == 1000.0
