"""Research client interface and HTTP implementation."""

from abc import ABC, abstractmethod

import httpx
from pydantic import ValidationError

from autonomous_trading_analyst.tools.research.models import (
    ResearchConnectionError,
    ResearchError,
    ResearchReport,
    ResearchRequest,
    ResearchTimeoutError,
)


class ResearchClient(ABC):
    """Abstract interface for retrieving financial research reports."""

    @abstractmethod
    def get_research(self, ticker: str, query: str | None = None) -> ResearchReport:
        """Fetch research analysis for a given ticker."""


class HttpResearchClient(ResearchClient):
    """Production HTTP client querying P-09 Financial Research Agent."""

    def __init__(self, base_url: str, timeout_s: float = 60.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_s = timeout_s

    def get_research(self, ticker: str, query: str | None = None) -> ResearchReport:
        """Issue POST /research to the upstream research service."""
        request_model = ResearchRequest(ticker=ticker, query=query)
        endpoint = f"{self.base_url}/research"

        try:
            with httpx.Client(timeout=self.timeout_s) as client:
                response = client.post(endpoint, json=request_model.model_dump())
                response.raise_for_status()
                data = response.json()
        except httpx.TimeoutException as exc:
            msg = f"Research request timed out after {self.timeout_s}s for {ticker}"
            raise ResearchTimeoutError(msg) from exc
        except httpx.ConnectError as exc:
            msg = f"Failed to connect to research service at {self.base_url}: {exc}"
            raise ResearchConnectionError(msg) from exc
        except httpx.HTTPStatusError as exc:
            msg = f"Research service returned HTTP {exc.response.status_code}: {exc.response.text}"
            raise ResearchError(msg) from exc
        except Exception as exc:
            msg = f"Unexpected error during research request for {ticker}: {exc}"
            raise ResearchError(msg) from exc

        try:
            return ResearchReport.model_validate(data)
        except ValidationError as exc:
            msg = f"Malformed research response structure: {exc}"
            raise ResearchError(msg) from exc
