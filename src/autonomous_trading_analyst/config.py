"""Application settings and configuration management."""

import functools
from typing import Any, Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed application settings loaded from environment or .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Runtime ---
    app_env: Literal["local", "dev", "staging", "prod"] = "local"
    log_level: str = "INFO"
    trading_mode: Literal["paper"] = "paper"

    # --- LLM ---
    llm_provider: Literal["fake", "openai", "anthropic", "gemini"] = "fake"
    llm_model: str = "gpt-4o-mini"
    openai_api_key: SecretStr | None = None
    anthropic_api_key: SecretStr | None = None
    google_api_key: SecretStr | None = None

    # --- Embeddings ---
    embedding_provider: Literal["fake", "openai", "gemini"] = "fake"
    embedding_model: str = "text-embedding-3-small"
    embedding_dim: int = 1536

    # --- Database ---
    database_url: str = "postgresql+psycopg://trader:trader@localhost:5432/trading"

    # --- Agent tools ---
    research_api_url: str = "http://localhost:8000"
    research_api_timeout_s: float = 60.0
    market_data_provider: Literal["yahoo", "fake"] = "yahoo"
    watchlist: list[str] = Field(default_factory=lambda: ["AAPL", "MSFT", "NVDA", "SPY"])

    # --- Deterministic risk limits ---
    risk_max_position_pct: float = Field(default=0.10, ge=0.0, le=1.0)
    risk_max_gross_exposure_pct: float = Field(default=0.80, ge=0.0, le=1.0)
    risk_stop_loss_pct: float = Field(default=0.08, ge=0.0, le=1.0)
    risk_max_trades_per_day: int = Field(default=5, ge=1)

    # --- Paper broker ---
    paper_initial_cash: float = Field(default=100000.0, gt=0.0)
    paper_commission_bps: float = Field(default=1.0, ge=0.0)
    paper_slippage_bps: float = Field(default=5.0, ge=0.0)

    # --- Agent budgets ---
    agent_max_steps: int = Field(default=8, ge=1)
    agent_max_cost_usd_per_decision: float = Field(default=0.05, ge=0.0)
    memory_top_k: int = Field(default=5, ge=1)

    # --- GCP ---
    gcp_project_id: str | None = None
    gcp_region: str = "europe-west1"
    gcs_artifacts_bucket: str | None = None
    google_application_credentials: str | None = None

    # --- Orchestration ---
    agent_api_url: str = "http://api:8080"
    airflow_uid: int = 50000

    @field_validator("watchlist", mode="before")
    @classmethod
    def parse_watchlist(cls, value: Any) -> list[str]:
        """Parse comma-separated strings or list of strings into clean uppercase tickers."""
        if isinstance(value, str):
            tickers = [t.strip().upper() for t in value.split(",") if t.strip()]
            return tickers
        if isinstance(value, list):
            return [str(t).strip().upper() for t in value if str(t).strip()]
        msg = f"Watchlist must be a comma-separated string or list, got {type(value)}"
        raise ValueError(msg)


@functools.lru_cache
def get_settings() -> Settings:
    """Return cached application settings instance."""
    return Settings()
