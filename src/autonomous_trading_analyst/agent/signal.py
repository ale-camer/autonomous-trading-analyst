"""Trading signal contract produced by the ReAct agent."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SignalDecision(StrEnum):
    """Possible trading decisions produced by the agent."""

    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


class TradingSignal(BaseModel):
    """Structured trading decision submitted by the ReAct agent."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    ticker: str = Field(description="Ticker symbol analyzed.")
    decision: SignalDecision = Field(description="Trading decision: BUY, SELL, or HOLD.")
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Confidence score between 0.0 and 1.0.",
    )
    rationale: str = Field(description="Detailed rationale and justification for the decision.")

    @field_validator("ticker")
    @classmethod
    def validate_ticker(cls, v: str) -> str:
        clean = v.strip().upper()
        if not clean:
            msg = "Ticker symbol cannot be empty"
            raise ValueError(msg)
        return clean
