"""Analysis cycle orchestrator integrating agent, risk, broker, persistence, and memory."""

import asyncio
import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session, sessionmaker

from autonomous_trading_analyst.agent.loop import ReActAgent
from autonomous_trading_analyst.agent.trace import Scratchpad
from autonomous_trading_analyst.broker.paper import PaperBroker
from autonomous_trading_analyst.config import Settings, get_settings
from autonomous_trading_analyst.domain.cycle import CycleSummary
from autonomous_trading_analyst.domain.models import (
    Action,
    DecisionRecord,
    Fill,
    Order,
    OrderStatus,
    Signal,
    TraceStep,
)
from autonomous_trading_analyst.llm.client import LLMClient
from autonomous_trading_analyst.llm.factory import get_llm_client
from autonomous_trading_analyst.memory.embeddings import (
    EmbeddingClient,
    get_embedding_client,
)
from autonomous_trading_analyst.memory.store import EpisodicMemory
from autonomous_trading_analyst.memory.tool import build_recall_memory_tool
from autonomous_trading_analyst.persistence.repositories import (
    DecisionRepository,
    FillRepository,
    OrderRepository,
    PortfolioRepository,
)
from autonomous_trading_analyst.risk.manager import RiskManager
from autonomous_trading_analyst.tools.builtins import build_market_tools_registry
from autonomous_trading_analyst.tools.market_data import (
    MarketDataProvider,
    get_market_data_provider,
)
from autonomous_trading_analyst.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


class AnalysisCycleOrchestrator:
    """End-to-end trading cycle orchestrator executing watchlist analysis and execution."""

    def __init__(
        self,
        agent: ReActAgent,
        risk_manager: RiskManager,
        broker: PaperBroker,
        market_data_provider: MarketDataProvider,
        session_factory: sessionmaker[Session],
        memory: EpisodicMemory,
        settings: Settings | None = None,
    ) -> None:
        self.agent = agent
        self.risk_manager = risk_manager
        self.broker = broker
        self.market_data_provider = market_data_provider
        self.session_factory = session_factory
        self.memory = memory
        self.settings = settings if settings is not None else get_settings()

        self.decision_repo = DecisionRepository(session_factory)
        self.order_repo = OrderRepository(session_factory)
        self.fill_repo = FillRepository(session_factory)
        self.portfolio_repo = PortfolioRepository(session_factory)

    async def run_cycle(
        self,
        watchlist: list[str] | None = None,
        as_of: datetime | None = None,
    ) -> CycleSummary:
        """Execute complete analysis cycle: prices -> stop-loss -> agent -> risk -> broker."""
        cycle_time = as_of if as_of is not None else datetime.now(UTC)
        cycle_id = f"cycle_{uuid.uuid4().hex[:12]}"
        tickers = [
            s.strip().upper()
            for s in (watchlist if watchlist is not None else self.settings.watchlist)
            if s.strip()
        ]

        # 1. Fetch current prices for watchlist and existing holdings
        current_prices: dict[str, float] = {}
        relevant_tickers = set(tickers) | set(self.broker.positions.keys())
        for ticker in relevant_tickers:
            try:
                price = self.market_data_provider.get_latest_price(ticker)
                if price > 0.0:
                    current_prices[ticker] = float(price)
            except Exception as exc:
                logger.debug("Failed to fetch price for %s: %s", ticker, exc)

        portfolio_state = self.broker.mark_to_market(current_prices)

        # 2. Stop-loss sweep
        stop_orders = self.risk_manager.check_stop_losses(portfolio_state, current_prices)
        executed_stop_orders: list[Order] = []
        stop_fills: list[Fill] = []

        for stop_order in stop_orders:
            self.order_repo.save(stop_order)
            executed_stop_orders.append(stop_order)
            m_price = current_prices.get(stop_order.ticker, 0.0)
            fill = self.broker.execute_order(stop_order, market_price=m_price)
            if fill is not None:
                self.fill_repo.save(fill)
                stop_fills.append(fill)

        if stop_fills:
            portfolio_state = self.broker.mark_to_market(current_prices)

        # 3. Analyze each watchlist ticker
        decisions: list[DecisionRecord] = []
        regular_orders: list[Order] = []
        regular_fills: list[Fill] = []
        errors: dict[str, str] = {}
        trades_today = len(self.broker.fills)
        total_cost_usd = 0.0
        total_tokens = 0

        for ticker in tickers:
            try:
                scratchpad = await self.agent.run(ticker)
                total_cost_usd += scratchpad.total_cost_usd
                total_tokens += scratchpad.total_tokens

                trace_steps = self._convert_scratchpad_trace(scratchpad)
                signal_data = self._resolve_signal(scratchpad, ticker, cycle_time)
                action = signal_data.action
                rationale = signal_data.rationale

                decision_id = f"dec_{uuid.uuid4().hex[:12]}"
                decision = DecisionRecord(
                    decision_id=decision_id,
                    ticker=ticker,
                    signal=signal_data,
                    trace=trace_steps,
                    total_cost_usd=scratchpad.total_cost_usd,
                    total_tokens=scratchpad.total_tokens,
                    created_at=cycle_time,
                )
                self.decision_repo.save(decision)
                decisions.append(decision)

                # Store episodic memory setup
                context_text = self._build_context_text(scratchpad, ticker, rationale)
                self.memory.store_episode(
                    ticker=ticker,
                    context_text=context_text,
                    action=action.value,
                    rationale=rationale,
                    decision_id=decision_id,
                    created_at=cycle_time,
                )

                # Evaluate risk and execute trade if approved
                m_price = current_prices.get(ticker, 0.0)
                eval_order = self.risk_manager.evaluate_signal(
                    signal=signal_data,
                    portfolio=portfolio_state,
                    current_price=m_price,
                    trades_today=trades_today,
                )

                if eval_order is not None:
                    eval_order = eval_order.model_copy(update={"decision_id": decision_id})
                    self.order_repo.save(eval_order)
                    regular_orders.append(eval_order)

                    if eval_order.status in (OrderStatus.APPROVED, OrderStatus.RESIZED):
                        fill = self.broker.execute_order(eval_order, market_price=m_price)
                        if fill is not None:
                            self.fill_repo.save(fill)
                            regular_fills.append(fill)
                            trades_today += 1
                            portfolio_state = self.broker.mark_to_market(current_prices)

            except Exception as exc:
                errors[ticker] = f"{type(exc).__name__}: {exc}"

        # 4. Persist end-of-cycle portfolio snapshot
        self.portfolio_repo.save(portfolio_state)

        return CycleSummary(
            cycle_id=cycle_id,
            timestamp=cycle_time,
            watchlist=tickers,
            decisions=decisions,
            orders=regular_orders,
            fills=regular_fills,
            stop_loss_orders=executed_stop_orders,
            portfolio_state=portfolio_state,
            total_cost_usd=round(total_cost_usd, 6),
            total_tokens=total_tokens,
            errors=errors,
        )

    def run_cycle_sync(
        self,
        watchlist: list[str] | None = None,
        as_of: datetime | None = None,
    ) -> CycleSummary:
        """Synchronously execute the full analysis cycle."""
        return asyncio.run(self.run_cycle(watchlist=watchlist, as_of=as_of))

    @staticmethod
    def _convert_scratchpad_trace(scratchpad: Scratchpad) -> list[TraceStep]:
        """Convert agent Scratchpad steps into relational domain TraceSteps."""
        domain_steps: list[TraceStep] = []
        step_number = 1

        for step in scratchpad.steps:
            thought = step.llm_message.content or ""
            tokens = int(step.usage.get("total_tokens", 0)) if step.usage else 0
            cost = float(step.usage.get("cost_usd", 0.0)) if step.usage else 0.0

            if step.llm_message.tool_calls:
                for tc in step.llm_message.tool_calls:
                    matching_obs: str | None = None
                    for obs in step.observations:
                        if obs.tool_call_id == tc.id:
                            matching_obs = obs.content
                            break

                    args_dict = dict(tc.arguments) if isinstance(tc.arguments, dict) else {}
                    domain_steps.append(
                        TraceStep(
                            step_number=step_number,
                            thought=thought,
                            action_name=tc.name,
                            action_args=args_dict,
                            observation_id=tc.id,
                            observation=matching_obs,
                            tokens_used=tokens,
                            cost_usd=cost,
                            timestamp=datetime.now(UTC),
                        )
                    )
                    step_number += 1
            else:
                domain_steps.append(
                    TraceStep(
                        step_number=step_number,
                        thought=thought,
                        action_name=None,
                        action_args={},
                        observation_id=None,
                        observation=None,
                        tokens_used=tokens,
                        cost_usd=cost,
                        timestamp=datetime.now(UTC),
                    )
                )
                step_number += 1

        return domain_steps

    @staticmethod
    def _resolve_signal(scratchpad: Scratchpad, ticker: str, cycle_time: datetime) -> Signal:
        """Extract and validate domain Signal from agent Scratchpad."""
        citations: list[str] = []
        for step in scratchpad.steps:
            for obs in step.observations:
                if obs.tool_call_id:
                    citations.append(obs.tool_call_id)

        if scratchpad.signal is not None:
            act = Action(scratchpad.signal.decision.value)
            conf = scratchpad.signal.confidence
            rat = scratchpad.signal.rationale
            if not citations and act != Action.HOLD:
                citations = ["agent_observation_1"]
            return Signal(
                ticker=ticker,
                action=act,
                size=0.10,
                confidence=conf,
                rationale=rat,
                citations=citations,
                timestamp=cycle_time,
            )

        # Fallback if agent failed to submit a terminal signal
        return Signal(
            ticker=ticker,
            action=Action.HOLD,
            size=0.0,
            confidence=0.5,
            rationale="Agent reached step budget without submitting terminal signal.",
            citations=[],
            timestamp=cycle_time,
        )

    @staticmethod
    def _build_context_text(scratchpad: Scratchpad, ticker: str, rationale: str) -> str:
        """Build summarized text representation for episodic memory vector embedding."""
        parts = [f"Analysis for ticker {ticker}:"]
        for step in scratchpad.steps:
            if step.llm_message.content:
                parts.append(f"Thought: {step.llm_message.content}")
            for obs in step.observations:
                if obs.content:
                    snippet = obs.content[:300].strip()
                    parts.append(f"Observation: {snippet}")
        parts.append(f"Final Decision Rationale: {rationale}")
        return "\n".join(parts)


def create_analysis_cycle(
    session_factory: sessionmaker[Session],
    market_data_provider: MarketDataProvider | None = None,
    llm_client: LLMClient | None = None,
    embedding_client: EmbeddingClient | None = None,
    tool_registry: ToolRegistry | None = None,
    paper_broker: PaperBroker | None = None,
    risk_manager: RiskManager | None = None,
    settings: Settings | None = None,
) -> AnalysisCycleOrchestrator:
    """Factory creating an AnalysisCycleOrchestrator with all dependencies wired."""
    cfg = settings if settings is not None else get_settings()
    data_provider = (
        market_data_provider
        if market_data_provider is not None
        else get_market_data_provider(cfg.market_data_provider)
    )
    llm = llm_client if llm_client is not None else get_llm_client(cfg)
    emb = embedding_client if embedding_client is not None else get_embedding_client(cfg)
    broker = paper_broker if paper_broker is not None else PaperBroker(settings=cfg)
    risk = risk_manager if risk_manager is not None else RiskManager(settings=cfg)

    memory = EpisodicMemory(
        session_factory=session_factory,
        embedding_client=emb,
        settings=cfg,
    )

    if tool_registry is not None:
        registry = tool_registry
    else:
        registry = build_market_tools_registry(market_data_provider=data_provider)
        build_recall_memory_tool(memory=memory, registry=registry)

    agent = ReActAgent(
        llm_client=llm,
        tool_registry=registry,
        settings=cfg,
    )

    return AnalysisCycleOrchestrator(
        agent=agent,
        risk_manager=risk,
        broker=broker,
        market_data_provider=data_provider,
        session_factory=session_factory,
        memory=memory,
        settings=cfg,
    )
