"""Unit tests for backtest comparative report generation, export, and CLI."""

import json
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from autonomous_trading_analyst.evaluation import (
    BacktestConfig,
    BacktestResult,
    BuyAndHoldStrategy,
    SMACrossoverStrategy,
    cli_main,
    create_backtest_engine,
    export_report,
    generate_json_report,
    generate_markdown_report,
)
from autonomous_trading_analyst.evaluation.cli import parse_args
from autonomous_trading_analyst.evaluation.report import _fmt_curr, _fmt_float, _fmt_pct
from autonomous_trading_analyst.tools.market_data.fake import FakeMarketDataProvider
from autonomous_trading_analyst.tools.market_data.yahoo import YahooMarketDataProvider


@pytest.fixture
def sample_backtest_result() -> BacktestResult:
    """Create a deterministic BacktestResult fixture using FakeMarketDataProvider."""
    t0 = datetime(2026, 1, 1, tzinfo=UTC)
    t1 = datetime(2026, 1, 3, tzinfo=UTC)

    config = BacktestConfig(
        watchlist=["AAPL"],
        start_date=t0,
        end_date=t1,
        initial_cash=50000.0,
        risk_free_rate=0.02,
    )

    fake_market = FakeMarketDataProvider()
    fake_market.seed_latest_price("AAPL", 150.0)

    engine = create_backtest_engine(
        config=config,
        market_data_provider=fake_market,
        baselines=[BuyAndHoldStrategy(), SMACrossoverStrategy()],
    )
    return engine.run()


@pytest.mark.issue_21
def test_format_helpers() -> None:
    """Helper functions format percentages, currencies, and floating numbers correctly."""
    assert _fmt_pct(0.052) == "+5.20%"
    assert _fmt_pct(-0.1234) == "-12.34%"
    assert _fmt_pct(0.0) == "+0.00%"

    assert _fmt_curr(100000.5) == "$100,000.50"
    assert _fmt_curr(-1250.75) == "-$1,250.75"
    assert _fmt_curr(0.0) == "$0.00"

    assert _fmt_float(1.23456, 4) == "1.2346"
    assert _fmt_float(1.23456, 2) == "1.23"


@pytest.mark.issue_21
def test_generate_markdown_report_structure(sample_backtest_result: BacktestResult) -> None:
    """Markdown report contains executive summary and comparative metrics table."""
    report = generate_markdown_report(sample_backtest_result)

    # Executive Summary checks
    assert "# Backtest Comparative Report" in report
    assert "## Executive Summary" in report
    assert "- **Watchlist**: AAPL" in report
    assert "- **Simulation Period**: 2026-01-01 to 2026-01-03" in report
    assert "- **Initial Capital**: $50,000.00" in report
    assert "- **Risk-Free Rate**: +2.00%" in report

    # Table structure checks
    assert "## Performance Comparison" in report
    assert "| Metric | Agent (ReAct) | Buy And Hold | Sma Crossover |" in report
    assert "| --- | --- | --- | --- |" in report

    # Required metric rows
    expected_metrics = [
        "Start Equity",
        "End Equity",
        "Total Return",
        "Annualized Return (CAGR)",
        "Annualized Volatility",
        "Sharpe Ratio",
        "Sortino Ratio",
        "Max Drawdown",
        "Max Drawdown Duration",
        "Calmar Ratio",
        "Total Closed Trades",
        "Winning Trades",
        "Losing Trades",
        "Win Rate",
        "Profit Factor",
        "Average Trade PnL",
        "Average Win PnL",
        "Average Loss PnL",
        "Total Decisions",
        "Total Tokens",
        "Tokens / Decision",
        "Total Cost (USD)",
        "Cost / Decision (USD)",
    ]
    for metric in expected_metrics:
        assert f"| {metric} |" in report

    # Integrity analysis notes
    assert "## Analysis Notes" in report
    assert "Point-in-Time Integrity" in report
    assert "Identical Guardrails" in report
    assert "LLM Resource Attribution" in report


@pytest.mark.issue_21
def test_generate_json_report_serialization(sample_backtest_result: BacktestResult) -> None:
    """JSON report generates valid schema with configurations and metrics."""
    json_str = generate_json_report(sample_backtest_result, indent=2)
    data = json.loads(json_str)

    assert "config" in data
    assert data["config"]["watchlist"] == ["AAPL"]
    assert data["config"]["initial_cash"] == 50000.0
    assert "agent_metrics" in data
    assert "baseline_metrics" in data
    assert "buy_and_hold" in data["baseline_metrics"]
    assert "sma_crossover" in data["baseline_metrics"]
    assert "total_cycles" in data
    assert "timestamps" in data
    assert "agent_equity" in data
    assert "baseline_equities" in data


@pytest.mark.issue_21
def test_export_report_markdown_and_json(
    sample_backtest_result: BacktestResult,
    tmp_path: Path,
) -> None:
    """export_report writes report files to disk creating parent directories as needed."""
    # Export Markdown
    md_file = tmp_path / "reports" / "summary.md"
    written_md_path = export_report(sample_backtest_result, md_file, format="markdown")
    assert written_md_path == md_file
    assert md_file.exists()
    content_md = md_file.read_text(encoding="utf-8")
    assert "# Backtest Comparative Report" in content_md

    # Export JSON
    json_file = tmp_path / "reports" / "nested" / "summary.json"
    written_json_path = export_report(sample_backtest_result, json_file, format="json")
    assert written_json_path == json_file
    assert json_file.exists()
    content_json = json_file.read_text(encoding="utf-8")
    parsed_json = json.loads(content_json)
    assert parsed_json["config"]["watchlist"] == ["AAPL"]


@pytest.mark.issue_21
def test_cli_parse_args_defaults() -> None:
    """CLI argument parser sets intended defaults."""
    args = parse_args([])
    assert args.watchlist == "AAPL"
    assert args.initial_cash == 100000.0
    assert args.risk_free_rate == 0.0
    assert args.output is None
    assert args.format == "markdown"
    assert args.provider == "fake"


@pytest.mark.issue_21
def test_cli_parse_args_custom() -> None:
    """CLI argument parser accepts custom flag overrides."""
    custom = [
        "--watchlist",
        "MSFT,NVDA",
        "--start-date",
        "2026-01-01",
        "--end-date",
        "2026-01-15",
        "--initial-cash",
        "25000",
        "--risk-free-rate",
        "0.05",
        "--output",
        "out/report.json",
        "--format",
        "json",
        "--provider",
        "yahoo",
    ]
    args = parse_args(custom)
    assert args.watchlist == "MSFT,NVDA"
    assert args.start_date == "2026-01-01"
    assert args.end_date == "2026-01-15"
    assert args.initial_cash == 25000.0
    assert args.risk_free_rate == 0.05
    assert args.output == "out/report.json"
    assert args.format == "json"
    assert args.provider == "yahoo"


@pytest.mark.issue_21
def test_cli_main_success_stdout_and_file(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """CLI execution runs backtest, prints Markdown to stdout, and exports to file."""
    output_path = tmp_path / "cli_report.md"
    exit_code = cli_main(
        [
            "--watchlist",
            "AAPL",
            "--start-date",
            "2026-01-01",
            "--end-date",
            "2026-01-02",
            "--initial-cash",
            "10000",
            "--provider",
            "fake",
            "--output",
            str(output_path),
            "--format",
            "markdown",
        ]
    )
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "# Backtest Comparative Report" in captured.out
    assert f"Report successfully saved to: {output_path}" in captured.out
    assert output_path.exists()
    assert "# Backtest Comparative Report" in output_path.read_text(encoding="utf-8")


@pytest.mark.issue_21
def test_cli_main_invalid_date_format(capsys: pytest.CaptureFixture[str]) -> None:
    """CLI exits with error code 1 when given invalid date strings."""
    exit_code = cli_main(["--start-date", "invalid-date"])
    assert exit_code == 1
    captured = capsys.readouterr()
    assert "Error parsing dates" in captured.err


@pytest.mark.issue_21
def test_cli_main_start_date_after_end_date(capsys: pytest.CaptureFixture[str]) -> None:
    """CLI exits with error code 1 when start date is chronologically after end date."""
    exit_code = cli_main(
        [
            "--start-date",
            "2026-01-10",
            "--end-date",
            "2026-01-01",
        ]
    )
    assert exit_code == 1
    captured = capsys.readouterr()
    assert "Error: start-date" in captured.err
    assert "cannot be after end-date" in captured.err


@pytest.mark.issue_21
def test_cli_main_empty_watchlist(capsys: pytest.CaptureFixture[str]) -> None:
    """CLI exits with error code 1 when watchlist has no valid tickers."""
    exit_code = cli_main(["--watchlist", " , "])
    assert exit_code == 1
    captured = capsys.readouterr()
    assert "Error: watchlist must contain at least one valid ticker symbol" in captured.err


@pytest.mark.issue_21
def test_cli_main_yahoo_provider_selection(sample_backtest_result: BacktestResult) -> None:
    """CLI correctly instantiates YahooMarketDataProvider when requested."""
    with (
        patch("autonomous_trading_analyst.evaluation.cli.create_backtest_engine") as mock_create,
        patch.object(YahooMarketDataProvider, "__init__", return_value=None),
    ):
        mock_engine = MagicMock()
        mock_engine.run.return_value = sample_backtest_result
        mock_create.return_value = mock_engine

        exit_code = cli_main(
            [
                "--watchlist",
                "AAPL",
                "--start-date",
                "2026-01-01",
                "--end-date",
                "2026-01-02",
                "--provider",
                "yahoo",
            ]
        )
        assert exit_code == 0
        mock_create.assert_called_once()
        _, kwargs = mock_create.call_args
        assert isinstance(kwargs["market_data_provider"], YahooMarketDataProvider)
