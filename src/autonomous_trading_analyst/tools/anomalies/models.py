"""Data models for market anomaly detection (P-06 style)."""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class AnomalyType(StrEnum):
    """Categorization of detected market anomalies."""

    VOLUME_SPIKE = "VOLUME_SPIKE"
    PRICE_JUMP = "PRICE_JUMP"
    VOLATILITY_EXPANSION = "VOLATILITY_EXPANSION"


class AnomalySeverity(StrEnum):
    """Severity tier for detected anomalies."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class AnomalyEvent(BaseModel):
    """Specific anomalous event detected in price or volume."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    type: AnomalyType
    score: float
    threshold: float
    severity: AnomalySeverity
    description: str


class AnomalyReport(BaseModel):
    """Aggregated anomaly assessment for a given asset."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    ticker: str
    timestamp: datetime
    is_anomaly: bool
    anomalies: list[AnomalyEvent] = Field(default_factory=list)
    summary: str
