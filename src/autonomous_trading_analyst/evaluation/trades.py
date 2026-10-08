"""Trade round-trip extraction from execution fills and statistical trade metrics."""

from collections import defaultdict
from collections.abc import Sequence
from typing import Any

from autonomous_trading_analyst.domain.models import Action, Fill
from autonomous_trading_analyst.evaluation.models import TradeRecord


def extract_trades_from_fills(fills: Sequence[Fill]) -> list[TradeRecord]:
    """Parse execution fills using FIFO accounting to reconstruct closed round-trip trades."""
    sorted_fills = sorted(fills, key=lambda f: f.executed_at)
    inventory: dict[str, list[dict[str, Any]]] = defaultdict(list)
    closed_trades: list[TradeRecord] = []

    for fill in sorted_fills:
        symbol = fill.ticker.strip().upper()

        if fill.action == Action.BUY:
            comm_per_share = fill.commission / fill.shares if fill.shares > 0 else 0.0
            inventory[symbol].append(
                {
                    "shares": fill.shares,
                    "price": fill.price,
                    "time": fill.executed_at,
                    "commission_per_share": comm_per_share,
                }
            )
        elif fill.action == Action.SELL:
            remaining_to_close = fill.shares
            sell_comm_per_share = fill.commission / fill.shares if fill.shares > 0 else 0.0

            while remaining_to_close > 1e-9 and inventory[symbol]:
                open_lot = inventory[symbol][0]
                matched_shares = min(remaining_to_close, open_lot["shares"])
                entry_price = float(open_lot["price"])
                exit_price = float(fill.price)
                entry_time = open_lot["time"]
                exit_time = fill.executed_at

                total_commission = (
                    open_lot["commission_per_share"] + sell_comm_per_share
                ) * matched_shares
                pnl = (exit_price - entry_price) * matched_shares - total_commission
                cost_basis = entry_price * matched_shares
                return_pct = pnl / cost_basis if cost_basis > 0 else 0.0

                closed_trades.append(
                    TradeRecord(
                        ticker=symbol,
                        entry_time=entry_time,
                        exit_time=exit_time,
                        entry_price=entry_price,
                        exit_price=exit_price,
                        shares=matched_shares,
                        pnl=round(pnl, 4),
                        return_pct=round(return_pct, 6),
                        commission=round(total_commission, 4),
                    )
                )

                open_lot["shares"] -= matched_shares
                remaining_to_close -= matched_shares

                if open_lot["shares"] <= 1e-9:
                    inventory[symbol].pop(0)

    return closed_trades


def compute_trade_statistics(trades: Sequence[TradeRecord]) -> dict[str, Any]:
    """Calculate aggregated trade performance metrics including win rate and profit factor."""
    total_trades = len(trades)
    if total_trades == 0:
        return {
            "total_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "win_rate": 0.0,
            "profit_factor": None,
            "average_trade_pnl": 0.0,
            "average_win_pnl": 0.0,
            "average_loss_pnl": 0.0,
        }

    winning_trades = [t for t in trades if t.pnl > 0.0]
    losing_trades = [t for t in trades if t.pnl < 0.0]

    gross_profit = sum(t.pnl for t in winning_trades)
    gross_loss = abs(sum(t.pnl for t in losing_trades))

    win_rate = len(winning_trades) / total_trades

    if gross_loss > 0.0:
        profit_factor: float | None = round(gross_profit / gross_loss, 4)
    else:
        profit_factor = None

    average_trade_pnl = sum(t.pnl for t in trades) / total_trades
    average_win_pnl = gross_profit / len(winning_trades) if winning_trades else 0.0
    average_loss_pnl = -gross_loss / len(losing_trades) if losing_trades else 0.0

    return {
        "total_trades": total_trades,
        "winning_trades": len(winning_trades),
        "losing_trades": len(losing_trades),
        "win_rate": round(win_rate, 4),
        "profit_factor": profit_factor,
        "average_trade_pnl": round(average_trade_pnl, 4),
        "average_win_pnl": round(average_win_pnl, 4),
        "average_loss_pnl": round(average_loss_pnl, 4),
    }
