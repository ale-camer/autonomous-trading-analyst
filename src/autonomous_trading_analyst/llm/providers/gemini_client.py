from typing import Any

from google import genai
from google.genai import types

from autonomous_trading_analyst.llm.client import LLMClient
from autonomous_trading_analyst.llm.messages import Message, Role, ToolCall
from autonomous_trading_analyst.llm.pricing import calculate_cost


class GeminiClient(LLMClient):
    """Google Gemini implementation of the LLMClient."""

    def __init__(self, api_key: str, model: str = "gemini-1.5-flash") -> None:
        self.client = genai.Client(api_key=api_key)
        self.model = model

    async def generate(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]] | None = None,
    ) -> tuple[Message, dict[str, Any]]:
        contents = []
        system_instruction = None
        for msg in messages:
            if msg.role == Role.SYSTEM:
                system_instruction = msg.content
                continue

            role = "user" if msg.role in (Role.USER, Role.TOOL) else "model"
            parts = []
            if msg.content:
                parts.append(types.Part.from_text(text=msg.content))

            if msg.role == Role.TOOL:
                parts.append(
                    types.Part.from_function_response(
                        name="unknown",
                        response={"result": msg.content},
                    )
                )
            elif msg.tool_calls:
                for tc in msg.tool_calls:
                    parts.append(
                        types.Part.from_function_call(
                            name=tc.name,
                            args=tc.arguments,
                        )
                    )

            contents.append(types.Content(role=role, parts=parts))

        config_args: dict[str, Any] = {}
        if system_instruction:
            config_args["system_instruction"] = system_instruction

        if tools:
            gemini_tools = []
            for t in tools:
                gemini_tools.append(
                    types.Tool(
                        function_declarations=[
                            types.FunctionDeclaration(
                                name=t["name"],
                                description=t["description"],
                                parameters=t["parameters_schema"],
                            )
                        ]
                    )
                )
            config_args["tools"] = gemini_tools

        config = types.GenerateContentConfig(**config_args)

        response = await self.client.aio.models.generate_content(
            model=self.model,
            contents=contents,
            config=config,
        )

        content = None
        tool_calls = None

        if (
            response.candidates
            and response.candidates[0].content
            and response.candidates[0].content.parts
        ):
            for part in response.candidates[0].content.parts:
                if part.text:
                    content = part.text
                elif part.function_call:
                    if tool_calls is None:
                        tool_calls = []
                    args = part.function_call.args
                    tool_calls.append(
                        ToolCall(
                            id="gemini_call",
                            name=str(part.function_call.name),
                            arguments=dict(args) if args else {},
                        )
                    )

        res_msg = Message(
            role=Role.ASSISTANT,
            content=content,
            tool_calls=tool_calls,
        )

        pt = 0
        ct = 0
        if response.usage_metadata:
            pt = response.usage_metadata.prompt_token_count or 0
            ct = response.usage_metadata.candidates_token_count or 0

        usage = {
            "prompt_tokens": pt,
            "completion_tokens": ct,
            "total_tokens": pt + ct,
            "cost_usd": calculate_cost(self.model, pt, ct),
        }

        return res_msg, usage
