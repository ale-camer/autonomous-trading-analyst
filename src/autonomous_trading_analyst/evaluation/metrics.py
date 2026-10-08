"""Financial, risk, trade, and system performance metrics calculation engine."""

import math
from collections.abc import Sequence
from typing import Any

import numpy as np
import pandas as pd

from autonomous_trading_analyst.domain.models import DecisionRecord, Fill, PortfolioState
from autonomous_trading_analyst.evaluation.models import PerformanceMetrics
from autonomous_trading_analyst.evaluation.trades import (
    compute_trade_statistics,
    extract_trades_from_fills,
)


def calculate_drawdowns(equity: pd.Series) -> tuple[pd.Series, float, int]:
    """Calculate drawdown series, peak maximum drawdown percentage, and max duration in days.

    Returns:
        A tuple of (drawdown_series, max_drawdown_fraction, max_duration_periods).
    """
    if equity.empty or len(equity) < 2:
        empty_dd = pd.Series(dtype=float) if equity.empty else pd.Series([0.0], index=equity.index)
        return empty_dd, 0.0, 0

    cummax = equity.cummax()
    drawdown = (equity - cummax) / cummax
    max_dd = float(abs(drawdown.min())) if not drawdown.empty else 0.0

    # Calculate max duration in periods where equity remains below peak
    max_duration = 0
    current_duration = 0
    for dd in drawdown:
        if dd < 0.0:
            current_duration += 1
            if current_duration > max_duration:
                max_duration = current_duration
        else:
            current_duration = 0

    return drawdown, round(max_dd, 6), max_duration


def compute_equity_metrics(
    equity: pd.Series | Sequence[PortfolioState] | Sequence[float],
    risk_free_rate: float = 0.0,
) -> dict[str, Any]:
    """Compute financial returns, volatility, risk-adjusted ratios, and drawdowns."""
    if isinstance(equity, pd.Series):
        series = equity.astype(float)
    elif isinstance(equity, Sequence) and len(equity) > 0 and isinstance(equity[0], PortfolioState):
        dates = [p.updated_at for p in equity]  # type: ignore[union-attr]
        values = [p.total_equity for p in equity]  # type: ignore[union-attr]
        series = pd.Series(values, index=pd.to_datetime(dates, utc=True), dtype=float)
    elif isinstance(equity, Sequence):
        series = pd.Series(list(equity), dtype=float)
    else:
        series = pd.Series(dtype=float)

    if series.empty:
        return {
            "start_equity": 0.0,
            "end_equity": 0.0,
            "total_return": 0.0,
            "annualized_return": 0.0,
            "annualized_volatility": 0.0,
            "sharpe_ratio": 0.0,
            "sortino_ratio": 0.0,
            "max_drawdown": 0.0,
            "max_drawdown_duration_days": 0,
            "calmar_ratio": 0.0,
        }

    start_equity = float(series.iloc[0])
    end_equity = float(series.iloc[-1])

    if len(series) == 1:
        return {
            "start_equity": start_equity,
            "end_equity": end_equity,
            "total_return": 0.0,
            "annualized_return": 0.0,
            "annualized_volatility": 0.0,
            "sharpe_ratio": 0.0,
            "sortino_ratio": 0.0,
            "max_drawdown": 0.0,
            "max_drawdown_duration_days": 0,
            "calmar_ratio": 0.0,
        }

    total_return = (end_equity - start_equity) / start_equity if start_equity > 0 else 0.0
    daily_returns = series.pct_change().dropna()
    n_periods = len(daily_returns)

    # Annualized CAGR return assuming 252 trading periods per year
    if n_periods > 0 and total_return > -1.0:
        annualized_return = (1.0 + total_return) ** (252.0 / max(n_periods, 1)) - 1.0
    else:
        annualized_return = total_return

    # Volatility
    if n_periods > 1:
        daily_std = float(daily_returns.std(ddof=1))
        if math.isnan(daily_std):
            daily_std = 0.0
    else:
        daily_std = 0.0

    annualized_vol = daily_std * math.sqrt(252.0)

    # Sharpe ratio
    if annualized_vol > 1e-9:
        sharpe_ratio = (annualized_return - risk_free_rate) / annualized_vol
    else:
        sharpe_ratio = 0.0

    # Sortino ratio
    downside_returns = daily_returns[daily_returns < 0.0]
    if not downside_returns.empty:
        downside_std = float(np.sqrt(np.mean(downside_returns**2))) * math.sqrt(252.0)
        sortino_ratio = (
            (annualized_return - risk_free_rate) / downside_std if downside_std > 1e-9 else 0.0
        )
    else:
        sortino_ratio = sharpe_ratio if sharpe_ratio > 0 else 0.0

    # Drawdown metrics
    _, max_dd, max_dd_days = calculate_drawdowns(series)

    # Calmar ratio
    calmar_ratio = annualized_return / max_dd if max_dd > 1e-9 else 0.0

    return {
        "start_equity": round(start_equity, 2),
        "end_equity": round(end_equity, 2),
        "total_return": round(total_return, 6),
        "annualized_return": round(annualized_return, 6),
        "annualized_volatility": round(annualized_vol, 6),
        "sharpe_ratio": round(sharpe_ratio, 4),
        "sortino_ratio": round(sortino_ratio, 4),
        "max_drawdown": round(max_dd, 6),
        "max_drawdown_duration_days": max_dd_days,
        "calmar_ratio": round(calmar_ratio, 4),
    }


def compute_decision_metrics(
    decisions: Sequence[DecisionRecord] | None = None,
) -> dict[str, Any]:
    """Aggregate agent token consumption and USD expenses across decisions."""
    if not decisions:
        return {
            "total_decisions": 0,
            "total_cost_usd": 0.0,
            "cost_per_decision": 0.0,
            "total_tokens": 0,
            "tokens_per_decision": 0.0,
        }

    total_decisions = len(decisions)
    total_cost = sum(d.total_cost_usd for d in decisions)
    total_tokens = sum(d.total_tokens for d in decisions)

    cost_per_decision = total_cost / total_decisions if total_decisions > 0 else 0.0
    tokens_per_decision = float(total_tokens) / total_decisions if total_decisions > 0 else 0.0

    return {
        "total_decisions": total_decisions,
        "total_cost_usd": round(total_cost, 6),
        "cost_per_decision": round(cost_per_decision, 6),
        "total_tokens": total_tokens,
        "tokens_per_decision": round(tokens_per_decision, 2),
    }


def compute_performance_metrics(
    equity_curve: pd.Series | Sequence[PortfolioState] | Sequence[float],
    fills: Sequence[Fill] | None = None,
    decisions: Sequence[DecisionRecord] | None = None,
    risk_free_rate: float = 0.0,
) -> PerformanceMetrics:
    """Combine equity curve, execution fills, and decisions into unified PerformanceMetrics."""
    equity_stats = compute_equity_metrics(equity_curve, risk_free_rate=risk_free_rate)

    if fills:
        trades = extract_trades_from_fills(fills)
        trade_stats = compute_trade_statistics(trades)
    else:
        trade_stats = compute_trade_statistics([])

    decision_stats = compute_decision_metrics(decisions)

    return PerformanceMetrics(
        start_equity=equity_stats["start_equity"],
        end_equity=equity_stats["end_equity"],
        total_return=equity_stats["total_return"],
        annualized_return=equity_stats["annualized_return"],
        annualized_volatility=equity_stats["annualized_volatility"],
        sharpe_ratio=equity_stats["sharpe_ratio"],
        sortino_ratio=equity_stats["sortino_ratio"],
        max_drawdown=equity_stats["max_drawdown"],
        max_drawdown_duration_days=equity_stats["max_drawdown_duration_days"],
        calmar_ratio=equity_stats["calmar_ratio"],
        total_trades=trade_stats["total_trades"],
        winning_trades=trade_stats["winning_trades"],
        losing_trades=trade_stats["losing_trades"],
        win_rate=trade_stats["win_rate"],
        profit_factor=trade_stats["profit_factor"],
        average_trade_pnl=trade_stats["average_trade_pnl"],
        average_win_pnl=trade_stats["average_win_pnl"],
        average_loss_pnl=trade_stats["average_loss_pnl"],
        total_decisions=decision_stats["total_decisions"],
        total_cost_usd=decision_stats["total_cost_usd"],
        cost_per_decision=decision_stats["cost_per_decision"],
        total_tokens=decision_stats["total_tokens"],
        tokens_per_decision=decision_stats["tokens_per_decision"],
    )
