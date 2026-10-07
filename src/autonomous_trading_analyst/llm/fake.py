from typing import Any

from autonomous_trading_analyst.llm.client import LLMClient
from autonomous_trading_analyst.llm.messages import Message


class FakeLLMClient(LLMClient):
    """
    A fake LLM client that returns pre-programmed responses for deterministic testing.
    """

    def __init__(self, responses: list[Message]) -> None:
        """
        Initialize the fake client with a list of mock responses.

        Args:
            responses: The sequence of messages to return on consecutive calls to generate.
        """
        self.responses = responses
        self.received_messages: list[list[Message]] = []

    async def generate(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]] | None = None,
    ) -> tuple[Message, dict[str, int]]:
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

        usage = {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30}

        return response_msg, usage
