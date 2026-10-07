from typing import Any, Protocol

from autonomous_trading_analyst.llm.messages import Message


class LLMClient(Protocol):
    """
    Protocol defining the provider-agnostic interface for an LLM client.
    """

    async def generate(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]] | None = None,
    ) -> tuple[Message, dict[str, int]]:
        """
        Generate a response from the LLM.

        Args:
            messages: A list of Message objects representing the conversation history.
            tools: An optional list of tool definition schemas.

        Returns:
            A tuple containing:
            - The generated Message (which may include tool_calls or text content).
            - A dictionary containing token usage metrics (e.g., prompt_tokens, completion_tokens).
        """
        ...
