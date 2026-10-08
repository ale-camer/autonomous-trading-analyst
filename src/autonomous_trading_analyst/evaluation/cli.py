"""Command-line interface for point-in-time trading backtest evaluation."""

import argparse
import sys
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

from autonomous_trading_analyst.evaluation.backtest import create_backtest_engine
from autonomous_trading_analyst.evaluation.models import BacktestConfig
from autonomous_trading_analyst.evaluation.report import (
    export_report,
    generate_markdown_report,
)
from autonomous_trading_analyst.tools.market_data.base import MarketDataProvider
from autonomous_trading_analyst.tools.market_data.fake import FakeMarketDataProvider
from autonomous_trading_analyst.tools.market_data.yahoo import YahooMarketDataProvider


def parse_args(args: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse command line arguments for the backtest execution CLI."""
    today = datetime.now(UTC).date()
    default_end = today.strftime("%Y-%m-%d")
    default_start = (today - timedelta(days=30)).strftime("%Y-%m-%d")

    parser = argparse.ArgumentParser(
        prog="backtest",
        description="Run point-in-time backtests comparing autonomous agent against baselines.",
    )
    parser.add_argument(
        "--watchlist",
        "-w",
        default="AAPL",
        help="Comma-separated list of ticker symbols (default: AAPL)",
    )
    parser.add_argument(
        "--start-date",
        "-s",
        default=default_start,
        help=f"Backtest start date in YYYY-MM-DD format (default: {default_start})",
    )
    parser.add_argument(
        "--end-date",
        "-e",
        default=default_end,
        help=f"Backtest end date in YYYY-MM-DD format (default: {default_end})",
    )
    parser.add_argument(
        "--initial-cash",
        "-c",
        type=float,
        default=100000.0,
        help="Starting cash portfolio balance in USD (default: 100000.0)",
    )
    parser.add_argument(
        "--risk-free-rate",
        "-r",
        type=float,
        default=0.0,
        help="Annual risk-free rate fraction for Sharpe/Sortino ratios (default: 0.0)",
    )
    parser.add_argument(
        "--output",
        "-o",
        default=None,
        help="Optional path to write generated report file (e.g. reports/run.md)",
    )
    parser.add_argument(
        "--format",
        "-f",
        choices=["markdown", "json"],
        default="markdown",
        help="Output format when saving report: markdown or json (default: markdown)",
    )
    parser.add_argument(
        "--provider",
        "-p",
        choices=["fake", "yahoo"],
        default="fake",
        help="Market data source provider: fake or yahoo (default: fake)",
    )
    return parser.parse_args(args)


def main(args: Sequence[str] | None = None) -> int:
    """Execute backtest workflow from command-line arguments and render comparative report."""
    parsed = parse_args(args)

    try:
        start_dt = datetime.strptime(parsed.start_date, "%Y-%m-%d").replace(tzinfo=UTC)
        end_dt = datetime.strptime(parsed.end_date, "%Y-%m-%d").replace(tzinfo=UTC)
    except ValueError as exc:
        sys.stderr.write(f"Error parsing dates: {exc}\n")
        return 1

    if start_dt > end_dt:
        sys.stderr.write(f"Error: start-date ({start_dt}) cannot be after end-date ({end_dt})\n")
        return 1

    tickers = [t.strip().upper() for t in parsed.watchlist.split(",") if t.strip()]
    if not tickers:
        sys.stderr.write("Error: watchlist must contain at least one valid ticker symbol\n")
        return 1

    config = BacktestConfig(
        watchlist=tickers,
        start_date=start_dt,
        end_date=end_dt,
        initial_cash=parsed.initial_cash,
        risk_free_rate=parsed.risk_free_rate,
    )

    provider: MarketDataProvider = (
        YahooMarketDataProvider() if parsed.provider == "yahoo" else FakeMarketDataProvider()
    )

    engine = create_backtest_engine(
        config=config,
        market_data_provider=provider,
    )

    result = engine.run()
    markdown_report = generate_markdown_report(result)
    sys.stdout.write(markdown_report + "\n")

    if parsed.output:
        saved_path = export_report(
            result=result,
            output_path=parsed.output,
            format=parsed.format,
        )
        sys.stdout.write(f"\nReport successfully saved to: {saved_path}\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
