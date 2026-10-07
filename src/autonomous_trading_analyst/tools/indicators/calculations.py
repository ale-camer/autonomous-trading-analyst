"""Core mathematical routines for technical indicator calculations."""

import numpy as np
import pandas as pd


def compute_sma(series: pd.Series, window: int) -> pd.Series:
    """Compute Simple Moving Average (SMA)."""
    if len(series) == 0:
        msg = "Cannot compute SMA on empty series"
        raise ValueError(msg)
    if window <= 0:
        msg = f"Window must be positive, got {window}"
        raise ValueError(msg)
    return series.rolling(window=window).mean()


def compute_ema(series: pd.Series, span: int) -> pd.Series:
    """Compute Exponential Moving Average (EMA)."""
    if len(series) == 0:
        msg = "Cannot compute EMA on empty series"
        raise ValueError(msg)
    if span <= 0:
        msg = f"Span must be positive, got {span}"
        raise ValueError(msg)
    return series.ewm(span=span, adjust=False).mean()


def compute_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Compute Relative Strength Index (RSI) using Wilder's smoothing."""
    if len(series) == 0:
        msg = "Cannot compute RSI on empty series"
        raise ValueError(msg)
    if period <= 0:
        msg = f"Period must be positive, got {period}"
        raise ValueError(msg)

    delta = series.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)

    # Wilder's smoothing: alpha = 1 / period
    avg_gain = gain.ewm(alpha=1.0 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, adjust=False).mean()

    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    rsi = 100.0 - (100.0 / (1.0 + rs))

    # Where loss is 0 and gain > 0, RSI is 100. Where both are 0, RSI is 50.
    rsi = rsi.where(avg_loss != 0.0, 100.0)
    rsi = rsi.where((avg_gain != 0.0) | (avg_loss != 0.0), 50.0)

    # First `period` rows do not have sufficient historical warmup
    if len(series) < period:
        return pd.Series(np.nan, index=series.index)

    return rsi


def compute_macd(
    series: pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> pd.DataFrame:
    """Compute Moving Average Convergence Divergence (MACD)."""
    if len(series) == 0:
        msg = "Cannot compute MACD on empty series"
        raise ValueError(msg)
    if fast >= slow:
        msg = f"Fast span ({fast}) must be smaller than slow span ({slow})"
        raise ValueError(msg)

    fast_ema = compute_ema(series, span=fast)
    slow_ema = compute_ema(series, span=slow)
    macd_line = fast_ema - slow_ema
    signal_line = compute_ema(macd_line, span=signal)
    hist = macd_line - signal_line

    return pd.DataFrame(
        {"macd": macd_line, "signal": signal_line, "histogram": hist},
        index=series.index,
    )


def compute_bollinger_bands(
    series: pd.Series,
    window: int = 20,
    num_std: float = 2.0,
) -> pd.DataFrame:
    """Compute Bollinger Bands (upper, middle, lower, bandwidth, percent_b)."""
    if len(series) == 0:
        msg = "Cannot compute Bollinger Bands on empty series"
        raise ValueError(msg)

    middle = compute_sma(series, window=window)
    std = series.rolling(window=window).std()
    upper = middle + (std * num_std)
    lower = middle - (std * num_std)

    denom = upper - lower
    # Avoid zero division when prices are completely flat
    percent_b = (series - lower) / denom.replace(0.0, np.nan)
    bandwidth = (upper - lower) / middle.replace(0.0, np.nan)

    return pd.DataFrame(
        {
            "upper": upper,
            "middle": middle,
            "lower": lower,
            "bandwidth": bandwidth.fillna(0.0),
            "percent_b": percent_b.fillna(0.5),
        },
        index=series.index,
    )


def compute_atr(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    period: int = 14,
) -> pd.Series:
    """Compute Average True Range (ATR) using Wilder's smoothing."""
    if len(close) == 0:
        msg = "Cannot compute ATR on empty series"
        raise ValueError(msg)

    prev_close = close.shift(1)
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()

    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.ewm(alpha=1.0 / period, adjust=False).mean()
