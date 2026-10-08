"""Evaluation, performance metrics, baselines, and point-in-time backtesting module."""

from autonomous_trading_analyst.evaluation.backtest import (
    BacktestEngine,
    PointInTimeMarketDataProvider,
    create_backtest_engine,
)
from autonomous_trading_analyst.evaluation.baselines import (
    BaselineStrategy,
    BuyAndHoldStrategy,
    SMACrossoverStrategy,
    run_baseline_simulation,
)
from autonomous_trading_analyst.evaluation.metrics import (
    calculate_drawdowns,
    compute_decision_metrics,
    compute_equity_metrics,
    compute_performance_metrics,
)
from autonomous_trading_analyst.evaluation.models import (
    BacktestConfig,
    BacktestResult,
    PerformanceMetrics,
    TradeRecord,
)
from autonomous_trading_analyst.evaluation.trades import (
    compute_trade_statistics,
    extract_trades_from_fills,
)

__all__ = [
    "BacktestConfig",
    "BacktestEngine",
    "BacktestResult",
    "BaselineStrategy",
    "BuyAndHoldStrategy",
    "PerformanceMetrics",
    "PointInTimeMarketDataProvider",
    "SMACrossoverStrategy",
    "TradeRecord",
    "calculate_drawdowns",
    "compute_decision_metrics",
    "compute_equity_metrics",
    "compute_performance_metrics",
    "compute_trade_statistics",
    "create_backtest_engine",
    "extract_trades_from_fills",
    "run_baseline_simulation",
]
