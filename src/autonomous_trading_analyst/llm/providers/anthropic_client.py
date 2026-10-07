from typing import Any

from anthropic import AsyncAnthropic

from autonomous_trading_analyst.llm.client import LLMClient
from autonomous_trading_analyst.llm.messages import Message, Role, ToolCall
from autonomous_trading_analyst.llm.pricing import calculate_cost


class AnthropicClient(LLMClient):
    """Anthropic API implementation of the LLMClient."""

    def __init__(self, api_key: str, model: str = "claude-3-5-sonnet-latest") -> None:
        self.client = AsyncAnthropic(api_key=api_key)
        self.model = model

    async def generate(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]] | None = None,
    ) -> tuple[Message, dict[str, Any]]:
        system_prompt = next((m.content for m in messages if m.role == Role.SYSTEM), "")

        anthropic_messages: list[dict[str, Any]] = []
        for msg in messages:
            if msg.role == Role.SYSTEM:
                continue

            if msg.role == Role.USER:
                anthropic_messages.append({"role": "user", "content": msg.content or ""})
            elif msg.role == Role.ASSISTANT:
                content_blocks: list[dict[str, Any]] = []
                if msg.content:
                    content_blocks.append({"type": "text", "text": msg.content})
                if msg.tool_calls:
                    for tc in msg.tool_calls:
                        content_blocks.append(
                            {
                                "type": "tool_use",
                                "id": tc.id,
                                "name": tc.name,
                                "input": tc.arguments,
                            }
                        )
                anthropic_messages.append({"role": "assistant", "content": content_blocks})
            elif msg.role == Role.TOOL:
                anthropic_messages.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": msg.tool_call_id,
                                "content": msg.content,
                            }
                        ],
                    }
                )

        kwargs: dict[str, Any] = {
            "model": self.model,
            "system": system_prompt or "",
            "messages": anthropic_messages,
            "max_tokens": 4096,
        }

        if tools:
            kwargs["tools"] = [
                {
                    "name": t["name"],
                    "description": t["description"],
                    "input_schema": t["parameters_schema"],
                }
                for t in tools
            ]

        response = await self.client.messages.create(**kwargs)

        content = None
        tool_calls = None

        for block in response.content:
            if block.type == "text":
                content = block.text
            elif block.type == "tool_use":
                if tool_calls is None:
                    tool_calls = []
                tool_calls.append(
                    ToolCall(
                        id=block.id,
                        name=block.name,
                        arguments=block.input,
                    )
                )

        res_msg = Message(
            role=Role.ASSISTANT,
            content=content,
            tool_calls=tool_calls,
        )

        pt = response.usage.input_tokens
        ct = response.usage.output_tokens

        usage = {
            "prompt_tokens": pt,
            "completion_tokens": ct,
            "total_tokens": pt + ct,
            "cost_usd": calculate_cost(self.model, pt, ct),
        }

        return res_msg, usage
