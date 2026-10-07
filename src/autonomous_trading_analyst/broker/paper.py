"""Simulated paper broker for order execution and portfolio accounting."""

import uuid
from datetime import UTC, datetime

from autonomous_trading_analyst.config import Settings, get_settings
from autonomous_trading_analyst.domain.models import (
    Action,
    Fill,
    Order,
    OrderStatus,
    PortfolioState,
    Position,
)


class PaperBroker:
    """Simulated execution broker managing fills, slippage, commission, and portfolio state."""

    def __init__(
        self,
        settings: Settings | None = None,
        initial_cash: float | None = None,
    ) -> None:
        """Initialize PaperBroker with application settings and starting cash balance."""
        self.settings = settings if settings is not None else get_settings()
        self._cash = float(
            initial_cash if initial_cash is not None else self.settings.paper_initial_cash
        )
        self._positions: dict[str, Position] = {}
        self._fills: list[Fill] = []
        self._history: list[PortfolioState] = []
        self._total_realized_pnl: float = 0.0

    @property
    def cash(self) -> float:
        """Current uninvested cash balance."""
        return self._cash

    @property
    def positions(self) -> dict[str, Position]:
        """Dictionary of currently open positions."""
        return dict(self._positions)

    @property
    def fills(self) -> list[Fill]:
        """Audit log of all executed trade fills."""
        return list(self._fills)

    @property
    def history(self) -> list[PortfolioState]:
        """Historical portfolio state snapshots."""
        return list(self._history)

    @property
    def total_realized_pnl(self) -> float:
        """Cumulative net realized profit and loss across all closed trades."""
        return self._total_realized_pnl

    @property
    def total_unrealized_pnl(self) -> float:
        """Sum of unrealized profits and losses across currently open positions."""
        return sum(pos.unrealized_pnl for pos in self._positions.values())

    @property
    def total_equity(self) -> float:
        """Total portfolio equity including cash and mark-to-market positions."""
        return self.get_portfolio_state().total_equity

    def get_portfolio_state(self) -> PortfolioState:
        """Return an immutable snapshot of current cash, positions, equity, and exposure."""
        return PortfolioState.create(
            cash=self._cash,
            positions=dict(self._positions),
            updated_at=datetime.now(UTC),
        )

    def execute_order(self, order: Order, market_price: float) -> Fill | None:
        """
        Execute an approved or resized order against current market price with slippage and fees.

        Returns Fill on execution, or None if order is rejected, unapproved, or invalid.
        """
        if order.status not in (OrderStatus.APPROVED, OrderStatus.RESIZED):
            return None

        if order.action not in (Action.BUY, Action.SELL):
            return None

        if market_price <= 0.0 or order.shares <= 0.0:
            return None

        clean_ticker = order.ticker.strip().upper()
        slippage_rate = self.settings.paper_slippage_bps / 10000.0
        commission_rate = self.settings.paper_commission_bps / 10000.0

        if order.action == Action.BUY:
            exec_price = market_price * (1.0 + slippage_rate)
            gross_value = order.shares * exec_price
            commission_usd = gross_value * commission_rate
            slippage_usd = abs(exec_price - market_price) * order.shares
            total_required_cash = gross_value + commission_usd

            if self._cash < total_required_cash:
                return None

            self._cash -= total_required_cash

            if clean_ticker in self._positions:
                existing = self._positions[clean_ticker]
                new_shares = existing.shares + order.shares
                new_avg_entry = (
                    (existing.shares * existing.average_entry_price) + (order.shares * exec_price)
                ) / new_shares
                unrealized = (market_price - new_avg_entry) * new_shares

                self._positions[clean_ticker] = Position(
                    ticker=clean_ticker,
                    shares=new_shares,
                    average_entry_price=new_avg_entry,
                    current_price=market_price,
                    unrealized_pnl=unrealized,
                    realized_pnl=existing.realized_pnl,
                )
            else:
                unrealized = (market_price - exec_price) * order.shares
                self._positions[clean_ticker] = Position(
                    ticker=clean_ticker,
                    shares=order.shares,
                    average_entry_price=exec_price,
                    current_price=market_price,
                    unrealized_pnl=unrealized,
                    realized_pnl=0.0,
                )

            executed_shares = order.shares

        else:
            # Action.SELL
            if clean_ticker not in self._positions:
                return None

            existing_pos = self._positions[clean_ticker]
            if existing_pos.shares <= 0.0:
                return None

            executed_shares = min(order.shares, existing_pos.shares)
            exec_price = market_price * (1.0 - slippage_rate)
            gross_value = executed_shares * exec_price
            commission_usd = gross_value * commission_rate
            slippage_usd = abs(exec_price - market_price) * executed_shares

            net_proceeds = gross_value - commission_usd
            self._cash += net_proceeds

            cost_basis = executed_shares * existing_pos.average_entry_price
            trade_realized_pnl = gross_value - cost_basis - commission_usd
            self._total_realized_pnl += trade_realized_pnl
            new_position_realized = existing_pos.realized_pnl + trade_realized_pnl

            remaining_shares = existing_pos.shares - executed_shares
            if remaining_shares <= 1e-9:
                del self._positions[clean_ticker]
            else:
                unrealized = (market_price - existing_pos.average_entry_price) * remaining_shares
                self._positions[clean_ticker] = Position(
                    ticker=clean_ticker,
                    shares=remaining_shares,
                    average_entry_price=existing_pos.average_entry_price,
                    current_price=market_price,
                    unrealized_pnl=unrealized,
                    realized_pnl=new_position_realized,
                )

        fill = Fill(
            fill_id=f"fill_{uuid.uuid4().hex[:8]}",
            order_id=order.order_id,
            ticker=clean_ticker,
            action=order.action,
            shares=executed_shares,
            price=exec_price,
            commission=commission_usd,
            slippage=slippage_usd,
            executed_at=datetime.now(UTC),
        )
        self._fills.append(fill)

        snapshot = self.get_portfolio_state()
        self._history.append(snapshot)

        return fill

    def mark_to_market(self, current_prices: dict[str, float]) -> PortfolioState:
        """
        Revalue all open positions based on latest market prices and record snapshot.
        """
        for ticker, pos in list(self._positions.items()):
            if ticker in current_prices and current_prices[ticker] > 0.0:
                new_price = current_prices[ticker]
                unrealized = (new_price - pos.average_entry_price) * pos.shares
                self._positions[ticker] = Position(
                    ticker=ticker,
                    shares=pos.shares,
                    average_entry_price=pos.average_entry_price,
                    current_price=new_price,
                    unrealized_pnl=unrealized,
                    realized_pnl=pos.realized_pnl,
                )

        snapshot = self.get_portfolio_state()
        self._history.append(snapshot)
        return snapshot

    def reset(self, initial_cash: float | None = None) -> None:
        """Reset the broker to an empty initial state."""
        self._cash = float(
            initial_cash if initial_cash is not None else self.settings.paper_initial_cash
        )
        self._positions.clear()
        self._fills.clear()
        self._history.clear()
        self._total_realized_pnl = 0.0
