"""Agent tool allowing similarity-based recall of historical market episodes."""

from collections.abc import Callable

from pydantic import BaseModel, Field

from autonomous_trading_analyst.memory.store import EpisodicMemory
from autonomous_trading_analyst.tools.registry import ToolRegistry


class RecallMemoryArgs(BaseModel):
    """Arguments for the recall_memory tool."""

    query: str = Field(
        description="Market context description or strategy pattern to recall.",
    )
    ticker: str | None = Field(
        default=None,
        description="Optional ticker symbol to restrict retrieval to a specific asset.",
    )
    top_k: int | None = Field(
        default=None,
        ge=1,
        le=20,
        description="Optional maximum number of relevant historical episodes to recall.",
    )


def build_recall_memory_tool(
    memory: EpisodicMemory,
    registry: ToolRegistry | None = None,
) -> Callable[..., str]:
    """Construct the recall_memory tool handler and optionally register it in a ToolRegistry."""

    def handle_recall_memory(
        query: str,
        ticker: str | None = None,
        top_k: int | None = None,
    ) -> str:
        """Recall similar past trading setups and outcomes from episodic memory."""
        episodes = memory.recall_similar(query=query, ticker=ticker, top_k=top_k)
        if not episodes:
            target = f" for ticker {ticker.upper()}" if ticker else ""
            return f"No historical memory episodes found matching query: '{query}'{target}."

        lines: list[str] = [
            f"Found {len(episodes)} historical episode(s) matching context query '{query}':"
        ]
        for idx, ep in enumerate(episodes, 1):
            outcome_text = (
                f"{ep.outcome_return:+.2%}"
                if ep.outcome_return is not None
                else "Pending / Unknown"
            )
            sim_text = f"{ep.similarity_score:.4f}" if ep.similarity_score is not None else "N/A"
            lines.append(
                f"\n[Episode {idx}] {ep.ticker} | Action: {ep.action} "
                f"| Realized Return: {outcome_text} | Similarity: {sim_text}\n"
                f"- Context: {ep.context_text}\n"
                f"- Rationale: {ep.rationale}\n"
                f"- Recorded At: {ep.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')}"
            )
        return "\n".join(lines)

    if registry is not None:
        registry.register(
            name="recall_memory",
            description=(
                "Recall past trading decisions and realized return outcomes "
                "for similar market conditions."
            ),
            handler=handle_recall_memory,
            args_schema=RecallMemoryArgs,
        )

    return handle_recall_memory


def register_recall_memory_tool(
    registry: ToolRegistry,
    memory: EpisodicMemory,
) -> ToolRegistry:
    """Register the recall_memory tool into an existing ToolRegistry and return the registry."""
    build_recall_memory_tool(memory, registry=registry)
    return registry
