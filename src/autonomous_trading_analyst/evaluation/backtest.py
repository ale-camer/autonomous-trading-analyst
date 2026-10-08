"""Point-in-time backtesting engine and market data isolation provider."""

import asyncio
import concurrent.futures
import logging
from collections.abc import Sequence
from datetime import UTC, date, datetime, time, timedelta
from typing import Any

import pandas as pd
from sqlalchemy.orm import Session, sessionmaker

from autonomous_trading_analyst.broker.paper import PaperBroker
from autonomous_trading_analyst.config import Settings, get_settings
from autonomous_trading_analyst.cycle import (
    AnalysisCycleOrchestrator,
    create_analysis_cycle,
)
from autonomous_trading_analyst.domain.models import Action, OrderStatus
from autonomous_trading_analyst.evaluation.baselines import (
    BaselineStrategy,
    BuyAndHoldStrategy,
    SMACrossoverStrategy,
)
from autonomous_trading_analyst.evaluation.metrics import compute_performance_metrics
from autonomous_trading_analyst.evaluation.models import (
    BacktestConfig,
    BacktestResult,
    PerformanceMetrics,
)
from autonomous_trading_analyst.llm.client import LLMClient
from autonomous_trading_analyst.llm.messages import Message, Role, ToolCall
from autonomous_trading_analyst.memory.embeddings import (
    EmbeddingClient,
    FakeEmbeddingClient,
)
from autonomous_trading_analyst.persistence.db import (
    create_db_engine,
    get_session_factory,
    init_db,
)
from autonomous_trading_analyst.risk.manager import RiskManager
from autonomous_trading_analyst.tools.market_data.base import MarketDataProvider
from autonomous_trading_analyst.tools.market_data.fake import FakeMarketDataProvider

logger = logging.getLogger(__name__)


def _to_utc_datetime(d: datetime | date) -> datetime:
    """Normalize date or datetime to timezone-aware UTC datetime."""
    if isinstance(d, datetime):
        if d.tzinfo is None:
            return d.replace(tzinfo=UTC)
        return d.astimezone(UTC)
    return datetime.combine(d, time.min, tzinfo=UTC)


class PointInTimeMarketDataProvider(MarketDataProvider):
    """Decorator wrapping any MarketDataProvider to strictly clamp historical access to as_of."""

    def __init__(
        self,
        provider: MarketDataProvider,
        current_as_of: datetime | None = None,
    ) -> None:
        """Initialize PointInTimeMarketDataProvider with underlying provider and timestamp."""
        self._provider = provider
        self._current_as_of = (
            _to_utc_datetime(current_as_of) if current_as_of is not None else datetime.now(UTC)
        )

    @property
    def current_as_of(self) -> datetime:
        """Current point-in-time timestamp."""
        return self._current_as_of

    def set_as_of(self, as_of: datetime | date) -> None:
        """Advance or update the point-in-time timestamp."""
        self._current_as_of = _to_utc_datetime(as_of)

    def get_bars(
        self,
        ticker: str,
        start: datetime | date,
        end: datetime | date,
        interval: str = "1d",
    ) -> pd.DataFrame:
        """Fetch historical OHLCV bars strictly clamped to <= current_as_of."""
        start_dt = _to_utc_datetime(start)
        end_dt = _to_utc_datetime(end)

        if start_dt > self._current_as_of:
            return pd.DataFrame(
                columns=["open", "high", "low", "close", "volume"],
                index=pd.DatetimeIndex([], tz=UTC, name="timestamp"),
            )

        clamped_end = min(end_dt, self._current_as_of)
        if start_dt > clamped_end:
            return pd.DataFrame(
                columns=["open", "high", "low", "close", "volume"],
                index=pd.DatetimeIndex([], tz=UTC, name="timestamp"),
            )

        df = self._provider.get_bars(
            ticker=ticker,
            start=start_dt,
            end=clamped_end,
            interval=interval,
        )
        if df.empty:
            return df

        if isinstance(df.index, pd.DatetimeIndex):
            # Guarantee no future bars slip past current_as_of
            mask = df.index <= self._current_as_of
            return df.loc[mask].copy()

        return df

    def get_latest_price(self, ticker: str) -> float:
        """Fetch price as of current_as_of without future data leakage."""
        start_lookback = self._current_as_of - timedelta(days=30)
        bars = self.get_bars(
            ticker=ticker,
            start=start_lookback,
            end=self._current_as_of,
        )
        if not bars.empty and "close" in bars.columns:
            return float(bars["close"].iloc[-1])

        try:
            return float(self._provider.get_latest_price(ticker))
        except Exception:
            return 0.0


class BacktestEngine:
    """Point-in-time multi-asset backtesting engine."""

    def __init__(
        self,
        config: BacktestConfig,
        market_data_provider: MarketDataProvider,
        agent_orchestrator: AnalysisCycleOrchestrator | None = None,
        baselines: Sequence[BaselineStrategy] | None = None,
        risk_manager: RiskManager | None = None,
        settings: Settings | None = None,
    ) -> None:
        """Initialize BacktestEngine with simulation specification and participants."""
        self.config = config
        self.settings = settings if settings is not None else get_settings()

        # Wrap market data in strict point-in-time guard
        self.pit_market_data = PointInTimeMarketDataProvider(
            provider=market_data_provider,
            current_as_of=config.start_date,
        )

        # Risk manager shared across agent and baselines
        self.risk_manager = (
            risk_manager if risk_manager is not None else RiskManager(settings=self.settings)
        )

        # Agent orchestrator and broker
        self.agent_orchestrator = agent_orchestrator
        if self.agent_orchestrator is not None:
            # Wire point-in-time market data into orchestrator
            self.agent_orchestrator.market_data_provider = self.pit_market_data
            self.agent_broker = self.agent_orchestrator.broker
        else:
            self.agent_broker = PaperBroker(
                settings=self.settings,
                initial_cash=config.initial_cash,
            )

        # Baselines and dedicated brokers
        if baselines is not None:
            self.baselines = list(baselines)
        else:
            self.baselines = [BuyAndHoldStrategy(), SMACrossoverStrategy()]

        self.baseline_brokers: dict[str, PaperBroker] = {
            b.name: PaperBroker(settings=self.settings, initial_cash=config.initial_cash)
            for b in self.baselines
        }

    def _extract_trading_dates(self) -> list[datetime]:
        """Determine chronological list of trading evaluation dates."""
        start_dt = _to_utc_datetime(self.config.start_date)
        end_dt = _to_utc_datetime(self.config.end_date)

        if start_dt == end_dt:
            return [start_dt]

        # Temporarily query underlying market data for actual trading calendar days
        first_ticker = self.config.watchlist[0]
        try:
            bars = self.pit_market_data._provider.get_bars(
                ticker=first_ticker,
                start=start_dt,
                end=end_dt,
            )
            if not bars.empty and isinstance(bars.index, pd.DatetimeIndex):
                return [_to_utc_datetime(ts) for ts in bars.index]
        except Exception as exc:
            logger.debug("Could not extract trading calendar from bars: %s", exc)

        # Fallback to standard business days or consecutive days
        dr = pd.date_range(start=start_dt, end=end_dt, freq="1D", tz=UTC)
        return [_to_utc_datetime(ts) for ts in dr]

    async def run_async(self) -> BacktestResult:
        """Execute complete point-in-time backtest asynchronously across all historical dates."""
        sim_dates = self._extract_trading_dates()

        agent_equities: list[float] = [self.config.initial_cash]
        baseline_equities: dict[str, list[float]] = {
            b.name: [self.config.initial_cash] for b in self.baselines
        }

        if sim_dates:
            prior_date = sim_dates[0] - timedelta(days=1)
        else:
            prior_date = _to_utc_datetime(self.config.start_date) - timedelta(days=1)
        recorded_timestamps: list[datetime] = [prior_date]

        agent_decisions = []

        slippage_rate = self.settings.paper_slippage_bps / 10000.0
        commission_rate = self.settings.paper_commission_bps / 10000.0
        fee_mult = (1.0 + slippage_rate) * (1.0 + commission_rate)

        for as_of in sim_dates:
            self.pit_market_data.set_as_of(as_of)

            # 1. Collect current prices as of date
            current_prices: dict[str, float] = {}
            for ticker in self.config.watchlist:
                price = self.pit_market_data.get_latest_price(ticker)
                if price > 0.0:
                    current_prices[ticker] = price

            # 2. Run agent cycle
            if self.agent_orchestrator is not None:
                summary = await self.agent_orchestrator.run_cycle(
                    watchlist=self.config.watchlist,
                    as_of=as_of,
                )
                agent_decisions.extend(summary.decisions)
                agent_equities.append(self.agent_broker.total_equity)
            else:
                agent_equities.append(self.agent_broker.total_equity)

            # 3. Run baselines
            for baseline in self.baselines:
                b_broker = self.baseline_brokers[baseline.name]

                # Stop loss sweep
                stop_orders = self.risk_manager.check_stop_losses(
                    b_broker.get_portfolio_state(),
                    current_prices,
                )
                for s_order in stop_orders:
                    m_price = current_prices.get(s_order.ticker, 0.0)
                    b_broker.execute_order(s_order, market_price=m_price)

                # Signal generation for watchlist
                for ticker in self.config.watchlist:
                    curr_price = current_prices.get(ticker, 0.0)
                    if curr_price <= 0.0:
                        continue

                    # Lookback price history strictly up to as_of
                    hist_bars = self.pit_market_data.get_bars(
                        ticker=ticker,
                        start=as_of - timedelta(days=120),
                        end=as_of,
                    )
                    if not hist_bars.empty and "close" in hist_bars.columns:
                        hist_series = hist_bars["close"].astype(float)
                    else:
                        hist_series = pd.Series([curr_price], dtype=float)

                    sig = baseline.generate_signal(
                        ticker=ticker,
                        current_price=curr_price,
                        portfolio=b_broker.get_portfolio_state(),
                        price_history=hist_series,
                        as_of=as_of,
                    )

                    if sig.action in (Action.BUY, Action.SELL) and sig.size > 0.0:
                        order = self.risk_manager.evaluate_signal(
                            signal=sig,
                            portfolio=b_broker.get_portfolio_state(),
                            current_price=curr_price,
                        )
                        if order is not None and order.status in (
                            OrderStatus.APPROVED,
                            OrderStatus.RESIZED,
                        ):
                            if order.action == Action.BUY:
                                req_cash = order.shares * curr_price * fee_mult
                                if req_cash > b_broker.cash and b_broker.cash > 0:
                                    safe_shares = (b_broker.cash * 0.9999) / (curr_price * fee_mult)
                                    order = order.model_copy(update={"shares": safe_shares})
                            b_broker.execute_order(order, market_price=curr_price)

                m2m = b_broker.mark_to_market(current_prices)
                baseline_equities[baseline.name].append(m2m.total_equity)

            recorded_timestamps.append(as_of)

        # 4. Compute performance metrics
        agent_metrics = compute_performance_metrics(
            equity_curve=agent_equities,
            fills=self.agent_broker.fills,
            decisions=agent_decisions,
            risk_free_rate=self.config.risk_free_rate,
        )

        baseline_metrics: dict[str, PerformanceMetrics] = {}
        for baseline in self.baselines:
            b_broker = self.baseline_brokers[baseline.name]
            baseline_metrics[baseline.name] = compute_performance_metrics(
                equity_curve=baseline_equities[baseline.name],
                fills=b_broker.fills,
                decisions=None,
                risk_free_rate=self.config.risk_free_rate,
            )

        return BacktestResult(
            config=self.config,
            timestamps=recorded_timestamps,
            agent_metrics=agent_metrics,
            agent_equity=agent_equities,
            baseline_metrics=baseline_metrics,
            baseline_equities=baseline_equities,
            total_cycles=len(sim_dates),
        )

    def run(self) -> BacktestResult:
        """Execute backtest synchronously."""
        try:
            asyncio.get_running_loop()
            # If already inside an existing event loop, run in a separate worker thread
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                return executor.submit(lambda: asyncio.run(self.run_async())).result()
        except RuntimeError:
            return asyncio.run(self.run_async())


class DefaultHoldLLMClient(LLMClient):
    """Fallback LLM client that continuously emits HOLD signals for backtests."""

    async def generate(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]] | None = None,
    ) -> tuple[Message, dict[str, Any]]:
        """Return a deterministic HOLD signal message."""
        ticker = "AAPL"
        for m in reversed(messages):
            if m.content and "Analyze ticker" in m.content:
                parts = m.content.split("Analyze ticker")
                if len(parts) > 1:
                    ticker = parts[1].strip().split()[0].replace(".", "").upper()
                break

        msg = Message(
            role=Role.ASSISTANT,
            content=f"Holding position for {ticker}.",
            tool_calls=[
                ToolCall(
                    id=f"hold_{ticker}",
                    name="submit_signal",
                    arguments={
                        "ticker": ticker,
                        "decision": "HOLD",
                        "confidence": 0.5,
                        "rationale": "Holding position during evaluation.",
                    },
                )
            ],
        )
        usage = {"prompt_tokens": 50, "completion_tokens": 20, "total_tokens": 70}
        return msg, usage


def create_backtest_engine(
    config: BacktestConfig,
    market_data_provider: MarketDataProvider | None = None,
    llm_client: LLMClient | None = None,
    embedding_client: EmbeddingClient | None = None,
    baselines: Sequence[BaselineStrategy] | None = None,
    settings: Settings | None = None,
    session_factory: sessionmaker[Session] | None = None,
) -> BacktestEngine:
    """Factory creating a BacktestEngine with complete dependency injection."""
    cfg = settings if settings is not None else get_settings()

    if session_factory is None:
        db_engine = create_db_engine("sqlite:///:memory:")
        init_db(db_engine)
        sess_factory = get_session_factory(db_engine)
    else:
        sess_factory = session_factory

    data_provider = (
        market_data_provider if market_data_provider is not None else FakeMarketDataProvider()
    )
    llm = llm_client if llm_client is not None else DefaultHoldLLMClient()
    emb = embedding_client if embedding_client is not None else FakeEmbeddingClient()

    broker = PaperBroker(settings=cfg, initial_cash=config.initial_cash)
    risk = RiskManager(settings=cfg)

    orchestrator = create_analysis_cycle(
        session_factory=sess_factory,
        market_data_provider=data_provider,
        llm_client=llm,
        embedding_client=emb,
        paper_broker=broker,
        risk_manager=risk,
        settings=cfg,
    )

    return BacktestEngine(
        config=config,
        market_data_provider=data_provider,
        agent_orchestrator=orchestrator,
        baselines=baselines,
        risk_manager=risk,
        settings=cfg,
    )
