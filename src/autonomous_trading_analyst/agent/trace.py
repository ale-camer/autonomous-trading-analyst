from typing import Any

from pydantic import BaseModel, Field

from autonomous_trading_analyst.agent.signal import TradingSignal
from autonomous_trading_analyst.llm.messages import Message


class TraceStep(BaseModel):
    """A single step in the agent's decision trace."""

    llm_message: Message
    usage: dict[str, Any] | None = None
    observations: list[Message] = Field(default_factory=list)


class Scratchpad(BaseModel):
    """Short-term memory recording thoughts, tool calls, and observations for an episode."""

    system_prompt: Message | None = None
    user_prompt: Message | None = None
    steps: list[TraceStep] = Field(default_factory=list)
    signal: TradingSignal | None = None

    def add_step(self, step: TraceStep) -> None:
        """Add a new trace step to the scratchpad."""
        self.steps.append(step)

    def get_messages(self) -> list[Message]:
        """Flatten the scratchpad into an ordered sequence of messages for the LLM."""
        messages: list[Message] = []
        if self.system_prompt:
            messages.append(self.system_prompt)
        if self.user_prompt:
            messages.append(self.user_prompt)

        for step in self.steps:
            messages.append(step.llm_message)
            messages.extend(step.observations)

        return messages

    @property
    def total_cost_usd(self) -> float:
        """Calculate the total accumulated USD cost of all steps in the episode."""
        total = 0.0
        for step in self.steps:
            if step.usage and "cost_usd" in step.usage:
                total += float(step.usage["cost_usd"])
        return total

    @property
    def total_tokens(self) -> int:
        """Calculate the total accumulated tokens used in all steps in the episode."""
        total = 0
        for step in self.steps:
            if step.usage and "total_tokens" in step.usage:
                total += int(step.usage["total_tokens"])
        return total

    def export_trace(self) -> dict[str, Any]:
        """Export the scratchpad to a JSON-serializable dictionary."""
        return self.model_dump(mode="json")
