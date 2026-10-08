"""Data models representing trades, evaluated metrics, and backtest execution results."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


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


class BacktestConfig(BaseModel):
    """Configuration specification for a point-in-time backtest simulation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    watchlist: list[str]
    start_date: datetime
    end_date: datetime
    initial_cash: float = Field(default=100000.0, gt=0.0)
    risk_free_rate: float = Field(default=0.0, ge=0.0)

    @field_validator("watchlist")
    @classmethod
    def validate_watchlist(cls, v: list[str]) -> list[str]:
        """Normalize tickers to uppercase and ensure non-empty watchlist."""
        clean = [s.strip().upper() for s in v if s.strip()]
        if not clean:
            msg = "Watchlist cannot be empty"
            raise ValueError(msg)
        return clean

    @model_validator(mode="after")
    def validate_dates(self) -> "BacktestConfig":
        """Verify start_date is before or equal to end_date."""
        if self.start_date > self.end_date:
            msg = f"start_date ({self.start_date}) cannot be after end_date ({self.end_date})"
            raise ValueError(msg)
        return self


class BacktestResult(BaseModel):
    """Immutable aggregate output of a point-in-time backtest."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    config: BacktestConfig
    timestamps: list[datetime]
    agent_metrics: PerformanceMetrics
    agent_equity: list[float]
    baseline_metrics: dict[str, PerformanceMetrics]
    baseline_equities: dict[str, list[float]]
    total_cycles: int = 0
