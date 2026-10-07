from autonomous_trading_analyst.config import Settings
from autonomous_trading_analyst.llm.client import LLMClient
from autonomous_trading_analyst.llm.fake import FakeLLMClient
from autonomous_trading_analyst.llm.providers.anthropic_client import AnthropicClient
from autonomous_trading_analyst.llm.providers.gemini_client import GeminiClient
from autonomous_trading_analyst.llm.providers.openai_client import OpenAIClient


def get_llm_client(settings: Settings) -> LLMClient:
    """Factory to get the configured LLMClient."""
    provider = settings.llm_provider
    model = settings.llm_model

    if provider == "fake":
        return FakeLLMClient(responses=[])

    if provider == "openai":
        api_key = settings.openai_api_key.get_secret_value() if settings.openai_api_key else ""
        return OpenAIClient(api_key=api_key, model=model)

    if provider == "anthropic":
        anthropic_key = settings.anthropic_api_key
        api_key = anthropic_key.get_secret_value() if anthropic_key else ""
        return AnthropicClient(api_key=api_key, model=model)

    if provider == "gemini":
        gemini_key = settings.google_api_key
        api_key = gemini_key.get_secret_value() if gemini_key else ""
        return GeminiClient(api_key=api_key, model=model)

    raise ValueError(f"Unknown LLM provider: {provider}")
