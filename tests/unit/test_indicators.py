"""Unit tests for technical indicators suite and snapshot generator."""

from datetime import UTC

import numpy as np
import pandas as pd
import pytest

from autonomous_trading_analyst.tools.indicators import (
    compute_atr,
    compute_bollinger_bands,
    compute_ema,
    compute_macd,
    compute_rsi,
    compute_sma,
    compute_technical_indicators,
)


@pytest.mark.issue_4
def test_compute_sma() -> None:
    """SMA computes correctly and handles window validations."""
    s = pd.Series([10.0, 20.0, 30.0, 40.0, 50.0])
    sma = compute_sma(s, window=3)
    assert np.isnan(sma.iloc[0])
    assert np.isnan(sma.iloc[1])
    assert sma.iloc[2] == pytest.approx(20.0)
    assert sma.iloc[4] == pytest.approx(40.0)

    with pytest.raises(ValueError, match="Cannot compute SMA on empty series"):
        compute_sma(pd.Series([], dtype=float), window=5)

    with pytest.raises(ValueError, match="Window must be positive"):
        compute_sma(s, window=0)


@pytest.mark.issue_4
def test_compute_ema() -> None:
    """EMA computes exponential decay and handles empty inputs."""
    s = pd.Series([100.0, 102.0, 104.0, 106.0])
    ema = compute_ema(s, span=2)
    assert len(ema) == 4
    assert ema.iloc[0] == 100.0
    assert ema.iloc[-1] > ema.iloc[0]

    with pytest.raises(ValueError, match="Cannot compute EMA on empty series"):
        compute_ema(pd.Series([], dtype=float), span=3)


@pytest.mark.issue_4
def test_compute_rsi_monotonic_trends() -> None:
    """RSI approaches 100 on uptrend and 0 on downtrend."""
    # Strong uptrend: 30 consecutive gains
    uptrend = pd.Series([10.0 + i * 2.0 for i in range(30)])
    rsi_up = compute_rsi(uptrend, period=14)
    assert rsi_up.iloc[-1] > 90.0
    assert 0.0 <= rsi_up.iloc[-1] <= 100.0

    # Strong downtrend: 30 consecutive drops
    downtrend = pd.Series([100.0 - i * 2.0 for i in range(30)])
    rsi_down = compute_rsi(downtrend, period=14)
    assert rsi_down.iloc[-1] < 10.0
    assert 0.0 <= rsi_down.iloc[-1] <= 100.0

    # Flat line: RSI is 50.0
    flat = pd.Series([100.0] * 30)
    rsi_flat = compute_rsi(flat, period=14)
    assert rsi_flat.iloc[-1] == pytest.approx(50.0)


@pytest.mark.issue_4
def test_compute_macd() -> None:
    """MACD calculates line, signal and histogram with fast < slow validation."""
    prices = pd.Series([100.0 + (i * 0.5) for i in range(50)])
    macd_df = compute_macd(prices, fast=12, slow=26, signal=9)

    assert set(macd_df.columns) == {"macd", "signal", "histogram"}
    assert len(macd_df) == 50

    with pytest.raises(ValueError, match=r"Fast span .* must be smaller than slow span"):
        compute_macd(prices, fast=26, slow=12)


@pytest.mark.issue_4
def test_compute_bollinger_bands() -> None:
    """Bollinger Bands construct upper, middle, and lower bands properly."""
    rng = np.random.default_rng(42)
    prices = pd.Series(100.0 + rng.normal(0, 2, 50))
    bb = compute_bollinger_bands(prices, window=20, num_std=2.0)

    assert set(bb.columns) == {"upper", "middle", "lower", "bandwidth", "percent_b"}
    # For valid rows after window warmup, upper > middle > lower
    valid = bb.dropna()
    assert (valid["upper"] > valid["middle"]).all()
    assert (valid["middle"] > valid["lower"]).all()
    assert (valid["bandwidth"] > 0).all()


@pytest.mark.issue_4
def test_compute_atr() -> None:
    """ATR calculates Average True Range based on high, low, close."""
    high = pd.Series([105.0, 107.0, 106.0, 108.0] * 5)
    low = pd.Series([100.0, 101.0, 102.0, 103.0] * 5)
    close = pd.Series([104.0, 105.0, 104.0, 107.0] * 5)

    atr = compute_atr(high, low, close, period=14)
    assert len(atr) == 20
    assert (atr.dropna() > 0).all()


@pytest.mark.issue_4
def test_compute_technical_indicators_snapshot_full() -> None:
    """Snapshot computes all indicators on sufficient historical series."""
    dates = pd.date_range("2024-01-01", periods=250, freq="1D", tz=UTC)
    rng = np.random.default_rng(123)
    returns = rng.normal(0.0005, 0.015, 250)
    prices = 100.0 * np.cumprod(1 + returns)

    df = pd.DataFrame(
        {
            "open": prices * 0.99,
            "high": prices * 1.01,
            "low": prices * 0.98,
            "close": prices,
            "volume": 1000000.0,
        },
        index=dates,
    )

    snapshot = compute_technical_indicators(df, ticker="AAPL")

    assert snapshot.ticker == "AAPL"
    assert snapshot.close_price == pytest.approx(float(prices[-1]))
    assert snapshot.timestamp == dates[-1].to_pydatetime()
    assert snapshot.rsi_14 is not None
    assert 0.0 <= snapshot.rsi_14 <= 100.0
    assert snapshot.sma_20 is not None
    assert snapshot.sma_50 is not None
    assert snapshot.sma_200 is not None
    assert snapshot.ema_12 is not None
    assert snapshot.ema_26 is not None
    assert snapshot.macd is not None
    assert snapshot.bollinger is not None
    assert snapshot.atr_14 is not None


@pytest.mark.issue_4
def test_compute_technical_indicators_snapshot_short_data() -> None:
    """Snapshot gracefully sets long-window metrics to None on short series."""
    dates = pd.date_range("2025-01-01", periods=5, freq="1D", tz=UTC)
    df = pd.DataFrame(
        {
            "close": [10.0, 11.0, 12.0, 11.5, 12.5],
            "high": [10.5, 11.5, 12.5, 12.0, 13.0],
            "low": [9.5, 10.5, 11.5, 11.0, 12.0],
        },
        index=dates,
    )

    snapshot = compute_technical_indicators(df, ticker="TSLA")
    assert snapshot.ticker == "TSLA"
    assert snapshot.close_price == 12.5
    assert snapshot.sma_20 is None
    assert snapshot.sma_200 is None
    assert snapshot.bollinger is None


@pytest.mark.issue_4
def test_compute_technical_indicators_empty_df_raises() -> None:
    """Empty DataFrame raises ValueError."""
    with pytest.raises(ValueError, match="DataFrame cannot be empty"):
        compute_technical_indicators(pd.DataFrame(), ticker="XYZ")
