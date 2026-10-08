"""Pydantic request and response schemas for the FastAPI application."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CycleRequest(BaseModel):
    """Optional payload to trigger an analysis cycle with custom parameters."""

    model_config = ConfigDict(extra="forbid")

    watchlist: list[str] | None = Field(
        default=None,
        description="Optional list of ticker symbols. Defaults to configured settings watchlist.",
    )
    as_of: datetime | None = Field(
        default=None,
        description="Optional simulation evaluation timestamp (UTC). Defaults to current time.",
    )

    @field_validator("watchlist")
    @classmethod
    def normalize_watchlist(cls, val: list[str] | None) -> list[str] | None:
        """Strip whitespace and uppercase tickers if provided."""
        if val is None:
            return None
        cleaned = [t.strip().upper() for t in val if t.strip()]
        return cleaned or None


class HealthResponse(BaseModel):
    """System liveness, readiness, and connectivity health check response."""

    model_config = ConfigDict(extra="forbid")

    status: str = Field(default="ok", description="Overall service status")
    database: str = Field(default="connected", description="Database connection health")
    app_env: str = Field(default="local", description="Configured runtime environment")
    timestamp: datetime = Field(description="UTC timestamp of the health check probe")
