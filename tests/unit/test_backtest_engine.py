"""Unit and integration tests for Point-in-Time Backtest Engine."""

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from autonomous_trading_analyst.config import Settings
from autonomous_trading_analyst.evaluation import (
    BacktestConfig,
    BacktestResult,
    BuyAndHoldStrategy,
    PointInTimeMarketDataProvider,
    SMACrossoverStrategy,
    create_backtest_engine,
)
from autonomous_trading_analyst.llm.fake import FakeLLMClient
from autonomous_trading_analyst.llm.messages import Message, Role, ToolCall
from autonomous_trading_analyst.tools.market_data.base import Bar
from autonomous_trading_analyst.tools.market_data.fake import FakeMarketDataProvider


@pytest.mark.issue_20
def test_backtest_config_validation() -> None:
    """BacktestConfig normalizes watchlist tickers and validates date ordering."""
    t0 = datetime(2026, 1, 1, tzinfo=UTC)
    t1 = datetime(2026, 1, 10, tzinfo=UTC)

    config = BacktestConfig(
        watchlist=["aapl", " msft "],
        start_date=t0,
        end_date=t1,
        initial_cash=50000.0,
    )
    assert config.watchlist == ["AAPL", "MSFT"]
    assert config.initial_cash == 50000.0

    # Empty watchlist rejected
    with pytest.raises(ValidationError, match="Watchlist cannot be empty"):
        BacktestConfig(
            watchlist=[],
            start_date=t0,
            end_date=t1,
        )

    # Inverted dates rejected
    with pytest.raises(ValidationError, match=r"start_date .* cannot be after end_date"):
        BacktestConfig(
            watchlist=["AAPL"],
            start_date=t1,
            end_date=t0,
        )


@pytest.mark.issue_20
def test_point_in_time_market_data_clamping() -> None:
    """PointInTimeMarketDataProvider strictly enforces historical data cutoff."""
    base = datetime(2026, 1, 1, tzinfo=UTC)
    bars = [
        Bar(
            timestamp=base + timedelta(days=i),
            open=100.0 + i,
            high=102.0 + i,
            low=99.0 + i,
            close=101.0 + i,
            volume=1000.0,
        )
        for i in range(10)
    ]

    fake_provider = FakeMarketDataProvider()
    fake_provider.seed_bars("AAPL", bars)

    # Set as_of to day 5 (index 4: 2026-01-05)
    as_of_t4 = base + timedelta(days=4)
    pit_provider = PointInTimeMarketDataProvider(fake_provider, current_as_of=as_of_t4)
    assert pit_provider.current_as_of == as_of_t4

    # Request range from day 1 to day 10
    query_end = base + timedelta(days=9)
    result_bars = pit_provider.get_bars("AAPL", start=base, end=query_end)

    # Returned bars must NOT contain bars past 2026-01-05
    assert len(result_bars) == 5
    assert result_bars.index[-1] == as_of_t4
    assert pit_provider.get_latest_price("AAPL") == 105.0  # close at index 4

    # Advance as_of to day 8 (index 7: 2026-01-08)
    as_of_t7 = base + timedelta(days=7)
    pit_provider.set_as_of(as_of_t7)
    result_bars_adv = pit_provider.get_bars("AAPL", start=base, end=query_end)
    assert len(result_bars_adv) == 8
    assert result_bars_adv.index[-1] == as_of_t7
    assert pit_provider.get_latest_price("AAPL") == 108.0

    # Query starting strictly in the future relative to current_as_of
    future_start = base + timedelta(days=8)
    empty_bars = pit_provider.get_bars("AAPL", start=future_start, end=query_end)
    assert empty_bars.empty


def _build_scripted_llm_for_backtest() -> FakeLLMClient:
    """Script a FakeLLMClient for 3 cycle evaluations."""
    # Cycle 1: inspect price and BUY
    # Cycle 2 & 3: inspect price and HOLD
    responses = [
        # Cycle 1 (day 1)
        Message(
            role=Role.ASSISTANT,
            content="Price check",
            tool_calls=[
                ToolCall(id="c1_p", name="get_latest_price", arguments={"ticker": "AAPL"}),
            ],
        ),
        Message(
            role=Role.ASSISTANT,
            content="Bullish breakout",
            tool_calls=[
                ToolCall(
                    id="c1_s",
                    name="submit_signal",
                    arguments={
                        "ticker": "AAPL",
                        "decision": "BUY",
                        "confidence": 0.85,
                        "rationale": "Strong momentum",
                    },
                ),
            ],
        ),
        # Cycle 2 (day 2)
        Message(
            role=Role.ASSISTANT,
            content="Holding position",
            tool_calls=[
                ToolCall(
                    id="c2_s",
                    name="submit_signal",
                    arguments={
                        "ticker": "AAPL",
                        "decision": "HOLD",
                        "confidence": 0.70,
                        "rationale": "Holding initial entry",
                    },
                ),
            ],
        ),
        # Cycle 3 (day 3)
        Message(
            role=Role.ASSISTANT,
            content="Continuing hold",
            tool_calls=[
                ToolCall(
                    id="c3_s",
                    name="submit_signal",
                    arguments={
                        "ticker": "AAPL",
                        "decision": "HOLD",
                        "confidence": 0.70,
                        "rationale": "Trend continues",
                    },
                ),
            ],
        ),
    ]
    return FakeLLMClient(responses=responses)


@pytest.mark.issue_20
def test_backtest_engine_execution_and_results() -> None:
    """BacktestEngine replays dates, executing agent and baselines side-by-side."""
    t0 = datetime(2026, 1, 5, tzinfo=UTC)
    t1 = datetime(2026, 1, 6, tzinfo=UTC)
    t2 = datetime(2026, 1, 7, tzinfo=UTC)

    bars = [
        Bar(timestamp=t0, open=100.0, high=102.0, low=99.0, close=100.0, volume=1000.0),
        Bar(timestamp=t1, open=100.0, high=105.0, low=100.0, close=104.0, volume=1200.0),
        Bar(timestamp=t2, open=104.0, high=110.0, low=103.0, close=108.0, volume=1500.0),
    ]

    fake_market = FakeMarketDataProvider()
    fake_market.seed_bars("AAPL", bars)

    config = BacktestConfig(
        watchlist=["AAPL"],
        start_date=t0,
        end_date=t2,
        initial_cash=100000.0,
    )

    llm = _build_scripted_llm_for_backtest()
    engine = create_backtest_engine(
        config=config,
        market_data_provider=fake_market,
        llm_client=llm,
        baselines=[
            BuyAndHoldStrategy(allocation_pct=1.0),
            SMACrossoverStrategy(fast_period=2, slow_period=3),
        ],
    )

    result = engine.run()

    assert isinstance(result, BacktestResult)
    assert result.total_cycles == 3
    # 4 timestamps: initial capital prior date + 3 trading days
    assert len(result.timestamps) == 4

    # Agent equity progression
    assert len(result.agent_equity) == 4
    assert result.agent_equity[0] == 100000.0
    assert result.agent_metrics.start_equity == 100000.0
    assert result.agent_metrics.total_decisions > 0

    # Baseline Buy & Hold progression
    assert "buy_and_hold" in result.baseline_metrics
    bnh_metrics = result.baseline_metrics["buy_and_hold"]
    assert bnh_metrics.start_equity == 100000.0
    assert bnh_metrics.total_return > 0.0
    assert bnh_metrics.total_decisions == 0
    assert bnh_metrics.total_cost_usd == 0.0

    # Baseline SMA Crossover progression
    assert "sma_crossover" in result.baseline_metrics
    sma_metrics = result.baseline_metrics["sma_crossover"]
    assert sma_metrics.total_decisions == 0


@pytest.mark.issue_20
def test_backtest_engine_shared_risk_guardrails() -> None:
    """Agent and baselines adhere to shared RiskManager position sizing limits."""
    t0 = datetime(2026, 1, 5, tzinfo=UTC)
    t1 = datetime(2026, 1, 6, tzinfo=UTC)

    bars = [
        Bar(timestamp=t0, open=100.0, high=101.0, low=99.0, close=100.0, volume=1000.0),
        Bar(timestamp=t1, open=100.0, high=102.0, low=99.0, close=101.0, volume=1000.0),
    ]

    fake_market = FakeMarketDataProvider()
    fake_market.seed_bars("AAPL", bars)

    settings = Settings(
        watchlist=["AAPL"],
        risk_max_position_pct=0.20,  # Strict 20% position limit
    )

    config = BacktestConfig(
        watchlist=["AAPL"],
        start_date=t0,
        end_date=t1,
        initial_cash=100000.0,
    )

    engine = create_backtest_engine(
        config=config,
        market_data_provider=fake_market,
        settings=settings,
        baselines=[BuyAndHoldStrategy(allocation_pct=1.0)],
    )

    result = engine.run()
    assert result.total_cycles == 2
    bnh_broker = engine.baseline_brokers["buy_and_hold"]

    assert len(bnh_broker.fills) == 1
    # Max 20% position of $100,000 equity at $100 price = ~200 shares
    assert 190.0 <= bnh_broker.fills[0].shares <= 205.0


@pytest.mark.issue_20
def test_backtest_engine_stop_loss_sweep_during_replay() -> None:
    """Engine checks stop-losses on baseline broker when price drops significantly."""
    t0 = datetime(2026, 1, 5, tzinfo=UTC)
    t1 = datetime(2026, 1, 6, tzinfo=UTC)

    # Initial purchase at 100, then plunge to 85 (-15%, triggering default 5% stop loss)
    bars = [
        Bar(timestamp=t0, open=100.0, high=100.0, low=100.0, close=100.0, volume=1000.0),
        Bar(timestamp=t1, open=85.0, high=85.0, low=80.0, close=85.0, volume=1000.0),
    ]

    fake_market = FakeMarketDataProvider()
    fake_market.seed_bars("AAPL", bars)

    config = BacktestConfig(
        watchlist=["AAPL"],
        start_date=t0,
        end_date=t1,
        initial_cash=10000.0,
    )

    engine = create_backtest_engine(
        config=config,
        market_data_provider=fake_market,
        baselines=[BuyAndHoldStrategy(allocation_pct=1.0)],
    )

    result = engine.run()
    bnh_broker = engine.baseline_brokers["buy_and_hold"]

    # Fill 1: BUY at t0. Fill 2: Stop-loss SELL at t1. Fill 3: Re-entry BUY at t1.
    assert len(bnh_broker.fills) == 3
    assert bnh_broker.fills[0].action == "BUY"
    assert bnh_broker.fills[1].action == "SELL"
    assert bnh_broker.fills[2].action == "BUY"
    assert result.baseline_metrics["buy_and_hold"].total_trades == 1


@pytest.mark.issue_20
def test_backtest_result_json_serialization() -> None:
    """BacktestResult is fully serializable to and deserializable from JSON."""
    t0 = datetime(2026, 1, 1, tzinfo=UTC)
    config = BacktestConfig(
        watchlist=["AAPL"],
        start_date=t0,
        end_date=t0,
        initial_cash=10000.0,
    )

    fake_market = FakeMarketDataProvider()
    fake_market.seed_latest_price("AAPL", 150.0)

    engine = create_backtest_engine(
        config=config,
        market_data_provider=fake_market,
        baselines=[BuyAndHoldStrategy()],
    )

    result = engine.run()
    json_payload = result.model_dump_json()

    # Reconstruct from json
    restored = BacktestResult.model_validate_json(json_payload)
    assert restored.config.watchlist == ["AAPL"]
    assert restored.config.initial_cash == 10000.0
    assert len(restored.timestamps) == len(result.timestamps)
    assert restored.total_cycles == result.total_cycles
