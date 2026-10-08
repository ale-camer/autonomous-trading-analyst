"""Data models representing individual trade records and evaluated performance metrics."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TradeRecord(BaseModel):
    """Immutable record of a closed round-trip trade."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    ticker: str
    entry_time: datetime
    exit_time: datetime
    entry_price: float
    exit_price: float
    shares: float
    pnl: float
    return_pct: float
    commission: float = Field(default=0.0, ge=0.0)


class PerformanceMetrics(BaseModel):
    """Comprehensive financial and system performance metrics."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    # Financial / Equity Curve Metrics
    start_equity: float
    end_equity: float
    total_return: float
    annualized_return: float
    annualized_volatility: float
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown: float
    max_drawdown_duration_days: int
    calmar_ratio: float

    # Trade Statistics
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    profit_factor: float | None = None
    average_trade_pnl: float = 0.0
    average_win_pnl: float = 0.0
    average_loss_pnl: float = 0.0

    # Agent Resource / LLM Metrics
    total_decisions: int = 0
    total_cost_usd: float = 0.0
    cost_per_decision: float = 0.0
    total_tokens: int = 0
    tokens_per_decision: float = 0.0
