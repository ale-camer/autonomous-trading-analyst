from typing import Any

from autonomous_trading_analyst.llm.client import LLMClient
from autonomous_trading_analyst.llm.messages import Message


class FakeLLMClient(LLMClient):
    """
    A fake LLM client that returns pre-programmed responses for deterministic testing.
    """

    def __init__(
        self,
        responses: list[Message],
        usages: list[dict[str, Any]] | None = None,
    ) -> None:
        """
        Initialize the fake client with a list of mock responses.

        Args:
            responses: The sequence of messages to return on consecutive calls to generate.
            usages: Optional sequence of usage dictionaries corresponding to responses.
        """
        self.responses = list(responses)
        self.usages = list(usages) if usages is not None else None
        self.received_messages: list[list[Message]] = []

    async def generate(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]] | None = None,
    ) -> tuple[Message, dict[str, Any]]:
        """
        Simulate an LLM response by returning the next message in the pre-programmed sequence.

        Args:
            messages: The input conversation history.
            tools: Optional tool definitions.

        Returns:
            The next mock message and a dummy token usage dictionary.

        Raises:
            RuntimeError: If the pre-programmed responses are exhausted.
        """
        self.received_messages.append(messages)

        if not self.responses:
            raise RuntimeError("FakeLLMClient: No more mock responses available.")

        response_msg = self.responses.pop(0)

        if self.usages:
            usage = self.usages.pop(0)
        else:
            usage = {
                "prompt_tokens": 10,
                "completion_tokens": 20,
                "total_tokens": 30,
                "cost_usd": 0.0,
            }

        return response_msg, usage
