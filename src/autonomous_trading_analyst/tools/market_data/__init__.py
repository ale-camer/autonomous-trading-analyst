"""Market data module exposing providers, models, and factory."""

from autonomous_trading_analyst.config import get_settings
from autonomous_trading_analyst.tools.market_data.base import (
    EXPECTED_OHLCV_COLUMNS,
    Bar,
    MarketDataError,
    MarketDataProvider,
    TickerNotFoundError,
)
from autonomous_trading_analyst.tools.market_data.fake import FakeMarketDataProvider
from autonomous_trading_analyst.tools.market_data.yahoo import YahooMarketDataProvider


def get_market_data_provider(provider_type: str | None = None) -> MarketDataProvider:
    """Factory function to instantiate the configured MarketDataProvider."""
    selected = provider_type or get_settings().market_data_provider
    normalized = selected.lower().strip()

    if normalized == "fake":
        return FakeMarketDataProvider()
    if normalized == "yahoo":
        return YahooMarketDataProvider()

    msg = f"Unknown market data provider '{selected}'. Expected 'yahoo' or 'fake'."
    raise ValueError(msg)


__all__ = [
    "EXPECTED_OHLCV_COLUMNS",
    "Bar",
    "FakeMarketDataProvider",
    "MarketDataError",
    "MarketDataProvider",
    "TickerNotFoundError",
    "YahooMarketDataProvider",
    "get_market_data_provider",
]
