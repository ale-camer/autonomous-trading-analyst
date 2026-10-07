import pytest
from pydantic import SecretStr

from autonomous_trading_analyst.config import Settings
from autonomous_trading_analyst.llm.factory import get_llm_client
from autonomous_trading_analyst.llm.fake import FakeLLMClient
from autonomous_trading_analyst.llm.pricing import calculate_cost
from autonomous_trading_analyst.llm.providers.anthropic_client import AnthropicClient
from autonomous_trading_analyst.llm.providers.gemini_client import GeminiClient
from autonomous_trading_analyst.llm.providers.openai_client import OpenAIClient


@pytest.mark.issue_9
def test_calculate_cost() -> None:
    """Test cost calculation based on pricing tables."""
    # 1 million tokens for gpt-4o-mini
    cost = calculate_cost("gpt-4o-mini", 1_000_000, 1_000_000)
    assert cost == 0.75  # 0.150 + 0.600

    cost_unknown = calculate_cost("unknown-model", 100, 100)
    assert cost_unknown == 0.0


@pytest.mark.issue_9
def test_get_llm_client_fake() -> None:
    """Test factory creates fake client."""
    settings = Settings(llm_provider="fake")
    client = get_llm_client(settings)
    assert isinstance(client, FakeLLMClient)


@pytest.mark.issue_9
def test_get_llm_client_openai() -> None:
    """Test factory creates OpenAI client."""
    settings = Settings(llm_provider="openai", openai_api_key=SecretStr("sk-test"))
    client = get_llm_client(settings)
    assert isinstance(client, OpenAIClient)


@pytest.mark.issue_9
def test_get_llm_client_anthropic() -> None:
    """Test factory creates Anthropic client."""
    settings = Settings(llm_provider="anthropic", anthropic_api_key=SecretStr("sk-test"))
    client = get_llm_client(settings)
    assert isinstance(client, AnthropicClient)


@pytest.mark.issue_9
def test_get_llm_client_gemini() -> None:
    """Test factory creates Gemini client."""
    settings = Settings(llm_provider="gemini", google_api_key=SecretStr("sk-test"))
    client = get_llm_client(settings)
    assert isinstance(client, GeminiClient)


@pytest.mark.issue_9
def test_get_llm_client_unknown() -> None:
    """Test factory raises ValueError for unknown provider."""
    # We bypass Pydantic Literal validation to test factory safety
    settings = Settings(llm_provider="fake")
    settings.llm_provider = "invalid"  # type: ignore
    with pytest.raises(ValueError, match="Unknown LLM provider: invalid"):
        get_llm_client(settings)
