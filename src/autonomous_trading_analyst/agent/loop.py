"""ReAct orchestration loop for autonomous trading analysis."""

import asyncio
from typing import Any

from autonomous_trading_analyst.agent.signal import TradingSignal
from autonomous_trading_analyst.agent.trace import Scratchpad, TraceStep
from autonomous_trading_analyst.config import Settings, get_settings
from autonomous_trading_analyst.llm.client import LLMClient
from autonomous_trading_analyst.llm.messages import Message, Role
from autonomous_trading_analyst.tools.registry import ToolRegistry

SYSTEM_PROMPT_TEMPLATE = (
    "You are an Autonomous Trading Analyst, an expert financial intelligence agent.\n"
    "Your objective is to thoroughly analyze the market dynamics for ticker: {ticker}.\n\n"
    "Operational Rules:\n"
    "1. Reason step-by-step (Thought) about what information is needed to evaluate {ticker}.\n"
    "2. Use available market tools (Action) to inspect historical prices, technical indicators, "
    "market anomalies, and research.\n"
    "3. Review tool outputs (Observation) carefully to refine your thesis.\n"
    "4. When you have collected sufficient evidence to form a conviction, you MUST conclude your "
    "analysis by calling the 'submit_signal' tool with your final decision (BUY, SELL, or HOLD), "
    "confidence level (0.0 to 1.0), and a structured rationale.\n"
    "5. You operate under strict resource constraints:\n"
    "   - Maximum Steps: {max_steps}\n"
    "   - Maximum Cost Budget: ${max_cost:.4f} USD\n"
    "Do not stall or output conversational filler without taking action. Make decisive progress "
    "toward submitting your signal within the allotted budget."
)


class ReActAgent:
    """Agent orchestrating the Reasoning and Acting (ReAct) decision loop."""

    def __init__(
        self,
        llm_client: LLMClient,
        tool_registry: ToolRegistry,
        settings: Settings | None = None,
    ) -> None:
        """Initialize ReActAgent with LLM client, tool registry, and application settings."""
        self.llm_client = llm_client
        self.tool_registry = tool_registry
        self.settings = settings if settings is not None else get_settings()

    def _build_tools_schema(self) -> list[dict[str, Any]]:
        """Construct tool schemas including registry tools and terminal submit_signal."""
        tools: list[dict[str, Any]] = []
        for tool_def in self.tool_registry.list_tools():
            tools.append(
                {
                    "name": tool_def.name,
                    "description": tool_def.description,
                    "parameters_schema": tool_def.parameters,
                    "parameters": tool_def.parameters,
                }
            )

        submit_signal_schema = TradingSignal.model_json_schema()
        submit_signal_schema.pop("title", None)

        tools.append(
            {
                "name": "submit_signal",
                "description": (
                    "Submit the final trading decision signal for the ticker (BUY, SELL, or HOLD) "
                    "with confidence score and rationale to conclude analysis."
                ),
                "parameters_schema": submit_signal_schema,
                "parameters": submit_signal_schema,
            }
        )
        return tools

    async def run(self, ticker: str) -> Scratchpad:
        """
        Execute the ReAct reasoning and acting loop for the given ticker.

        Terminates upon submit_signal invocation, reaching max steps, or exceeding cost budget.
        """
        clean_ticker = ticker.strip().upper()
        system_content = SYSTEM_PROMPT_TEMPLATE.format(
            ticker=clean_ticker,
            max_steps=self.settings.agent_max_steps,
            max_cost=self.settings.agent_max_cost_usd_per_decision,
        )
        system_msg = Message(role=Role.SYSTEM, content=system_content)
        user_msg = Message(
            role=Role.USER,
            content=f"Please analyze ticker {clean_ticker} and submit trading signal.",
        )
        scratchpad = Scratchpad(system_prompt=system_msg, user_prompt=user_msg)
        tools_schema = self._build_tools_schema()

        for _ in range(self.settings.agent_max_steps):
            if scratchpad.total_cost_usd >= self.settings.agent_max_cost_usd_per_decision:
                break

            messages = scratchpad.get_messages()
            res_msg, usage = await self.llm_client.generate(
                messages=messages,
                tools=tools_schema,
            )

            observations: list[Message] = []
            signal_submitted = False

            if res_msg.tool_calls:
                for tool_call in res_msg.tool_calls:
                    if tool_call.name == "submit_signal":
                        try:
                            signal_data = dict(tool_call.arguments)
                            if "ticker" not in signal_data or not signal_data["ticker"]:
                                signal_data["ticker"] = clean_ticker
                            signal = TradingSignal.model_validate(signal_data)
                            scratchpad.signal = signal
                            signal_submitted = True
                            obs_content = (
                                f"Signal {signal.decision.value} for {signal.ticker} "
                                f"submitted successfully."
                            )
                        except Exception as exc:
                            obs_content = f"Error validating signal: {type(exc).__name__}: {exc}"

                        observations.append(
                            Message(
                                role=Role.TOOL,
                                content=obs_content,
                                tool_call_id=tool_call.id,
                            )
                        )
                    else:
                        try:
                            obs_content = self.tool_registry.execute(
                                tool_call.name, tool_call.arguments
                            )
                        except Exception as exc:
                            obs_content = (
                                f"Error executing tool '{tool_call.name}': "
                                f"{type(exc).__name__}: {exc}"
                            )

                        observations.append(
                            Message(
                                role=Role.TOOL,
                                content=obs_content,
                                tool_call_id=tool_call.id,
                            )
                        )
            else:
                observations.append(
                    Message(
                        role=Role.USER,
                        content=(
                            "No tool call was requested. Please use an available market tool "
                            "to gather data or call 'submit_signal' to conclude your analysis."
                        ),
                    )
                )

            step = TraceStep(
                llm_message=res_msg,
                usage=usage,
                observations=observations,
            )
            scratchpad.add_step(step)

            if signal_submitted:
                break

            if scratchpad.total_cost_usd >= self.settings.agent_max_cost_usd_per_decision:
                break

        return scratchpad

    def run_sync(self, ticker: str) -> Scratchpad:
        """Synchronous wrapper for run()."""
        return asyncio.run(self.run(ticker))
