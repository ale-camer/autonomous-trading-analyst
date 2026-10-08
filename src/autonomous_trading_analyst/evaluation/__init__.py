"""Evaluation and quantitative performance metrics module."""

from autonomous_trading_analyst.evaluation.metrics import (
    calculate_drawdowns,
    compute_decision_metrics,
    compute_equity_metrics,
    compute_performance_metrics,
)
from autonomous_trading_analyst.evaluation.models import (
    PerformanceMetrics,
    TradeRecord,
)
from autonomous_trading_analyst.evaluation.trades import (
    compute_trade_statistics,
    extract_trades_from_fills,
)

__all__ = [
    "PerformanceMetrics",
    "TradeRecord",
    "calculate_drawdowns",
    "compute_decision_metrics",
    "compute_equity_metrics",
    "compute_performance_metrics",
    "compute_trade_statistics",
    "extract_trades_from_fills",
]
