"""Reporting engine generating comparative Markdown and JSON backtest evaluations."""

import json
from collections.abc import Callable
from pathlib import Path

from autonomous_trading_analyst.evaluation.models import BacktestResult, PerformanceMetrics


def _fmt_pct(val: float) -> str:
    """Format floating point fraction as percentage string."""
    return f"{val * 100:+.2f}%"


def _fmt_curr(val: float) -> str:
    """Format dollar amounts with currency symbols and comma separators."""
    if val < 0.0:
        return f"-${abs(val):,.2f}"
    return f"${val:,.2f}"


def _fmt_float(val: float, decimals: int = 2) -> str:
    """Format floating point numbers with fixed decimals."""
    return f"{val:.{decimals}f}"


def generate_markdown_report(result: BacktestResult) -> str:
    """Generate comprehensive comparative Markdown report evaluating agent vs baselines."""
    cfg = result.config
    start_str = cfg.start_date.strftime("%Y-%m-%d")
    end_str = cfg.end_date.strftime("%Y-%m-%d")
    tickers_str = ", ".join(cfg.watchlist)

    baseline_names = list(result.baseline_metrics.keys())
    # Format header row
    cols = ["Metric", "Agent (ReAct)"] + [b.replace("_", " ").title() for b in baseline_names]
    header_line = "| " + " | ".join(cols) + " |"
    separator_line = "| " + " | ".join(["---"] * len(cols)) + " |"

    def make_row(metric_label: str, agent_val: str, baseline_vals: list[str]) -> str:
        vals = [metric_label, agent_val, *baseline_vals]
        return "| " + " | ".join(vals) + " |"

    def get_baseline_vals(extractor: Callable[[PerformanceMetrics], str]) -> list[str]:
        return [extractor(result.baseline_metrics[b]) for b in baseline_names]

    rows: list[str] = [
        header_line,
        separator_line,
        # Financial / Equity Curve Metrics
        make_row(
            "Start Equity",
            _fmt_curr(result.agent_metrics.start_equity),
            get_baseline_vals(lambda m: _fmt_curr(m.start_equity)),
        ),
        make_row(
            "End Equity",
            _fmt_curr(result.agent_metrics.end_equity),
            get_baseline_vals(lambda m: _fmt_curr(m.end_equity)),
        ),
        make_row(
            "Total Return",
            _fmt_pct(result.agent_metrics.total_return),
            get_baseline_vals(lambda m: _fmt_pct(m.total_return)),
        ),
        make_row(
            "Annualized Return (CAGR)",
            _fmt_pct(result.agent_metrics.annualized_return),
            get_baseline_vals(lambda m: _fmt_pct(m.annualized_return)),
        ),
        make_row(
            "Annualized Volatility",
            _fmt_pct(result.agent_metrics.annualized_volatility),
            get_baseline_vals(lambda m: _fmt_pct(m.annualized_volatility)),
        ),
        make_row(
            "Sharpe Ratio",
            _fmt_float(result.agent_metrics.sharpe_ratio, 4),
            get_baseline_vals(lambda m: _fmt_float(m.sharpe_ratio, 4)),
        ),
        make_row(
            "Sortino Ratio",
            _fmt_float(result.agent_metrics.sortino_ratio, 4),
            get_baseline_vals(lambda m: _fmt_float(m.sortino_ratio, 4)),
        ),
        make_row(
            "Max Drawdown",
            _fmt_pct(-abs(result.agent_metrics.max_drawdown)),
            get_baseline_vals(lambda m: _fmt_pct(-abs(m.max_drawdown))),
        ),
        make_row(
            "Max Drawdown Duration",
            f"{result.agent_metrics.max_drawdown_duration_days} days",
            get_baseline_vals(lambda m: f"{m.max_drawdown_duration_days} days"),
        ),
        make_row(
            "Calmar Ratio",
            _fmt_float(result.agent_metrics.calmar_ratio, 4),
            get_baseline_vals(lambda m: _fmt_float(m.calmar_ratio, 4)),
        ),
        # Trade Statistics
        make_row(
            "Total Closed Trades",
            str(result.agent_metrics.total_trades),
            get_baseline_vals(lambda m: str(m.total_trades)),
        ),
        make_row(
            "Winning Trades",
            str(result.agent_metrics.winning_trades),
            get_baseline_vals(lambda m: str(m.winning_trades)),
        ),
        make_row(
            "Losing Trades",
            str(result.agent_metrics.losing_trades),
            get_baseline_vals(lambda m: str(m.losing_trades)),
        ),
        make_row(
            "Win Rate",
            f"{result.agent_metrics.win_rate * 100:.2f}%",
            get_baseline_vals(lambda m: f"{m.win_rate * 100:.2f}%"),
        ),
        make_row(
            "Profit Factor",
            (
                _fmt_float(result.agent_metrics.profit_factor, 4)
                if result.agent_metrics.profit_factor is not None
                else "N/A"
            ),
            get_baseline_vals(
                lambda m: _fmt_float(m.profit_factor, 4) if m.profit_factor is not None else "N/A"
            ),
        ),
        make_row(
            "Average Trade PnL",
            _fmt_curr(result.agent_metrics.average_trade_pnl),
            get_baseline_vals(lambda m: _fmt_curr(m.average_trade_pnl)),
        ),
        make_row(
            "Average Win PnL",
            _fmt_curr(result.agent_metrics.average_win_pnl),
            get_baseline_vals(lambda m: _fmt_curr(m.average_win_pnl)),
        ),
        make_row(
            "Average Loss PnL",
            _fmt_curr(result.agent_metrics.average_loss_pnl),
            get_baseline_vals(lambda m: _fmt_curr(m.average_loss_pnl)),
        ),
        # LLM Efficiency
        make_row(
            "Total Decisions",
            str(result.agent_metrics.total_decisions),
            get_baseline_vals(lambda m: str(m.total_decisions)),
        ),
        make_row(
            "Total Tokens",
            f"{result.agent_metrics.total_tokens:,}",
            get_baseline_vals(lambda m: f"{m.total_tokens:,}"),
        ),
        make_row(
            "Tokens / Decision",
            f"{result.agent_metrics.tokens_per_decision:,.1f}",
            get_baseline_vals(lambda m: f"{m.tokens_per_decision:,.1f}"),
        ),
        make_row(
            "Total Cost (USD)",
            f"${result.agent_metrics.total_cost_usd:.6f}",
            get_baseline_vals(lambda m: f"${m.total_cost_usd:.6f}"),
        ),
        make_row(
            "Cost / Decision (USD)",
            f"${result.agent_metrics.cost_per_decision:.6f}",
            get_baseline_vals(lambda m: f"${m.cost_per_decision:.6f}"),
        ),
    ]

    table_md = "\n".join(rows)

    return f"""# Backtest Comparative Report

## Executive Summary
- **Watchlist**: {tickers_str}
- **Simulation Period**: {start_str} to {end_str} ({result.total_cycles} evaluation cycles)
- **Initial Capital**: {_fmt_curr(cfg.initial_cash)}
- **Risk-Free Rate**: {_fmt_pct(cfg.risk_free_rate)}

## Performance Comparison
{table_md}

## Analysis Notes
- **Point-in-Time Integrity**: All indicators and decision inputs strictly clamped to each date.
- **Identical Guardrails**: Agent and baselines evaluated under shared risk limits and costs.
- **LLM Resource Attribution**: Agent tracked token consumption and API expenditures.
"""


def generate_json_report(result: BacktestResult, indent: int = 2) -> str:
    """Generate structured, formatted JSON representation of backtest results."""
    data = result.model_dump(mode="json")
    return json.dumps(data, indent=indent, default=str)


def export_report(
    result: BacktestResult,
    output_path: str | Path,
    format: str = "markdown",
) -> Path:
    """Export backtest evaluation report to disk in Markdown or JSON format."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    norm_format = format.strip().lower()
    if norm_format in ("json", "js"):
        content = generate_json_report(result)
    else:
        content = generate_markdown_report(result)

    path.write_text(content, encoding="utf-8")
    return path
