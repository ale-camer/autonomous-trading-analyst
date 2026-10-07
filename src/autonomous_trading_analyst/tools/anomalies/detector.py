"""Statistical market anomaly detection (P-06 style)."""

from datetime import UTC, datetime
from typing import Any

import pandas as pd

from autonomous_trading_analyst.tools.anomalies.models import (
    AnomalyEvent,
    AnomalyReport,
    AnomalySeverity,
    AnomalyType,
)


class AnomalyDetector:
    """Detects statistical outliers in trading volume, returns, and volatility."""

    def __init__(
        self,
        lookback_window: int = 20,
        volume_z_threshold: float = 2.5,
        return_z_threshold: float = 2.5,
        volatility_ratio_threshold: float = 2.0,
    ) -> None:
        if lookback_window < 5:
            msg = f"Lookback window must be at least 5, got {lookback_window}"
            raise ValueError(msg)
        self.lookback_window = lookback_window
        self.volume_z_threshold = volume_z_threshold
        self.return_z_threshold = return_z_threshold
        self.volatility_ratio_threshold = volatility_ratio_threshold

    def _determine_severity(self, score: float, base_threshold: float) -> AnomalySeverity:
        if score >= base_threshold * 1.6:
            return AnomalySeverity.HIGH
        if score >= base_threshold * 1.2:
            return AnomalySeverity.MEDIUM
        return AnomalySeverity.LOW

    def detect(self, df: pd.DataFrame, ticker: str = "UNKNOWN") -> AnomalyReport:
        """Run statistical anomaly detection over OHLCV data."""
        if df is None or df.empty:
            msg = "DataFrame cannot be empty for anomaly detection"
            raise ValueError(msg)

        cols = {str(c).lower(): c for c in df.columns}
        if "close" not in cols or "volume" not in cols:
            msg = "DataFrame must contain at least 'close' and 'volume' columns"
            raise ValueError(msg)

        last_dt = (
            df.index[-1].to_pydatetime()
            if isinstance(df.index, pd.DatetimeIndex)
            else datetime.now(UTC)
        )
        if last_dt.tzinfo is None:
            last_dt = last_dt.replace(tzinfo=UTC)

        if len(df) < self.lookback_window + 1:
            return AnomalyReport(
                ticker=ticker,
                timestamp=last_dt,
                is_anomaly=False,
                anomalies=[],
                summary=(
                    f"Insufficient history ({len(df)} bars); "
                    f"requires at least {self.lookback_window + 1} bars"
                ),
            )

        close = df[cols["close"]].astype(float)
        volume = df[cols["volume"]].astype(float)
        anomalies: list[AnomalyEvent] = []

        # 1. Volume spike detection
        # Use preceding lookback_window to calculate baseline stats
        baseline_vol = volume.iloc[-(self.lookback_window + 1) : -1]
        vol_mean = float(baseline_vol.mean())
        vol_std = float(baseline_vol.std())
        last_vol = float(volume.iloc[-1])

        if vol_std > 0:
            z_vol = (last_vol - vol_mean) / vol_std
            if z_vol >= self.volume_z_threshold:
                mult = (last_vol / vol_mean) if vol_mean > 0 else 0.0
                severity = self._determine_severity(z_vol, self.volume_z_threshold)
                anomalies.append(
                    AnomalyEvent(
                        type=AnomalyType.VOLUME_SPIKE,
                        score=float(z_vol),
                        threshold=self.volume_z_threshold,
                        severity=severity,
                        description=(
                            f"Unusual volume spike (z={z_vol:.2f}, {mult:.1f}x "
                            f"{self.lookback_window}-bar average)"
                        ),
                    )
                )

        # 2. Price return shock detection
        returns = close.pct_change()
        baseline_ret = returns.iloc[-(self.lookback_window + 1) : -1]
        ret_mean = float(baseline_ret.mean())
        ret_std = float(baseline_ret.std())
        last_ret = float(returns.iloc[-1])

        if ret_std > 0:
            z_ret = abs(last_ret - ret_mean) / ret_std
            if z_ret >= self.return_z_threshold:
                severity = self._determine_severity(z_ret, self.return_z_threshold)
                anomalies.append(
                    AnomalyEvent(
                        type=AnomalyType.PRICE_JUMP,
                        score=float(z_ret),
                        threshold=self.return_z_threshold,
                        severity=severity,
                        description=(f"Extreme price move ({last_ret * 100:+.2f}%, z={z_ret:.2f})"),
                    )
                )

        # 3. Volatility expansion detection (True Range vs ATR)
        if "high" in cols and "low" in cols:
            high = df[cols["high"]].astype(float)
            low = df[cols["low"]].astype(float)
            prev_close = close.shift(1)
            tr = pd.concat(
                [high - low, (high - prev_close).abs(), (low - prev_close).abs()],
                axis=1,
            ).max(axis=1)

            baseline_tr = tr.iloc[-(self.lookback_window + 1) : -1]
            atr = float(baseline_tr.mean())
            last_tr = float(tr.iloc[-1])

            if atr > 0:
                ratio_vol = last_tr / atr
                if ratio_vol >= self.volatility_ratio_threshold:
                    severity = self._determine_severity(ratio_vol, self.volatility_ratio_threshold)
                    anomalies.append(
                        AnomalyEvent(
                            type=AnomalyType.VOLATILITY_EXPANSION,
                            score=float(ratio_vol),
                            threshold=self.volatility_ratio_threshold,
                            severity=severity,
                            description=(
                                f"Volatility expansion (candle range {ratio_vol:.1f}x "
                                f"{self.lookback_window}-bar ATR)"
                            ),
                        )
                    )

        is_anomaly = len(anomalies) > 0
        summary = (
            "; ".join(a.description for a in anomalies)
            if is_anomaly
            else "Normal market conditions (no anomalies detected)"
        )

        return AnomalyReport(
            ticker=ticker,
            timestamp=last_dt,
            is_anomaly=is_anomaly,
            anomalies=anomalies,
            summary=summary,
        )


def detect_anomalies(
    df: pd.DataFrame,
    ticker: str = "UNKNOWN",
    **kwargs: Any,
) -> AnomalyReport:
    """Convenience functional wrapper for AnomalyDetector."""
    detector = AnomalyDetector(**kwargs)
    return detector.detect(df, ticker=ticker)
