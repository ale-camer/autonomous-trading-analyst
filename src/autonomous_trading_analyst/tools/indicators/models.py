"""Pydantic data models for technical indicators."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class MACDResult(BaseModel):
    """Moving Average Convergence Divergence values."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    macd: float
    signal: float
    histogram: float


class BollingerBandsResult(BaseModel):
    """Bollinger Bands envelope metrics."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    upper: float
    middle: float
    lower: float
    bandwidth: float = Field(ge=0.0)
    percent_b: float


class TechnicalIndicatorsSnapshot(BaseModel):
    """Snapshot of technical indicator readings at a specific point in time."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    ticker: str
    timestamp: datetime
    close_price: float = Field(gt=0.0)
    rsi_14: float | None = Field(default=None, ge=0.0, le=100.0)
    sma_20: float | None = Field(default=None, gt=0.0)
    sma_50: float | None = Field(default=None, gt=0.0)
    sma_200: float | None = Field(default=None, gt=0.0)
    ema_12: float | None = Field(default=None, gt=0.0)
    ema_26: float | None = Field(default=None, gt=0.0)
    macd: MACDResult | None = None
    bollinger: BollingerBandsResult | None = None
    atr_14: float | None = Field(default=None, ge=0.0)
