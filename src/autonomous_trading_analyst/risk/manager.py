"""Deterministic risk manager and guardrails outside the LLM."""

import uuid
from datetime import UTC, datetime

from autonomous_trading_analyst.agent.signal import SignalDecision, TradingSignal
from autonomous_trading_analyst.config import Settings, get_settings
from autonomous_trading_analyst.domain.models import (
    Action,
    Order,
    OrderStatus,
    PortfolioState,
    Signal,
)


class RiskManager:
    """Deterministic gatekeeper enforcing portfolio risk limits and order guardrails."""

    def __init__(self, settings: Settings | None = None) -> None:
        """Initialize RiskManager with typed application settings."""
        self.settings = settings if settings is not None else get_settings()

    def evaluate_order(
        self,
        order: Order,
        portfolio: PortfolioState,
        current_price: float,
        trades_today: int = 0,
    ) -> Order:
        """
        Evaluate a proposed order against deterministic risk guardrails.

        Returns a modified Order with status APPROVED, RESIZED, or REJECTED and explicit reason.
        """
        clean_ticker = order.ticker.strip().upper()

        if current_price <= 0.0:
            return order.model_copy(
                update={
                    "status": OrderStatus.REJECTED,
                    "reason": f"Current price must be positive, got {current_price}.",
                }
            )

        # 1. Watchlist-only check
        if clean_ticker not in self.settings.watchlist:
            return order.model_copy(
                update={
                    "status": OrderStatus.REJECTED,
                    "reason": f"Ticker '{clean_ticker}' is not in configured watchlist.",
                }
            )

        # 2. Daily trades limit check
        if trades_today >= self.settings.risk_max_trades_per_day:
            return order.model_copy(
                update={
                    "status": OrderStatus.REJECTED,
                    "reason": (
                        f"Daily trade limit reached "
                        f"({trades_today}/{self.settings.risk_max_trades_per_day})."
                    ),
                }
            )

        # 3. Action handling
        if order.action == Action.HOLD:
            return order.model_copy(
                update={
                    "status": OrderStatus.REJECTED,
                    "reason": "HOLD action does not generate executable trades.",
                }
            )

        # 4. SELL order checks (no shorting)
        if order.action == Action.SELL:
            pos = portfolio.positions.get(clean_ticker)
            held_shares = pos.shares if pos else 0.0

            if held_shares <= 0.0:
                return order.model_copy(
                    update={
                        "status": OrderStatus.REJECTED,
                        "reason": (
                            f"Shorting is not permitted: no open position in '{clean_ticker}'."
                        ),
                    }
                )

            if order.shares > held_shares:
                return order.model_copy(
                    update={
                        "status": OrderStatus.RESIZED,
                        "shares": held_shares,
                        "reason": (
                            f"Order resized from {order.shares} to {held_shares} shares "
                            "to prevent shorting."
                        ),
                    }
                )

            return order.model_copy(
                update={
                    "status": OrderStatus.APPROVED,
                    "reason": "Sell order approved within position limits.",
                }
            )

        # 5. BUY order checks (position limit, gross exposure, cash / leverage)
        if order.action == Action.BUY:
            if portfolio.total_equity <= 0.0:
                return order.model_copy(
                    update={
                        "status": OrderStatus.REJECTED,
                        "reason": "Portfolio total equity is non-positive.",
                    }
                )

            # Max position limit check
            pos = portfolio.positions.get(clean_ticker)
            current_pos_shares = pos.shares if pos else 0.0
            current_pos_value = current_pos_shares * current_price
            max_pos_value = portfolio.total_equity * self.settings.risk_max_position_pct
            remaining_pos_budget = max_pos_value - current_pos_value

            if remaining_pos_budget <= 0.0:
                return order.model_copy(
                    update={
                        "status": OrderStatus.REJECTED,
                        "reason": (
                            f"Max position size limit "
                            f"({self.settings.risk_max_position_pct:.1%}) reached for "
                            f"'{clean_ticker}'."
                        ),
                    }
                )

            # Max gross exposure limit check
            current_gross_value = sum(p.market_value for p in portfolio.positions.values())
            max_gross_value = portfolio.total_equity * self.settings.risk_max_gross_exposure_pct
            remaining_gross_budget = max_gross_value - current_gross_value

            if remaining_gross_budget <= 0.0:
                return order.model_copy(
                    update={
                        "status": OrderStatus.REJECTED,
                        "reason": (
                            f"Max gross exposure limit "
                            f"({self.settings.risk_max_gross_exposure_pct:.1%}) reached."
                        ),
                    }
                )

            # Cash availability check (no leverage)
            available_cash = portfolio.cash
            if available_cash <= 0.0:
                return order.model_copy(
                    update={
                        "status": OrderStatus.REJECTED,
                        "reason": "Insufficient cash to fund BUY order.",
                    }
                )

            # Max spendable bounded by position budget, gross exposure budget, and available cash
            max_spendable = min(remaining_pos_budget, remaining_gross_budget, available_cash)
            max_allowed_shares = max_spendable / current_price

            if max_allowed_shares <= 0.0:
                return order.model_copy(
                    update={
                        "status": OrderStatus.REJECTED,
                        "reason": "Risk limits allow 0 additional shares.",
                    }
                )

            if order.shares > max_allowed_shares:
                if max_spendable == remaining_pos_budget:
                    constraint = f"max position size ({self.settings.risk_max_position_pct:.1%})"
                elif max_spendable == remaining_gross_budget:
                    constraint = (
                        f"max gross exposure ({self.settings.risk_max_gross_exposure_pct:.1%})"
                    )
                else:
                    constraint = "available cash"

                resized_shares = round(max_allowed_shares, 6)
                if resized_shares <= 0.0:
                    resized_shares = max_allowed_shares

                return order.model_copy(
                    update={
                        "status": OrderStatus.RESIZED,
                        "shares": resized_shares,
                        "reason": (
                            f"Order resized from {order.shares} to {resized_shares} shares "
                            f"due to {constraint} limit."
                        ),
                    }
                )

            return order.model_copy(
                update={
                    "status": OrderStatus.APPROVED,
                    "reason": "Buy order approved within risk limits.",
                }
            )

        return order.model_copy(
            update={
                "status": OrderStatus.REJECTED,
                "reason": f"Unsupported order action: {order.action}.",
            }
        )

    def evaluate_signal(
        self,
        signal: Signal | TradingSignal,
        portfolio: PortfolioState,
        current_price: float,
        trades_today: int = 0,
    ) -> Order | None:
        """Translate an agent signal into a proposed Order and evaluate against guardrails."""
        if current_price <= 0.0 or portfolio.total_equity <= 0.0:
            return None

        clean_ticker = signal.ticker.strip().upper()

        if isinstance(signal, Signal):
            action = signal.action
            size = signal.size
        else:
            if signal.decision == SignalDecision.BUY:
                action = Action.BUY
            elif signal.decision == SignalDecision.SELL:
                action = Action.SELL
            else:
                action = Action.HOLD
            size = self.settings.risk_max_position_pct

        if action == Action.HOLD:
            return None

        order_id = f"ord_{uuid.uuid4().hex[:8]}"

        if action == Action.SELL:
            pos = portfolio.positions.get(clean_ticker)
            held_shares = pos.shares if pos else 0.0
            if held_shares <= 0.0:
                proposed_shares = 1.0  # Rejected by evaluate_order for shorting
            else:
                fraction = size if (isinstance(signal, Signal) and size > 0.0) else 1.0
                proposed_shares = max(held_shares * fraction, 1e-6)

            order = Order(
                order_id=order_id,
                ticker=clean_ticker,
                action=Action.SELL,
                shares=proposed_shares,
                limit_price=None,
                status=OrderStatus.PENDING,
            )
            return self.evaluate_order(order, portfolio, current_price, trades_today)

        # Action.BUY
        fraction = size if size > 0.0 else self.settings.risk_max_position_pct
        target_value = portfolio.total_equity * fraction
        proposed_shares = max(target_value / current_price, 1e-6)

        order = Order(
            order_id=order_id,
            ticker=clean_ticker,
            action=Action.BUY,
            shares=proposed_shares,
            limit_price=None,
            status=OrderStatus.PENDING,
        )
        return self.evaluate_order(order, portfolio, current_price, trades_today)

    def check_stop_losses(
        self,
        portfolio: PortfolioState,
        current_prices: dict[str, float],
    ) -> list[Order]:
        """
        Inspect open positions and generate approved exit orders if unrealized loss breaches limit.
        """
        exit_orders: list[Order] = []

        for ticker, pos in portfolio.positions.items():
            if pos.shares <= 0.0:
                continue

            price = current_prices.get(ticker)
            if price is None or price <= 0.0:
                continue

            if pos.average_entry_price <= 0.0:
                continue

            pnl_pct = (price - pos.average_entry_price) / pos.average_entry_price

            if pnl_pct <= -self.settings.risk_stop_loss_pct:
                order_id = f"stop_{uuid.uuid4().hex[:8]}"
                exit_order = Order(
                    order_id=order_id,
                    ticker=ticker,
                    action=Action.SELL,
                    shares=pos.shares,
                    limit_price=None,
                    status=OrderStatus.APPROVED,
                    reason=(
                        f"Stop-loss triggered: unrealized loss of {abs(pnl_pct):.2%} "
                        f"breaches limit of {self.settings.risk_stop_loss_pct:.2%}."
                    ),
                    created_at=datetime.now(UTC),
                )
                exit_orders.append(exit_order)

        return exit_orders
