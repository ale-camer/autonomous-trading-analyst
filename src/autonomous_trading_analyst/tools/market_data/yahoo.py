"""Yahoo Finance market data provider using yfinance."""

from datetime import UTC, date, datetime

import pandas as pd
import yfinance as yf

from autonomous_trading_analyst.tools.market_data.base import (
    EXPECTED_OHLCV_COLUMNS,
    MarketDataError,
    MarketDataProvider,
    TickerNotFoundError,
)


def _to_date_str(d: datetime | date) -> str:
    """Format datetime or date into YYYY-MM-DD string for yfinance."""
    if isinstance(d, datetime):
        return d.strftime("%Y-%m-%d")
    return d.strftime("%Y-%m-%d")


class YahooMarketDataProvider(MarketDataProvider):
    """Retrieves live or cached market data from Yahoo Finance."""

    def get_bars(
        self,
        ticker: str,
        start: datetime | date,
        end: datetime | date,
        interval: str = "1d",
    ) -> pd.DataFrame:
        """Download OHLCV bars from Yahoo Finance.

        Returns DataFrame indexed by UTC DatetimeIndex ('timestamp')
        with standard lowercase columns.
        """
        symbol = ticker.strip().upper()
        start_str = _to_date_str(start)
        end_str = _to_date_str(end)

        try:
            yticker = yf.Ticker(symbol)
            df = yticker.history(start=start_str, end=end_str, interval=interval)
        except Exception as exc:
            msg = f"Failed to fetch market data for {symbol}: {exc}"
            raise MarketDataError(msg) from exc

        if df is None or df.empty:
            msg = f"No market data found for ticker {symbol} between {start_str} and {end_str}"
            raise TickerNotFoundError(msg)

        # Standardize column names to lowercase
        df = df.rename(columns={col: str(col).lower() for col in df.columns})

        missing = [col for col in EXPECTED_OHLCV_COLUMNS if col not in df.columns]
        if missing:
            msg = f"Incomplete market data returned for {symbol}, missing columns: {missing}"
            raise MarketDataError(msg)

        # Keep only standard columns
        df = df[list(EXPECTED_OHLCV_COLUMNS)].copy()

        # Normalize index to UTC DatetimeIndex
        if not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index, utc=True)
        elif df.index.tz is None:
            df.index = df.index.tz_localize(UTC)
        else:
            df.index = df.index.tz_convert(UTC)

        df.index.name = "timestamp"
        return df

    def get_latest_price(self, ticker: str) -> float:
        """Fetch latest price for ticker from Yahoo Finance."""
        symbol = ticker.strip().upper()
        try:
            yticker = yf.Ticker(symbol)
            # fast_info provides low-latency quote metadata
            if hasattr(yticker, "fast_info") and "lastPrice" in yticker.fast_info:
                last_price = yticker.fast_info["lastPrice"]
                if last_price is not None and last_price > 0:
                    return float(last_price)

            hist = yticker.history(period="5d")
            if hist is not None and not hist.empty:
                return float(hist["Close"].iloc[-1])
        except Exception as exc:
            msg = f"Failed to fetch latest price for {symbol}: {exc}"
            raise MarketDataError(msg) from exc

        msg = f"Could not determine price for ticker {symbol}"
        raise TickerNotFoundError(msg)
