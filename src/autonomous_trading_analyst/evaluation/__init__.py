"""Evaluation, performance metrics, baselines, and point-in-time backtesting module."""

from collections.abc import Sequence

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
from autonomous_trading_analyst.evaluation.report import (
    export_report,
    generate_json_report,
    generate_markdown_report,
)
from autonomous_trading_analyst.evaluation.trades import (
    compute_trade_statistics,
    extract_trades_from_fills,
)


def cli_main(args: Sequence[str] | None = None) -> int:
    """Execute the backtest command-line interface entry point."""
    from autonomous_trading_analyst.evaluation.cli import main

    return main(args)


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
    "cli_main",
    "compute_decision_metrics",
    "compute_equity_metrics",
    "compute_performance_metrics",
    "compute_trade_statistics",
    "create_backtest_engine",
    "export_report",
    "extract_trades_from_fills",
    "generate_json_report",
    "generate_markdown_report",
    "run_baseline_simulation",
]
