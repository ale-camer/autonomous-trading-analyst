"""Outcome reflection engine scoring past trading decisions with realized forward returns."""

from datetime import UTC, datetime, timedelta

from autonomous_trading_analyst.config import Settings, get_settings
from autonomous_trading_analyst.domain.models import Action
from autonomous_trading_analyst.domain.reflection import ReflectionReport, ScoredOutcome
from autonomous_trading_analyst.memory.store import EpisodicMemory
from autonomous_trading_analyst.persistence.repositories import DecisionRepository
from autonomous_trading_analyst.tools.market_data import MarketDataProvider


class OutcomeReflector:
    """Evaluates past trading decisions over forward horizons and persists realized outcomes."""

    def __init__(
        self,
        decision_repo: DecisionRepository,
        memory: EpisodicMemory,
        market_data_provider: MarketDataProvider,
        settings: Settings | None = None,
    ) -> None:
        self.decision_repo = decision_repo
        self.memory = memory
        self.market_data_provider = market_data_provider
        self.settings = settings if settings is not None else get_settings()

    def compute_forward_return(
        self,
        ticker: str,
        action: Action | str,
        start_time: datetime,
        horizon_days: int,
        as_of: datetime | None = None,
    ) -> tuple[float, float, float] | None:
        """Calculate forward start price, end price, and directional return over horizon days.

        Returns:
            A tuple of (start_price, end_price, directional_return), or None if unmatured
            or market data is insufficient.
        """
        raw_eval = as_of if as_of is not None else datetime.now(UTC)
        eval_time = (
            raw_eval.replace(tzinfo=UTC) if raw_eval.tzinfo is None else raw_eval.astimezone(UTC)
        )
        clean_start = (
            start_time.replace(tzinfo=UTC)
            if start_time.tzinfo is None
            else start_time.astimezone(UTC)
        )
        target_end_time = clean_start + timedelta(days=horizon_days)

        if target_end_time > eval_time:
            # Horizon has not yet elapsed
            return None

        clean_ticker = ticker.strip().upper()
        act = action if isinstance(action, Action) else Action(action.strip().upper())

        try:
            # Request bars covering from clean_start up to target_end_time plus buffer for weekends
            search_end = min(target_end_time + timedelta(days=3), eval_time)
            df = self.market_data_provider.get_bars(
                ticker=clean_ticker,
                start=clean_start,
                end=search_end,
                interval="1d",
            )
        except Exception:
            return None

        if df.empty or len(df) < 1:
            return None

        # Start price is the close of the first bar on or after start_time
        start_price = float(df.iloc[0]["close"])
        if start_price <= 0.0:
            return None

        # Filter bars up to target_end_time + 1 day
        mature_bars = df[df.index <= target_end_time]
        if mature_bars.empty:
            end_price = float(df.iloc[-1]["close"])
        else:
            end_price = float(mature_bars.iloc[-1]["close"])

        if end_price <= 0.0:
            return None

        if act == Action.BUY:
            raw_return = (end_price - start_price) / start_price
        elif act == Action.SELL:
            # Profit from avoiding a decline or profit from short thesis
            raw_return = (start_price - end_price) / start_price
        else:
            # Neutral baseline for HOLD decisions
            raw_return = 0.0

        return start_price, end_price, raw_return

    def reflect(
        self,
        as_of: datetime | None = None,
        horizon_days: int | None = None,
        limit: int | None = None,
    ) -> ReflectionReport:
        """Evaluate pending decisions and persist outcomes to repository and episodic memory."""
        eff_horizon = (
            horizon_days if horizon_days is not None else self.settings.reflection_horizon_days
        )
        eff_limit = limit if limit is not None else self.settings.reflection_batch_size
        eval_time = as_of if as_of is not None else datetime.now(UTC)

        pending_decisions = self.decision_repo.list_pending_reflection(
            as_of=eval_time,
            horizon_days=eff_horizon,
            limit=eff_limit,
        )

        scored_outcomes: list[ScoredOutcome] = []
        skipped_count = 0

        for decision in pending_decisions:
            result = self.compute_forward_return(
                ticker=decision.ticker,
                action=decision.signal.action,
                start_time=decision.created_at,
                horizon_days=eff_horizon,
                as_of=eval_time,
            )

            if result is None:
                skipped_count += 1
                continue

            start_price, end_price, realized_return = result
            rounded_return = round(realized_return, 6)

            # Persist outcome to decision repository
            self.decision_repo.update_outcome(decision.decision_id, rounded_return)

            # Persist outcome to episodic memory
            self.memory.update_outcome_by_decision(decision.decision_id, rounded_return)

            scored_outcomes.append(
                ScoredOutcome(
                    decision_id=decision.decision_id,
                    ticker=decision.ticker,
                    action=decision.signal.action,
                    horizon_days=eff_horizon,
                    start_price=start_price,
                    end_price=end_price,
                    realized_return=rounded_return,
                    evaluated_at=eval_time,
                )
            )

        # Also reflect on any standalone episodes without decision_id
        pending_episodes = self.memory.list_pending_episodes(
            as_of=eval_time,
            horizon_days=eff_horizon,
            limit=eff_limit,
        )
        for ep in pending_episodes:
            if ep.decision_id is not None:
                # Already processed or linked
                continue

            act = Action(ep.action) if ep.action in Action.__members__ else Action.HOLD
            ep_result = self.compute_forward_return(
                ticker=ep.ticker,
                action=act,
                start_time=ep.created_at,
                horizon_days=eff_horizon,
                as_of=eval_time,
            )
            if ep_result is not None:
                _, _, ep_ret = ep_result
                self.memory.update_outcome(ep.episode_id, round(ep_ret, 6))

        return ReflectionReport(
            total_candidates=len(pending_decisions),
            scored_count=len(scored_outcomes),
            skipped_count=skipped_count,
            scored_outcomes=scored_outcomes,
            executed_at=eval_time,
        )
