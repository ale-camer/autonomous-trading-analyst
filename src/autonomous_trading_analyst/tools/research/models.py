"""Data models and exceptions for P-09 research client."""

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Sentiment(StrEnum):
    """Categorical sentiment orientation."""

    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"


class ResearchError(Exception):
    """Base exception for financial research operations."""


class ResearchTimeoutError(ResearchError):
    """Raised when the research API times out."""


class ResearchConnectionError(ResearchError):
    """Raised when failing to connect to the research API."""


class ResearchRequest(BaseModel):
    """Payload sent to POST /research."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    ticker: str
    query: str | None = None
    focus: str | None = None

    @field_validator("ticker")
    @classmethod
    def clean_ticker(cls, v: str) -> str:
        clean = v.strip().upper()
        if not clean:
            msg = "Ticker cannot be empty"
            raise ValueError(msg)
        return clean


class ResearchReport(BaseModel):
    """Output received from the financial research agent."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    ticker: str
    summary: str
    sentiment: Sentiment
    score: float = Field(ge=-1.0, le=1.0)
    key_findings: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("ticker")
    @classmethod
    def clean_ticker(cls, v: str) -> str:
        clean = v.strip().upper()
        if not clean:
            msg = "Ticker cannot be empty"
            raise ValueError(msg)
        return clean
