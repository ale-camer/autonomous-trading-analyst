"""Built-in market tools registration and factory for Milestone 1."""

from datetime import UTC, datetime, timedelta
from typing import Any

from pydantic import BaseModel, Field

from autonomous_trading_analyst.tools.anomalies import detect_anomalies
from autonomous_trading_analyst.tools.indicators import compute_technical_indicators
from autonomous_trading_analyst.tools.market_data import (
    MarketDataProvider,
    get_market_data_provider,
)
from autonomous_trading_analyst.tools.registry import ToolRegistry
from autonomous_trading_analyst.tools.research import (
    ResearchClient,
    get_research_client,
)


class LatestPriceArgs(BaseModel):
    """Arguments for get_latest_price tool."""

    ticker: str = Field(description="Ticker symbol to query (e.g., 'AAPL', 'MSFT').")


class HistoricalBarsArgs(BaseModel):
    """Arguments for get_historical_bars tool."""

    ticker: str = Field(description="Ticker symbol to query.")
    days: int = Field(default=30, ge=1, le=1000, description="Lookback days for historical bars.")


class TechnicalIndicatorsArgs(BaseModel):
    """Arguments for get_technical_indicators tool."""

    ticker: str = Field(description="Ticker symbol to compute indicators for.")
    lookback_days: int = Field(
        default=250, ge=15, le=1000, description="Days of history needed for calculation."
    )


class MarketAnomaliesArgs(BaseModel):
    """Arguments for get_market_anomalies tool."""

    ticker: str = Field(description="Ticker symbol to analyze for statistical anomalies.")
    lookback_days: int = Field(
        default=30, ge=10, le=100, description="Days of history for baseline anomaly scoring."
    )


class FinancialResearchArgs(BaseModel):
    """Arguments for get_financial_research tool."""

    ticker: str = Field(description="Ticker symbol to retrieve research for.")
    query: str | None = Field(
        default=None, description="Optional natural language query focus for research."
    )


def build_market_tools_registry(
    market_data_provider: MarketDataProvider | None = None,
    research_client: ResearchClient | None = None,
) -> ToolRegistry:
    """Build and populate a ToolRegistry containing all Milestone 1 market tools."""
    data_provider = market_data_provider or get_market_data_provider()
    research_prov = research_client or get_research_client()
    registry = ToolRegistry()

    # 1. Latest price tool
    def handle_latest_price(ticker: str) -> dict[str, Any]:
        price = data_provider.get_latest_price(ticker)
        return {"ticker": ticker.upper(), "price": price}

    registry.register(
        name="get_latest_price",
        description="Retrieve the most recent market price for an asset.",
        handler=handle_latest_price,
        args_schema=LatestPriceArgs,
    )

    # 2. Historical bars tool
    def handle_historical_bars(ticker: str, days: int = 30) -> list[dict[str, Any]]:
        end = datetime.now(UTC)
        start = end - timedelta(days=days)
        df = data_provider.get_bars(ticker, start=start, end=end)
        records = []
        for idx, row in df.iterrows():
            records.append(
                {
                    "timestamp": str(idx),
                    "open": float(row["open"]),
                    "high": float(row["high"]),
                    "low": float(row["low"]),
                    "close": float(row["close"]),
                    "volume": float(row["volume"]),
                }
            )
        return records

    registry.register(
        name="get_historical_bars",
        description="Fetch historical daily OHLCV price bars for a given ticker and duration.",
        handler=handle_historical_bars,
        args_schema=HistoricalBarsArgs,
    )

    # 3. Technical indicators tool
    def handle_technical_indicators(ticker: str, lookback_days: int = 250) -> dict[str, Any]:
        end = datetime.now(UTC)
        start = end - timedelta(days=lookback_days)
        df = data_provider.get_bars(ticker, start=start, end=end)
        snapshot = compute_technical_indicators(df, ticker=ticker)
        return snapshot.model_dump()

    registry.register(
        name="get_technical_indicators",
        description="Compute technical indicator snapshot (RSI, SMA, EMA, MACD, Bollinger, ATR).",
        handler=handle_technical_indicators,
        args_schema=TechnicalIndicatorsArgs,
    )

    # 4. Market anomalies tool
    def handle_market_anomalies(ticker: str, lookback_days: int = 30) -> dict[str, Any]:
        end = datetime.now(UTC)
        start = end - timedelta(days=lookback_days)
        df = data_provider.get_bars(ticker, start=start, end=end)
        report = detect_anomalies(df, ticker=ticker)
        return report.model_dump()

    registry.register(
        name="get_market_anomalies",
        description="Detect volume spikes, price shocks, and volatility expansions (P-06 style).",
        handler=handle_market_anomalies,
        args_schema=MarketAnomaliesArgs,
    )

    # 5. Financial research tool
    def handle_financial_research(ticker: str, query: str | None = None) -> dict[str, Any]:
        report = research_prov.get_research(ticker, query=query)
        return report.model_dump()

    registry.register(
        name="get_financial_research",
        description="Retrieve fundamental research and sentiment from the P-09 research agent.",
        handler=handle_financial_research,
        args_schema=FinancialResearchArgs,
    )

    return registry
