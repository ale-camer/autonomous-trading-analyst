"""Fake research client for offline deterministic testing and simulation."""

from datetime import UTC, datetime

from autonomous_trading_analyst.tools.research.client import ResearchClient
from autonomous_trading_analyst.tools.research.models import (
    ResearchConnectionError,
    ResearchReport,
    ResearchTimeoutError,
    Sentiment,
)


class FakeResearchClient(ResearchClient):
    """Deterministic, offline fake research client."""

    def __init__(self) -> None:
        self._seeded_reports: dict[str, ResearchReport] = {}
        self._simulate_timeout = False
        self._simulate_connection_error = False

    def seed_report(self, ticker: str, report: ResearchReport) -> None:
        """Seed a predefined report for a specific ticker."""
        self._seeded_reports[ticker.strip().upper()] = report

    def simulate_timeout(self, enabled: bool = True) -> None:
        """Configure client to raise ResearchTimeoutError on next calls."""
        self._simulate_timeout = enabled

    def simulate_connection_error(self, enabled: bool = True) -> None:
        """Configure client to raise ResearchConnectionError on next calls."""
        self._simulate_connection_error = enabled

    def get_research(self, ticker: str, query: str | None = None) -> ResearchReport:
        """Return seeded report or synthetic report for given ticker."""
        if self._simulate_timeout:
            msg = f"Simulated timeout error for {ticker}"
            raise ResearchTimeoutError(msg)
        if self._simulate_connection_error:
            msg = f"Simulated connection failure for {ticker}"
            raise ResearchConnectionError(msg)

        symbol = ticker.strip().upper()
        if symbol in self._seeded_reports:
            return self._seeded_reports[symbol]

        # Deterministic generation based on symbol
        seed_val = sum(ord(c) for c in symbol) % 3
        if seed_val == 0:
            sentiment = Sentiment.BULLISH
            score = 0.65
            bias_text = "exhibits robust revenue momentum and strong balance sheet health"
        elif seed_val == 1:
            sentiment = Sentiment.BEARISH
            score = -0.55
            bias_text = "faces margin compression and decelerating forward guidance"
        else:
            sentiment = Sentiment.NEUTRAL
            score = 0.05
            bias_text = "trades within fair valuation bands with balanced risk-reward profile"

        return ResearchReport(
            ticker=symbol,
            summary=(
                f"Comprehensive financial research for {symbol}: Company {bias_text}. "
                f"Query context: {query or 'General research'}."
            ),
            sentiment=sentiment,
            score=score,
            key_findings=[
                f"Primary revenue streams for {symbol} remain stable",
                "Management execution aligned with consensus expectations",
                "Liquidity and debt coverage ratios meet risk thresholds",
            ],
            sources=["SEC Form 10-K", "Earnings Call Transcript", "Financial News Feed"],
            timestamp=datetime.now(UTC),
        )
