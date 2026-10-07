"""Unit tests for P-09 financial research client."""

from datetime import UTC, datetime
from unittest.mock import MagicMock

import httpx
import pytest

from autonomous_trading_analyst.tools.research import (
    FakeResearchClient,
    HttpResearchClient,
    ResearchConnectionError,
    ResearchError,
    ResearchReport,
    ResearchTimeoutError,
    Sentiment,
    get_research_client,
)


@pytest.mark.issue_6
def test_fake_research_client_seeded() -> None:
    """FakeResearchClient returns exact seeded report when available."""
    client = FakeResearchClient()
    report = ResearchReport(
        ticker="AAPL",
        summary="Positive iPhone sales outlook",
        sentiment=Sentiment.BULLISH,
        score=0.8,
        key_findings=["Unit shipments up 12%"],
        sources=["Q3 Call"],
        timestamp=datetime.now(UTC),
    )
    client.seed_report("AAPL", report)

    res = client.get_research("AAPL")
    assert res.ticker == "AAPL"
    assert res.sentiment == Sentiment.BULLISH
    assert res.score == 0.8
    assert res.key_findings == ["Unit shipments up 12%"]


@pytest.mark.issue_6
def test_fake_research_client_synthetic() -> None:
    """FakeResearchClient generates deterministic synthetic report for unseeded tickers."""
    client = FakeResearchClient()
    res = client.get_research("MSFT", query="Cloud growth")

    assert res.ticker == "MSFT"
    assert isinstance(res.sentiment, Sentiment)
    assert -1.0 <= res.score <= 1.0
    assert len(res.key_findings) > 0
    assert len(res.sources) > 0
    assert "MSFT" in res.summary


@pytest.mark.issue_6
def test_fake_research_client_simulated_errors() -> None:
    """FakeResearchClient can simulate timeouts and connection drops."""
    client = FakeResearchClient()

    client.simulate_timeout(True)
    with pytest.raises(ResearchTimeoutError):
        client.get_research("NVDA")

    client.simulate_timeout(False)
    client.simulate_connection_error(True)
    with pytest.raises(ResearchConnectionError):
        client.get_research("NVDA")


@pytest.mark.issue_6
def test_http_research_client_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """HttpResearchClient issues POST /research and parses valid response."""
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "ticker": "TSLA",
        "summary": "Robotaxi event analysis indicates mixed sentiment",
        "sentiment": "NEUTRAL",
        "score": 0.05,
        "key_findings": ["Unveiled Cybercab", "Timeline uncertainty"],
        "sources": ["Press Release"],
        "timestamp": datetime.now(UTC).isoformat(),
    }

    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client
    mock_client.post.return_value = mock_response

    monkeypatch.setattr("httpx.Client", lambda **_kwargs: mock_client)

    client = HttpResearchClient(base_url="http://test-server:8000")
    report = client.get_research("TSLA", query="Robotaxi update")

    assert report.ticker == "TSLA"
    assert report.sentiment == Sentiment.NEUTRAL
    assert report.score == 0.05
    assert len(report.key_findings) == 2


@pytest.mark.issue_6
def test_http_research_client_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    """HttpResearchClient wraps httpx.TimeoutException in ResearchTimeoutError."""
    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client
    mock_client.post.side_effect = httpx.TimeoutException("Timed out")

    monkeypatch.setattr("httpx.Client", lambda **_kwargs: mock_client)

    client = HttpResearchClient(base_url="http://test-server:8000")
    with pytest.raises(ResearchTimeoutError, match="timed out"):
        client.get_research("AMZN")


@pytest.mark.issue_6
def test_http_research_client_connection_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """HttpResearchClient wraps httpx.ConnectError in ResearchConnectionError."""
    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client
    mock_client.post.side_effect = httpx.ConnectError("Connection refused")

    monkeypatch.setattr("httpx.Client", lambda **_kwargs: mock_client)

    client = HttpResearchClient(base_url="http://test-server:8000")
    with pytest.raises(ResearchConnectionError, match="Failed to connect"):
        client.get_research("AMZN")


@pytest.mark.issue_6
def test_http_research_client_http_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """HttpResearchClient converts HTTP status errors to ResearchError."""
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 500
    mock_response.text = "Internal Server Error"

    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client
    mock_client.post.side_effect = httpx.HTTPStatusError(
        message="500 Error",
        request=MagicMock(),
        response=mock_response,
    )

    monkeypatch.setattr("httpx.Client", lambda **_kwargs: mock_client)

    client = HttpResearchClient(base_url="http://test-server:8000")
    with pytest.raises(ResearchError, match="HTTP 500"):
        client.get_research("META")


@pytest.mark.issue_6
def test_http_research_client_malformed_json(monkeypatch: pytest.MonkeyPatch) -> None:
    """HttpResearchClient raises ResearchError on invalid response schema."""
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = {"invalid": "payload"}

    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client
    mock_client.post.return_value = mock_response

    monkeypatch.setattr("httpx.Client", lambda **_kwargs: mock_client)

    client = HttpResearchClient(base_url="http://test-server:8000")
    with pytest.raises(ResearchError, match="Malformed research response"):
        client.get_research("SPY")


@pytest.mark.issue_6
def test_get_research_client_factory() -> None:
    """Factory correctly resolves fake and HTTP client instances."""
    fake = get_research_client(use_fake=True)
    assert isinstance(fake, FakeResearchClient)

    http = get_research_client(use_fake=False, base_url="http://custom:9000", timeout_s=30.0)
    assert isinstance(http, HttpResearchClient)
    assert http.base_url == "http://custom:9000"
    assert http.timeout_s == 30.0
