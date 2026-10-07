"""Technical indicators module providing calculation routines and snapshot generation."""

from datetime import UTC, datetime

import numpy as np
import pandas as pd

from autonomous_trading_analyst.tools.indicators.calculations import (
    compute_atr,
    compute_bollinger_bands,
    compute_ema,
    compute_macd,
    compute_rsi,
    compute_sma,
)
from autonomous_trading_analyst.tools.indicators.models import (
    BollingerBandsResult,
    MACDResult,
    TechnicalIndicatorsSnapshot,
)


def _safe_float(val: float | np.floating | None) -> float | None:
    """Return float or None if NaN/None."""
    if val is None or pd.isna(val):
        return None
    return float(val)


def compute_technical_indicators(
    df: pd.DataFrame,
    ticker: str = "UNKNOWN",
) -> TechnicalIndicatorsSnapshot:
    """Calculate all technical indicators on an OHLCV DataFrame and return a snapshot.

    Expected DataFrame columns: 'close', 'high', 'low'.
    """
    if df is None or df.empty:
        msg = "DataFrame cannot be empty when computing technical indicators"
        raise ValueError(msg)

    cols = {str(c).lower(): c for c in df.columns}
    if "close" not in cols:
        msg = "DataFrame must contain a 'close' column"
        raise ValueError(msg)

    close = df[cols["close"]].astype(float)
    high = df[cols["high"]].astype(float) if "high" in cols else close
    low = df[cols["low"]].astype(float) if "low" in cols else close

    last_dt = (
        df.index[-1].to_pydatetime()
        if isinstance(df.index, pd.DatetimeIndex)
        else datetime.now(UTC)
    )
    if last_dt.tzinfo is None:
        last_dt = last_dt.replace(tzinfo=UTC)

    close_price = float(close.iloc[-1])

    # SMAs and EMAs
    sma_20 = _safe_float(compute_sma(close, window=20).iloc[-1])
    sma_50 = _safe_float(compute_sma(close, window=50).iloc[-1])
    sma_200 = _safe_float(compute_sma(close, window=200).iloc[-1])
    ema_12 = _safe_float(compute_ema(close, span=12).iloc[-1])
    ema_26 = _safe_float(compute_ema(close, span=26).iloc[-1])

    # RSI
    rsi_14 = _safe_float(compute_rsi(close, period=14).iloc[-1])

    # MACD
    macd_df = compute_macd(close, fast=12, slow=26, signal=9)
    m_val = _safe_float(macd_df["macd"].iloc[-1])
    s_val = _safe_float(macd_df["signal"].iloc[-1])
    h_val = _safe_float(macd_df["histogram"].iloc[-1])
    macd_res = (
        MACDResult(macd=m_val, signal=s_val, histogram=h_val)
        if m_val is not None and s_val is not None and h_val is not None
        else None
    )

    # Bollinger Bands
    bb_df = compute_bollinger_bands(close, window=20, num_std=2.0)
    u_val = _safe_float(bb_df["upper"].iloc[-1])
    mid_val = _safe_float(bb_df["middle"].iloc[-1])
    l_val = _safe_float(bb_df["lower"].iloc[-1])
    bw_val = _safe_float(bb_df["bandwidth"].iloc[-1])
    pb_val = _safe_float(bb_df["percent_b"].iloc[-1])
    bb_res = (
        BollingerBandsResult(
            upper=u_val,
            middle=mid_val,
            lower=l_val,
            bandwidth=bw_val or 0.0,
            percent_b=pb_val or 0.5,
        )
        if u_val is not None and mid_val is not None and l_val is not None
        else None
    )

    # ATR
    atr_14 = _safe_float(compute_atr(high, low, close, period=14).iloc[-1])

    return TechnicalIndicatorsSnapshot(
        ticker=ticker,
        timestamp=last_dt,
        close_price=close_price,
        rsi_14=rsi_14,
        sma_20=sma_20,
        sma_50=sma_50,
        sma_200=sma_200,
        ema_12=ema_12,
        ema_26=ema_26,
        macd=macd_res,
        bollinger=bb_res,
        atr_14=atr_14,
    )


__all__ = [
    "BollingerBandsResult",
    "MACDResult",
    "TechnicalIndicatorsSnapshot",
    "compute_atr",
    "compute_bollinger_bands",
    "compute_ema",
    "compute_macd",
    "compute_rsi",
    "compute_sma",
    "compute_technical_indicators",
]
