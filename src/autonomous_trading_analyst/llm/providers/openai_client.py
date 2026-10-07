import json
from typing import Any

from openai import AsyncOpenAI

from autonomous_trading_analyst.llm.client import LLMClient
from autonomous_trading_analyst.llm.messages import Message, Role, ToolCall
from autonomous_trading_analyst.llm.pricing import calculate_cost


class OpenAIClient(LLMClient):
    """OpenAI API implementation of the LLMClient."""

    def __init__(self, api_key: str, model: str = "gpt-4o-mini") -> None:
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model

    async def generate(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]] | None = None,
    ) -> tuple[Message, dict[str, Any]]:
        oai_messages = []
        for msg in messages:
            m: dict[str, Any] = {"role": msg.role.value}
            if msg.content is not None:
                m["content"] = msg.content
            if msg.tool_calls:
                m["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.name, "arguments": json.dumps(tc.arguments)},
                    }
                    for tc in msg.tool_calls
                ]
            if msg.tool_call_id:
                m["tool_call_id"] = msg.tool_call_id
            oai_messages.append(m)

        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": oai_messages,
        }

        if tools:
            kwargs["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": t["name"],
                        "description": t["description"],
                        "parameters": t["parameters_schema"],
                    },
                }
                for t in tools
            ]

        response = await self.client.chat.completions.create(**kwargs)
        choice = response.choices[0].message

        tool_calls = None
        if choice.tool_calls:
            tool_calls = [
                ToolCall(
                    id=tc.id,
                    name=tc.function.name,
                    arguments=json.loads(tc.function.arguments),
                )
                for tc in choice.tool_calls
            ]

        res_msg = Message(
            role=Role.ASSISTANT,
            content=choice.content,
            tool_calls=tool_calls,
        )

        pt = response.usage.prompt_tokens if response.usage else 0
        ct = response.usage.completion_tokens if response.usage else 0

        usage = {
            "prompt_tokens": pt,
            "completion_tokens": ct,
            "total_tokens": pt + ct,
            "cost_usd": calculate_cost(self.model, pt, ct),
        }

        return res_msg, usage
