"""Abstract base class and data structures for market data providers."""

from abc import ABC, abstractmethod
from collections.abc import Sequence
from datetime import date, datetime

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field

EXPECTED_OHLCV_COLUMNS: Sequence[str] = ("open", "high", "low", "close", "volume")


class MarketDataError(Exception):
    """Base exception for market data operations."""


class TickerNotFoundError(MarketDataError):
    """Raised when data for a requested ticker symbol cannot be found."""


class Bar(BaseModel):
    """Single OHLCV bar representation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    timestamp: datetime
    open: float = Field(gt=0.0)
    high: float = Field(gt=0.0)
    low: float = Field(gt=0.0)
    close: float = Field(gt=0.0)
    volume: float = Field(ge=0.0)


class MarketDataProvider(ABC):
    """Abstract interface for market data retrieval."""

    @abstractmethod
    def get_bars(
        self,
        ticker: str,
        start: datetime | date,
        end: datetime | date,
        interval: str = "1d",
    ) -> pd.DataFrame:
        """Fetch historical OHLCV price bars.

        Returns a DataFrame indexed by UTC DatetimeIndex named 'timestamp'
        with standard lowercase columns: 'open', 'high', 'low', 'close', 'volume'.
        """

    @abstractmethod
    def get_latest_price(self, ticker: str) -> float:
        """Fetch the most recent available price for a given ticker."""
