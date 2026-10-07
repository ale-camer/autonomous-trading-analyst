"""Fake market data provider for deterministic, offline testing."""

from collections.abc import Sequence
from datetime import UTC, date, datetime, time

import numpy as np
import pandas as pd

from autonomous_trading_analyst.tools.market_data.base import (
    Bar,
    MarketDataProvider,
    TickerNotFoundError,
)


def _to_utc_datetime(d: datetime | date) -> datetime:
    """Normalize date or datetime to UTC datetime."""
    if isinstance(d, datetime):
        if d.tzinfo is None:
            return d.replace(tzinfo=UTC)
        return d.astimezone(UTC)
    return datetime.combine(d, time.min, tzinfo=UTC)


class FakeMarketDataProvider(MarketDataProvider):
    """Deterministic, offline market data provider."""

    def __init__(self, default_price: float = 100.0) -> None:
        self._default_price = default_price
        self._seeded_bars: dict[str, pd.DataFrame] = {}
        self._seeded_prices: dict[str, float] = {}

    def seed_bars(self, ticker: str, bars_or_df: Sequence[Bar] | pd.DataFrame) -> None:
        """Seed explicit OHLCV bars for a given ticker."""
        symbol = ticker.strip().upper()
        if isinstance(bars_or_df, pd.DataFrame):
            df = bars_or_df.copy()
            if not isinstance(df.index, pd.DatetimeIndex):
                if "timestamp" in df.columns:
                    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
                    df = df.set_index("timestamp")
                else:
                    msg = "DataFrame must be indexed by DatetimeIndex or contain 'timestamp' column"
                    raise ValueError(msg)
            if df.index.tz is None:
                df.index = df.index.tz_localize(UTC)
            else:
                df.index = df.index.tz_convert(UTC)
            df.index.name = "timestamp"
            self._seeded_bars[symbol] = df
        else:
            records = [
                {
                    "timestamp": _to_utc_datetime(b.timestamp),
                    "open": b.open,
                    "high": b.high,
                    "low": b.low,
                    "close": b.close,
                    "volume": b.volume,
                }
                for b in bars_or_df
            ]
            if records:
                df = pd.DataFrame(records).set_index("timestamp")
                df.index.name = "timestamp"
                self._seeded_bars[symbol] = df
            else:
                empty_idx = pd.DatetimeIndex([], tz=UTC, name="timestamp")
                self._seeded_bars[symbol] = pd.DataFrame(
                    columns=["open", "high", "low", "close", "volume"],
                    index=empty_idx,
                )

    def seed_latest_price(self, ticker: str, price: float) -> None:
        """Seed an explicit latest price quote for a ticker."""
        if price <= 0:
            msg = "Price must be strictly positive"
            raise ValueError(msg)
        self._seeded_prices[ticker.strip().upper()] = price

    def get_bars(
        self,
        ticker: str,
        start: datetime | date,
        end: datetime | date,
        interval: str = "1d",
    ) -> pd.DataFrame:
        """Retrieve bars for ticker. Returns seeded bars or synthetic generated bars."""
        symbol = ticker.strip().upper()
        start_dt = _to_utc_datetime(start)
        end_dt = _to_utc_datetime(end)

        if start_dt > end_dt:
            msg = f"start date {start_dt} cannot be after end date {end_dt}"
            raise ValueError(msg)

        if symbol in self._seeded_bars:
            df = self._seeded_bars[symbol]
            mask = (df.index >= start_dt) & (df.index <= end_dt)
            return df.loc[mask].copy()

        # Generate deterministic synthetic bars
        date_range = pd.date_range(start=start_dt, end=end_dt, freq="1D", tz=UTC)
        if len(date_range) == 0:
            return pd.DataFrame(
                columns=["open", "high", "low", "close", "volume"],
                index=pd.DatetimeIndex([], tz=UTC, name="timestamp"),
            )

        base_price = self._seeded_prices.get(symbol, self._default_price)
        n = len(date_range)
        # Deterministic variation based on ticker name
        seed = sum(ord(c) for c in symbol)
        rng = np.random.default_rng(seed)
        returns = rng.normal(0.0005, 0.015, n)
        prices = base_price * np.cumprod(1 + returns)

        opens = prices * (1 - 0.002)
        closes = prices
        highs = np.maximum(opens, closes) * 1.005
        lows = np.minimum(opens, closes) * 0.995
        volumes = rng.uniform(100000, 5000000, n)

        data = {
            "open": opens.astype(float),
            "high": highs.astype(float),
            "low": lows.astype(float),
            "close": closes.astype(float),
            "volume": volumes.astype(float),
        }
        df = pd.DataFrame(data, index=date_range)
        df.index.name = "timestamp"
        return df

    def get_latest_price(self, ticker: str) -> float:
        """Fetch latest price for ticker."""
        symbol = ticker.strip().upper()
        if symbol in self._seeded_prices:
            return self._seeded_prices[symbol]
        if symbol in self._seeded_bars and not self._seeded_bars[symbol].empty:
            return float(self._seeded_bars[symbol]["close"].iloc[-1])
        if symbol.startswith("INVALID"):
            raise TickerNotFoundError(f"Ticker {symbol} not found")
        return self._default_price
