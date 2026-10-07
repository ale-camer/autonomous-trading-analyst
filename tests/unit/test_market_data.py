"""Unit tests for market data providers."""

from datetime import UTC, date, datetime
from unittest.mock import MagicMock

import pandas as pd
import pytest

from autonomous_trading_analyst.tools.market_data import (
    Bar,
    FakeMarketDataProvider,
    TickerNotFoundError,
    YahooMarketDataProvider,
    get_market_data_provider,
)


@pytest.mark.issue_3
def test_fake_provider_seeded_bars() -> None:
    """FakeMarketDataProvider returns pre-seeded bars within requested date window."""
    provider = FakeMarketDataProvider()
    bars = [
        Bar(
            timestamp=datetime(2025, 1, 1, tzinfo=UTC),
            open=100.0,
            high=105.0,
            low=99.0,
            close=104.0,
            volume=1000.0,
        ),
        Bar(
            timestamp=datetime(2025, 1, 2, tzinfo=UTC),
            open=104.0,
            high=108.0,
            low=103.0,
            close=107.0,
            volume=1500.0,
        ),
        Bar(
            timestamp=datetime(2025, 1, 3, tzinfo=UTC),
            open=107.0,
            high=110.0,
            low=106.0,
            close=109.0,
            volume=2000.0,
        ),
    ]
    provider.seed_bars("AAPL", bars)

    # Fetch subset
    df = provider.get_bars(
        "AAPL",
        start=date(2025, 1, 1),
        end=date(2025, 1, 2),
    )
    assert len(df) == 2
    assert list(df.columns) == ["open", "high", "low", "close", "volume"]
    assert df.index.name == "timestamp"
    assert df["close"].iloc[-1] == 107.0


@pytest.mark.issue_3
def test_fake_provider_synthetic_bars() -> None:
    """FakeMarketDataProvider deterministically creates synthetic bars for unseeded tickers."""
    provider = FakeMarketDataProvider(default_price=150.0)
    df = provider.get_bars("MSFT", start=date(2025, 1, 1), end=date(2025, 1, 10))
    assert len(df) == 10
    assert (df["open"] > 0).all()
    assert (df["high"] >= df["low"]).all()
    assert (df["volume"] > 0).all()


@pytest.mark.issue_3
def test_fake_provider_latest_price() -> None:
    """FakeMarketDataProvider resolves seeded prices, seeded bars, and default prices."""
    provider = FakeMarketDataProvider(default_price=50.0)

    # Explicit seeded price
    provider.seed_latest_price("TSLA", 250.0)
    assert provider.get_latest_price("TSLA") == 250.0

    # Fallback to last close from seeded bars
    bars = [
        Bar(
            timestamp=datetime(2025, 1, 1, tzinfo=UTC),
            open=10.0,
            high=12.0,
            low=9.0,
            close=11.5,
            volume=500.0,
        )
    ]
    provider.seed_bars("NVDA", bars)
    assert provider.get_latest_price("NVDA") == 11.5

    # Fallback to default
    assert provider.get_latest_price("SPY") == 50.0

    # Invalid ticker error
    with pytest.raises(TickerNotFoundError):
        provider.get_latest_price("INVALID_TICKER")


@pytest.mark.issue_3
def test_yahoo_provider_get_bars_mocked(monkeypatch: pytest.MonkeyPatch) -> None:
    """YahooMarketDataProvider normalizes yfinance columns to lowercase and enforces UTC index."""
    mock_df = pd.DataFrame(
        {
            "Open": [150.0, 152.0],
            "High": [155.0, 156.0],
            "Low": [149.0, 151.0],
            "Close": [153.0, 155.0],
            "Volume": [1000000, 1200000],
            "Dividends": [0.0, 0.0],
        },
        index=pd.date_range("2025-01-01", periods=2, freq="D"),
    )

    mock_ticker_inst = MagicMock()
    mock_ticker_inst.history.return_value = mock_df

    monkeypatch.setattr("yfinance.Ticker", lambda _ticker: mock_ticker_inst)

    provider = YahooMarketDataProvider()
    df = provider.get_bars("AAPL", start=date(2025, 1, 1), end=date(2025, 1, 2))

    assert list(df.columns) == ["open", "high", "low", "close", "volume"]
    assert "dividends" not in df.columns
    assert df.index.tz is not None
    assert df.index.name == "timestamp"
    assert df["close"].iloc[0] == 153.0


@pytest.mark.issue_3
def test_yahoo_provider_missing_ticker_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """YahooMarketDataProvider raises TickerNotFoundError on empty history."""
    mock_ticker_inst = MagicMock()
    mock_ticker_inst.history.return_value = pd.DataFrame()

    monkeypatch.setattr("yfinance.Ticker", lambda _ticker: mock_ticker_inst)

    provider = YahooMarketDataProvider()
    with pytest.raises(TickerNotFoundError):
        provider.get_bars("NONEXISTENT", start=date(2025, 1, 1), end=date(2025, 1, 2))


@pytest.mark.issue_3
def test_yahoo_provider_latest_price_mocked(monkeypatch: pytest.MonkeyPatch) -> None:
    """YahooMarketDataProvider reads latest quote from fast_info."""
    mock_ticker_inst = MagicMock()
    mock_ticker_inst.fast_info = {"lastPrice": 234.56}

    monkeypatch.setattr("yfinance.Ticker", lambda _ticker: mock_ticker_inst)

    provider = YahooMarketDataProvider()
    assert provider.get_latest_price("AAPL") == 234.56


@pytest.mark.issue_3
def test_factory_resolution() -> None:
    """Factory returns configured provider instance or raises on unknown provider."""
    fake_p = get_market_data_provider("fake")
    assert isinstance(fake_p, FakeMarketDataProvider)

    yahoo_p = get_market_data_provider("yahoo")
    assert isinstance(yahoo_p, YahooMarketDataProvider)

    with pytest.raises(ValueError, match="Unknown market data provider"):
        get_market_data_provider("bloomberg")
