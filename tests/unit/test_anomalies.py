"""Unit tests for statistical market anomaly detection."""

from datetime import UTC

import numpy as np
import pandas as pd
import pytest

from autonomous_trading_analyst.tools.anomalies import (
    AnomalyDetector,
    AnomalySeverity,
    AnomalyType,
    detect_anomalies,
)


def _make_base_df(n: int = 30) -> pd.DataFrame:
    """Helper creating n bars with stable baseline dynamics."""
    dates = pd.date_range("2024-01-01", periods=n, freq="1D", tz=UTC)
    rng = np.random.default_rng(42)
    prices = 100.0 + np.cumsum(rng.normal(0, 0.2, n))
    volumes = 1000000.0 + rng.normal(0, 50000.0, n)

    return pd.DataFrame(
        {
            "open": prices,
            "high": prices + 0.5,
            "low": prices - 0.5,
            "close": prices,
            "volume": volumes,
        },
        index=dates,
    )


@pytest.mark.issue_5
def test_normal_market_no_anomalies() -> None:
    """Normal series with mild fluctuations produces no anomalies."""
    df = _make_base_df(30)
    report = detect_anomalies(df, ticker="AAPL")

    assert report.ticker == "AAPL"
    assert report.is_anomaly is False
    assert len(report.anomalies) == 0
    assert "Normal market conditions" in report.summary


@pytest.mark.issue_5
def test_volume_spike_anomaly() -> None:
    """Surging volume on the last bar triggers a VOLUME_SPIKE anomaly."""
    df = _make_base_df(30)
    # Inject a 10x volume spike on the last candle
    df.loc[df.index[-1], "volume"] = 10000000.0

    report = detect_anomalies(df, ticker="NVDA")

    assert report.is_anomaly is True
    vol_spikes = [a for a in report.anomalies if a.type == AnomalyType.VOLUME_SPIKE]
    assert len(vol_spikes) == 1
    assert vol_spikes[0].severity in (AnomalySeverity.MEDIUM, AnomalySeverity.HIGH)
    assert vol_spikes[0].score > 5.0
    assert "volume spike" in report.summary.lower()


@pytest.mark.issue_5
def test_price_jump_anomaly() -> None:
    """A sudden price jump on the last bar triggers a PRICE_JUMP anomaly."""
    df = _make_base_df(30)
    # Inject an extreme price return (+15%) on the last candle
    df.loc[df.index[-1], "close"] = df["close"].iloc[-2] * 1.15
    df.loc[df.index[-1], "high"] = df["close"].iloc[-1] + 1.0

    report = detect_anomalies(df, ticker="TSLA")

    assert report.is_anomaly is True
    jumps = [a for a in report.anomalies if a.type == AnomalyType.PRICE_JUMP]
    assert len(jumps) == 1
    assert jumps[0].score >= 2.5
    assert "extreme price move" in report.summary.lower()


@pytest.mark.issue_5
def test_volatility_expansion_anomaly() -> None:
    """A candle range far exceeding average true range triggers VOLATILITY_EXPANSION."""
    df = _make_base_df(30)
    # Normal high-low range is ~1.0; expand last bar range to 8.0
    last_close = df["close"].iloc[-1]
    df.loc[df.index[-1], "high"] = last_close + 4.0
    df.loc[df.index[-1], "low"] = last_close - 4.0

    report = detect_anomalies(df, ticker="SPY")

    assert report.is_anomaly is True
    expansions = [a for a in report.anomalies if a.type == AnomalyType.VOLATILITY_EXPANSION]
    assert len(expansions) == 1
    assert expansions[0].score >= 2.0
    assert "volatility expansion" in report.summary.lower()


@pytest.mark.issue_5
def test_insufficient_history_returns_safe_report() -> None:
    """Series with fewer bars than lookback window returns non-anomalous report."""
    df = _make_base_df(10)
    report = detect_anomalies(df, ticker="MSFT", lookback_window=20)

    assert report.is_anomaly is False
    assert "Insufficient history" in report.summary


@pytest.mark.issue_5
def test_custom_thresholds_and_validation() -> None:
    """Detector validates parameters and honors custom threshold configuration."""
    with pytest.raises(ValueError, match="Lookback window must be at least 5"):
        AnomalyDetector(lookback_window=3)

    df = _make_base_df(30)
    # Moderate volume increase (+2 standard deviations)
    df.loc[df.index[-1], "volume"] = 1100000.0

    lenient_detector = AnomalyDetector(volume_z_threshold=1.5)
    lenient_report = lenient_detector.detect(df, ticker="TEST")
    assert lenient_report.is_anomaly is True

    strict_detector = AnomalyDetector(volume_z_threshold=5.0)
    strict_report = strict_detector.detect(df, ticker="TEST")
    assert strict_report.is_anomaly is False


@pytest.mark.issue_5
def test_empty_dataframe_raises() -> None:
    """Empty DataFrame input raises ValueError."""
    with pytest.raises(ValueError, match="DataFrame cannot be empty"):
        detect_anomalies(pd.DataFrame(), ticker="XYZ")
