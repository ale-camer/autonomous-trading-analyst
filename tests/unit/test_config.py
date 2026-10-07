"""Unit tests for application configuration and settings."""

import pytest
from pydantic import ValidationError

from autonomous_trading_analyst.config import Settings, get_settings


@pytest.mark.issue_2
def test_default_settings() -> None:
    """Settings initializes with correct default values and paper trading mode."""
    settings = Settings()
    assert settings.app_env == "local"
    assert settings.log_level == "INFO"
    assert settings.trading_mode == "paper"
    assert settings.llm_provider == "fake"
    assert settings.watchlist == ["AAPL", "MSFT", "NVDA", "SPY"]
    assert settings.risk_max_position_pct == 0.10
    assert settings.risk_max_gross_exposure_pct == 0.80
    assert settings.risk_stop_loss_pct == 0.08
    assert settings.paper_initial_cash == 100000.0
    assert settings.paper_commission_bps == 1.0
    assert settings.paper_slippage_bps == 5.0
    assert settings.agent_max_steps == 8
    assert settings.agent_max_cost_usd_per_decision == 0.05


@pytest.mark.issue_2
def test_watchlist_parsing_from_comma_separated_string() -> None:
    """Watchlist correctly normalizes comma-separated tickers with whitespace."""
    settings = Settings(watchlist=" aapl , msft, tsla , ")  # type: ignore[arg-type]
    assert settings.watchlist == ["AAPL", "MSFT", "TSLA"]


@pytest.mark.issue_2
def test_watchlist_parsing_from_list() -> None:
    """Watchlist preserves and normalizes lists of tickers."""
    settings = Settings(watchlist=["aapl", " GOOG "])
    assert settings.watchlist == ["AAPL", "GOOG"]


@pytest.mark.issue_2
def test_trading_mode_only_accepts_paper() -> None:
    """Config strictly forbids any trading mode other than 'paper'."""
    with pytest.raises(ValidationError):
        Settings(trading_mode="live")  # type: ignore[arg-type]

    with pytest.raises(ValidationError):
        Settings(trading_mode="real")  # type: ignore[arg-type]


@pytest.mark.issue_2
def test_secret_string_masking() -> None:
    """API keys wrapped in SecretStr do not leak in string representation."""
    settings = Settings(openai_api_key="super-secret-key-123")  # type: ignore[arg-type]
    assert settings.openai_api_key is not None
    assert str(settings.openai_api_key) == "**********"
    assert settings.openai_api_key.get_secret_value() == "super-secret-key-123"


@pytest.mark.issue_2
def test_get_settings_caching() -> None:
    """get_settings returns a cached instance across calls."""
    s1 = get_settings()
    s2 = get_settings()
    assert s1 is s2
