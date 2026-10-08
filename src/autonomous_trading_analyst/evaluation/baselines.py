"""Baseline benchmark trading strategies and simulation runner for evaluation."""

import math
import uuid
from abc import ABC, abstractmethod
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

import pandas as pd

from autonomous_trading_analyst.broker.paper import PaperBroker
from autonomous_trading_analyst.domain.models import (
    Action,
    Order,
    OrderStatus,
    PortfolioState,
    Signal,
)
from autonomous_trading_analyst.evaluation.metrics import compute_performance_metrics
from autonomous_trading_analyst.evaluation.models import PerformanceMetrics
from autonomous_trading_analyst.risk.manager import RiskManager
from autonomous_trading_analyst.tools.indicators.calculations import compute_sma


class BaselineStrategy(ABC):
    """Abstract base class for benchmark trading strategies."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Name identifying the baseline strategy."""

    @abstractmethod
    def generate_signal(
        self,
        ticker: str,
        current_price: float,
        portfolio: PortfolioState,
        price_history: pd.Series | Sequence[float] | None = None,
        as_of: datetime | None = None,
    ) -> Signal:
        """Generate a trading signal based strictly on point-in-time state."""


class BuyAndHoldStrategy(BaselineStrategy):
    """Passive buy-and-hold benchmark strategy.

    Emits a BUY signal on the first available evaluation when uninvested,
    and maintains the position with HOLD signals thereafter.
    """

    def __init__(self, allocation_pct: float = 1.0) -> None:
        """Initialize BuyAndHoldStrategy.

        Args:
            allocation_pct: Target portfolio allocation fraction (0.0 < allocation_pct <= 1.0).
        """
        if not (0.0 < allocation_pct <= 1.0):
            msg = (
                f"allocation_pct must be between 0.0 (exclusive) and 1.0 (inclusive), "
                f"got {allocation_pct}"
            )
            raise ValueError(msg)
        self.allocation_pct = allocation_pct

    @property
    def name(self) -> str:
        """Name identifying the baseline strategy."""
        return "buy_and_hold"

    def generate_signal(
        self,
        ticker: str,
        current_price: float,
        portfolio: PortfolioState,
        price_history: pd.Series | Sequence[float] | None = None,
        as_of: datetime | None = None,
    ) -> Signal:
        """Generate a BUY signal when uninvested, or HOLD once position is established."""
        clean_ticker = ticker.strip().upper()
        pos = portfolio.positions.get(clean_ticker)
        current_shares = pos.shares if pos is not None else 0.0
        ts = as_of if as_of is not None else datetime.now(UTC)

        if current_shares > 1e-9:
            return Signal(
                ticker=clean_ticker,
                action=Action.HOLD,
                size=0.0,
                confidence=1.0,
                rationale="Buy and hold position is established; maintaining hold.",
                citations=["baseline:buy_and_hold"],
                timestamp=ts,
            )

        if portfolio.cash <= 0.0 or current_price <= 0.0:
            return Signal(
                ticker=clean_ticker,
                action=Action.HOLD,
                size=0.0,
                confidence=1.0,
                rationale="Cannot initiate buy and hold entry: zero cash or non-positive price.",
                citations=["baseline:buy_and_hold"],
                timestamp=ts,
            )

        return Signal(
            ticker=clean_ticker,
            action=Action.BUY,
            size=self.allocation_pct,
            confidence=1.0,
            rationale="Initial buy and hold portfolio allocation entry.",
            citations=["baseline:buy_and_hold"],
            timestamp=ts,
        )


class SMACrossoverStrategy(BaselineStrategy):
    """Trend-following benchmark based on Fast and Slow Simple Moving Average crossover.

    Point-in-time calculation strictly avoids future lookahead:
    - Golden cross: Fast SMA crosses strictly above Slow SMA -> Action.BUY
    - Death cross: Fast SMA crosses strictly below Slow SMA -> Action.SELL (liquidate position)
    - Flat / ongoing trend / warmup: Action.HOLD
    """

    def __init__(
        self,
        fast_period: int = 10,
        slow_period: int = 50,
        size: float = 1.0,
        enter_on_trend: bool = False,
    ) -> None:
        """Initialize SMACrossoverStrategy.

        Args:
            fast_period: Window length for the fast SMA.
            slow_period: Window length for the slow SMA. Must be > fast_period.
            size: Fraction of allowable position budget to buy or sell.
            enter_on_trend: If True, allows entering BUY when flat during ongoing bull trend.
        """
        if fast_period <= 0:
            msg = f"fast_period must be positive, got {fast_period}"
            raise ValueError(msg)
        if slow_period <= fast_period:
            msg = (
                f"slow_period ({slow_period}) must be strictly greater than "
                f"fast_period ({fast_period})"
            )
            raise ValueError(msg)
        if not (0.0 < size <= 1.0):
            msg = f"size must be between 0.0 (exclusive) and 1.0 (inclusive), got {size}"
            raise ValueError(msg)

        self.fast_period = fast_period
        self.slow_period = slow_period
        self.size = size
        self.enter_on_trend = enter_on_trend

    @property
    def name(self) -> str:
        """Name identifying the baseline strategy."""
        return "sma_crossover"

    def generate_signal(
        self,
        ticker: str,
        current_price: float,
        portfolio: PortfolioState,
        price_history: pd.Series | Sequence[float] | None = None,
        as_of: datetime | None = None,
    ) -> Signal:
        """Generate a trading signal based on moving average crossover state."""
        clean_ticker = ticker.strip().upper()
        pos = portfolio.positions.get(clean_ticker)
        current_shares = pos.shares if pos is not None else 0.0
        ts = as_of if as_of is not None else datetime.now(UTC)

        # Convert price history to Series
        if price_history is None:
            series = pd.Series([current_price], dtype=float)
        elif isinstance(price_history, pd.Series):
            series = price_history.astype(float)
        else:
            series = pd.Series(list(price_history), dtype=float)

        # Enforce point-in-time timestamp cut if applicable
        if as_of is not None and isinstance(series.index, pd.DatetimeIndex):
            series = series.loc[:as_of]

        # Warmup check
        if len(series) < self.slow_period:
            return Signal(
                ticker=clean_ticker,
                action=Action.HOLD,
                size=0.0,
                confidence=1.0,
                rationale=(
                    f"Insufficient price history ({len(series)} bars) for slow SMA "
                    f"({self.slow_period} periods). Maintaining hold."
                ),
                citations=["baseline:sma_crossover:warmup"],
                timestamp=ts,
            )

        fast_sma = compute_sma(series, self.fast_period)
        slow_sma = compute_sma(series, self.slow_period)

        fast_curr = float(fast_sma.iloc[-1])
        slow_curr = float(slow_sma.iloc[-1])

        # Previous values at bar t-1
        if len(series) >= self.slow_period + 1:
            fast_prev = float(fast_sma.iloc[-2])
            slow_prev = float(slow_sma.iloc[-2])
        else:
            fast_prev = float("nan")
            slow_prev = float("nan")

        # Crossover checks
        is_golden_cross = (fast_curr > slow_curr) and (
            math.isnan(slow_prev) or (fast_prev <= slow_prev)
        )
        is_death_cross = (fast_curr < slow_curr) and (
            math.isnan(slow_prev) or (fast_prev >= slow_prev)
        )

        if is_golden_cross:
            if current_shares <= 1e-9:
                return Signal(
                    ticker=clean_ticker,
                    action=Action.BUY,
                    size=self.size,
                    confidence=1.0,
                    rationale=(
                        f"Golden cross detected: Fast SMA ({fast_curr:.2f}) crossed above "
                        f"Slow SMA ({slow_curr:.2f})."
                    ),
                    citations=["baseline:sma_crossover:golden_cross"],
                    timestamp=ts,
                )
            return Signal(
                ticker=clean_ticker,
                action=Action.HOLD,
                size=0.0,
                confidence=1.0,
                rationale=(
                    f"Golden cross active but position already held ({current_shares} shares)."
                ),
                citations=["baseline:sma_crossover:hold"],
                timestamp=ts,
            )

        if is_death_cross:
            if current_shares > 1e-9:
                return Signal(
                    ticker=clean_ticker,
                    action=Action.SELL,
                    size=self.size,
                    confidence=1.0,
                    rationale=(
                        f"Death cross detected: Fast SMA ({fast_curr:.2f}) crossed below "
                        f"Slow SMA ({slow_curr:.2f}). Liquidating position."
                    ),
                    citations=["baseline:sma_crossover:death_cross"],
                    timestamp=ts,
                )
            return Signal(
                ticker=clean_ticker,
                action=Action.HOLD,
                size=0.0,
                confidence=1.0,
                rationale="Death cross active but portfolio is already flat.",
                citations=["baseline:sma_crossover:hold"],
                timestamp=ts,
            )

        # Continuation of ongoing trend without fresh crossover
        if self.enter_on_trend and fast_curr > slow_curr and current_shares <= 1e-9:
            return Signal(
                ticker=clean_ticker,
                action=Action.BUY,
                size=self.size,
                confidence=1.0,
                rationale=(
                    f"Trend following entry: Fast SMA ({fast_curr:.2f}) > "
                    f"Slow SMA ({slow_curr:.2f})."
                ),
                citations=["baseline:sma_crossover:trend_entry"],
                timestamp=ts,
            )

        return Signal(
            ticker=clean_ticker,
            action=Action.HOLD,
            size=0.0,
            confidence=1.0,
            rationale=(f"No crossover: Fast SMA ({fast_curr:.2f}) vs Slow SMA ({slow_curr:.2f})."),
            citations=["baseline:sma_crossover:hold"],
            timestamp=ts,
        )


def run_baseline_simulation(
    strategy: BaselineStrategy,
    ticker: str,
    price_history: pd.Series | Sequence[float],
    broker: PaperBroker | None = None,
    risk_manager: RiskManager | None = None,
    initial_cash: float | None = None,
    dates: Sequence[datetime] | None = None,
) -> tuple[PaperBroker, PerformanceMetrics]:
    """Execute point-in-time replay of a baseline strategy over historical price bars.

    Args:
        strategy: Baseline strategy instance (BuyAndHoldStrategy, SMACrossoverStrategy, etc.).
        ticker: Symbol to evaluate and execute trades for.
        price_history: Chronological price series or float sequence.
        broker: Optional PaperBroker instance. Created if None.
        risk_manager: Optional RiskManager for guardrail enforcement.
        initial_cash: Starting cash for broker if creating or resetting broker.
        dates: Optional sequence of datetime timestamps corresponding to price bars.

    Returns:
        Tuple of (PaperBroker with execution history, PerformanceMetrics object).
    """
    clean_ticker = ticker.strip().upper()

    if isinstance(price_history, pd.Series):
        series = price_history.astype(float)
    else:
        series = pd.Series(list(price_history), dtype=float)

    if dates is not None and len(dates) == len(series):
        series.index = pd.to_datetime(dates, utc=True)

    if series.empty:
        active_broker = broker if broker is not None else PaperBroker(initial_cash=initial_cash)
        metrics = compute_performance_metrics(pd.Series(dtype=float))
        return active_broker, metrics

    if broker is None:
        active_broker = PaperBroker(initial_cash=initial_cash)
    else:
        active_broker = broker
        if initial_cash is not None:
            active_broker.reset(initial_cash=initial_cash)

    initial_equity = float(active_broker.total_equity)
    daily_equities: list[float] = []

    slippage_rate = active_broker.settings.paper_slippage_bps / 10000.0
    commission_rate = active_broker.settings.paper_commission_bps / 10000.0
    fee_multiplier = (1.0 + slippage_rate) * (1.0 + commission_rate)

    for i in range(len(series)):
        current_price = float(series.iloc[i])
        sub_series = series.iloc[: i + 1]

        if isinstance(series.index, pd.DatetimeIndex):
            as_of_dt = series.index[i].to_pydatetime()
            if as_of_dt.tzinfo is None:
                as_of_dt = as_of_dt.replace(tzinfo=UTC)
        else:
            as_of_dt = datetime.now(UTC)

        portfolio_state = active_broker.get_portfolio_state()
        signal = strategy.generate_signal(
            ticker=clean_ticker,
            current_price=current_price,
            portfolio=portfolio_state,
            price_history=sub_series,
            as_of=as_of_dt,
        )

        order: Order | None = None
        if signal.action in (Action.BUY, Action.SELL) and signal.size > 0.0:
            if risk_manager is not None:
                order = risk_manager.evaluate_signal(
                    signal=signal,
                    portfolio=portfolio_state,
                    current_price=current_price,
                )
            else:
                order_id = f"ord_{uuid.uuid4().hex[:8]}"
                if signal.action == Action.BUY:
                    effective_price = current_price * fee_multiplier
                    spendable = active_broker.cash * signal.size * 0.9999
                    shares = spendable / effective_price if effective_price > 0.0 else 0.0
                    if shares > 1e-6:
                        order = Order(
                            order_id=order_id,
                            ticker=clean_ticker,
                            action=Action.BUY,
                            shares=shares,
                            status=OrderStatus.APPROVED,
                            created_at=as_of_dt,
                        )
                elif signal.action == Action.SELL:
                    pos = portfolio_state.positions.get(clean_ticker)
                    if pos is not None and pos.shares > 1e-6:
                        shares_to_sell = pos.shares * signal.size
                        order = Order(
                            order_id=order_id,
                            ticker=clean_ticker,
                            action=Action.SELL,
                            shares=shares_to_sell,
                            status=OrderStatus.APPROVED,
                            created_at=as_of_dt,
                        )

            # Safeguard BUY order shares so total_required_cash <= active_broker.cash
            if (
                order is not None
                and order.action == Action.BUY
                and order.status in (OrderStatus.APPROVED, OrderStatus.RESIZED)
            ):
                req_cash = order.shares * current_price * fee_multiplier
                if req_cash > active_broker.cash and active_broker.cash > 0:
                    max_safe_shares = (active_broker.cash * 0.9999) / (
                        current_price * fee_multiplier
                    )
                    order = order.model_copy(update={"shares": max_safe_shares})

        if order is not None and order.status in (OrderStatus.APPROVED, OrderStatus.RESIZED):
            active_broker.execute_order(order=order, market_price=current_price)

        m2m_state = active_broker.mark_to_market({clean_ticker: current_price})
        daily_equities.append(m2m_state.total_equity)

    # Build equity curve beginning with initial starting capital
    if isinstance(series.index, pd.DatetimeIndex):
        start_idx = series.index[0] - timedelta(days=1)
        full_index = pd.DatetimeIndex([start_idx, *list(series.index)])
    else:
        full_index = pd.Index([-1, *list(range(len(series)))])

    equity_series = pd.Series([initial_equity, *daily_equities], index=full_index, dtype=float)
    metrics = compute_performance_metrics(
        equity_curve=equity_series,
        fills=active_broker.fills,
        decisions=None,
        risk_free_rate=0.0,
    )

    return active_broker, metrics
