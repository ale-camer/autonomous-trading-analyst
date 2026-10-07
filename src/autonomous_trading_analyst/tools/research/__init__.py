"""Research module integrating with P-09 Financial Research Agent."""

from autonomous_trading_analyst.config import get_settings
from autonomous_trading_analyst.tools.research.client import (
    HttpResearchClient,
    ResearchClient,
)
from autonomous_trading_analyst.tools.research.fake import FakeResearchClient
from autonomous_trading_analyst.tools.research.models import (
    ResearchConnectionError,
    ResearchError,
    ResearchReport,
    ResearchRequest,
    ResearchTimeoutError,
    Sentiment,
)


def get_research_client(
    use_fake: bool = False,
    base_url: str | None = None,
    timeout_s: float | None = None,
) -> ResearchClient:
    """Factory creating configured ResearchClient instance."""
    if use_fake:
        return FakeResearchClient()

    settings = get_settings()
    url = base_url or settings.research_api_url
    timeout = timeout_s if timeout_s is not None else settings.research_api_timeout_s

    return HttpResearchClient(base_url=url, timeout_s=timeout)


__all__ = [
    "FakeResearchClient",
    "HttpResearchClient",
    "ResearchClient",
    "ResearchConnectionError",
    "ResearchError",
    "ResearchReport",
    "ResearchRequest",
    "ResearchTimeoutError",
    "Sentiment",
    "get_research_client",
]
