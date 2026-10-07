"""Unit tests for the ReAct loop and trading signal contract."""

import asyncio

import pytest
from pydantic import ValidationError

from autonomous_trading_analyst.agent.loop import ReActAgent
from autonomous_trading_analyst.agent.signal import SignalDecision, TradingSignal
from autonomous_trading_analyst.config import Settings
from autonomous_trading_analyst.llm.fake import FakeLLMClient
from autonomous_trading_analyst.llm.messages import Message, Role, ToolCall
from autonomous_trading_analyst.tools.registry import ToolRegistry


@pytest.mark.issue_11
def test_trading_signal_model_validation() -> None:
    """Test TradingSignal validation and uppercase ticker normalization."""
    signal = TradingSignal(
        ticker="aapl",
        decision=SignalDecision.BUY,
        confidence=0.85,
        rationale="Strong uptrend confirmed by 200 SMA breakout.",
    )
    assert signal.ticker == "AAPL"
    assert signal.decision == SignalDecision.BUY
    assert signal.confidence == 0.85

    with pytest.raises(ValidationError):
        TradingSignal(
            ticker="AAPL",
            decision=SignalDecision.BUY,
            confidence=1.5,  # Exceeds max 1.0
            rationale="Test",
        )

    with pytest.raises(ValidationError):
        TradingSignal(
            ticker="",  # Empty ticker
            decision=SignalDecision.BUY,
            confidence=0.5,
            rationale="Test",
        )


@pytest.mark.issue_11
def test_react_loop_successful_sequence() -> None:
    """Test standard successful ReAct loop: Thought -> Tool Call -> Thought -> submit_signal."""
    registry = ToolRegistry()
    registry.register(
        "get_latest_price",
        "Fetch latest price for ticker",
        lambda ticker: {"price": 182.50, "ticker": ticker},
    )

    responses = [
        Message(
            role=Role.ASSISTANT,
            content="Checking the latest price for AAPL.",
            tool_calls=[
                ToolCall(id="call_price", name="get_latest_price", arguments={"ticker": "AAPL"}),
            ],
        ),
        Message(
            role=Role.ASSISTANT,
            content="Price is $182.50, which looks bullish. Submitting BUY signal.",
            tool_calls=[
                ToolCall(
                    id="call_signal",
                    name="submit_signal",
                    arguments={
                        "ticker": "AAPL",
                        "decision": "BUY",
                        "confidence": 0.90,
                        "rationale": "Bullish momentum at current levels.",
                    },
                ),
            ],
        ),
    ]

    client = FakeLLMClient(responses=responses)
    settings = Settings(agent_max_steps=5, agent_max_cost_usd_per_decision=1.0)
    agent = ReActAgent(llm_client=client, tool_registry=registry, settings=settings)

    scratchpad = asyncio.run(agent.run("AAPL"))

    assert scratchpad.signal is not None
    assert scratchpad.signal.ticker == "AAPL"
    assert scratchpad.signal.decision == SignalDecision.BUY
    assert scratchpad.signal.confidence == 0.90
    assert "Bullish momentum" in scratchpad.signal.rationale

    assert len(scratchpad.steps) == 2
    # Verify Step 1: LLM tool call and observation
    assert scratchpad.steps[0].llm_message.tool_calls is not None
    assert scratchpad.steps[0].llm_message.tool_calls[0].name == "get_latest_price"
    assert len(scratchpad.steps[0].observations) == 1
    assert scratchpad.steps[0].observations[0].role == Role.TOOL
    assert "182.5" in (scratchpad.steps[0].observations[0].content or "")

    # Verify Step 2: Signal submission observation
    assert scratchpad.steps[1].llm_message.tool_calls is not None
    assert scratchpad.steps[1].llm_message.tool_calls[0].name == "submit_signal"
    assert len(scratchpad.steps[1].observations) == 1
    assert "submitted successfully" in (scratchpad.steps[1].observations[0].content or "")

    # Verify system prompt content
    assert scratchpad.system_prompt is not None
    assert "Autonomous Trading Analyst" in (scratchpad.system_prompt.content or "")
    assert "AAPL" in (scratchpad.system_prompt.content or "")
    assert "submit_signal" in (scratchpad.system_prompt.content or "")


@pytest.mark.issue_11
def test_react_loop_max_steps_budget_termination() -> None:
    """Test ReAct loop terminates when agent_max_steps is reached without a signal."""
    registry = ToolRegistry()
    registry.register("dummy_tool", "Dummy", lambda: "ok")

    responses = [
        Message(
            role=Role.ASSISTANT,
            content="Step 1 thinking...",
            tool_calls=[ToolCall(id="c1", name="dummy_tool", arguments={})],
        ),
        Message(
            role=Role.ASSISTANT,
            content="Step 2 thinking...",
            tool_calls=[ToolCall(id="c2", name="dummy_tool", arguments={})],
        ),
        Message(
            role=Role.ASSISTANT,
            content="Step 3 thinking...",
            tool_calls=[ToolCall(id="c3", name="dummy_tool", arguments={})],
        ),
    ]

    client = FakeLLMClient(responses=responses)
    settings = Settings(agent_max_steps=2, agent_max_cost_usd_per_decision=1.0)
    agent = ReActAgent(llm_client=client, tool_registry=registry, settings=settings)

    scratchpad = asyncio.run(agent.run("MSFT"))

    assert len(scratchpad.steps) == 2
    assert scratchpad.signal is None
    # 3rd response was not consumed because loop ended
    assert len(client.responses) == 1


@pytest.mark.issue_11
def test_react_loop_cost_budget_termination() -> None:
    """Test ReAct loop terminates early when total cost exceeds configured budget."""
    registry = ToolRegistry()
    registry.register("dummy_tool", "Dummy", lambda: "ok")

    responses = [
        Message(
            role=Role.ASSISTANT,
            content="Step 1 costing a lot...",
            tool_calls=[ToolCall(id="c1", name="dummy_tool", arguments={})],
        ),
        Message(
            role=Role.ASSISTANT,
            content="Step 2 which should never run...",
            tool_calls=[ToolCall(id="c2", name="dummy_tool", arguments={})],
        ),
    ]

    usages = [
        {"prompt_tokens": 500, "completion_tokens": 500, "total_tokens": 1000, "cost_usd": 0.08},
        {"prompt_tokens": 100, "completion_tokens": 100, "total_tokens": 200, "cost_usd": 0.01},
    ]

    client = FakeLLMClient(responses=responses, usages=usages)
    # Budget is 0.05 USD, Step 1 incurs 0.08 USD
    settings = Settings(agent_max_steps=5, agent_max_cost_usd_per_decision=0.05)
    agent = ReActAgent(llm_client=client, tool_registry=registry, settings=settings)

    scratchpad = asyncio.run(agent.run("NVDA"))

    assert len(scratchpad.steps) == 1
    assert scratchpad.total_cost_usd >= 0.05
    assert scratchpad.signal is None
    # Step 2 was never executed
    assert len(client.responses) == 1


@pytest.mark.issue_11
def test_react_loop_nudge_on_missing_tool_call() -> None:
    """Test that agent receives a nudge observation if LLM produces text with no tool call."""
    registry = ToolRegistry()
    responses = [
        Message(
            role=Role.ASSISTANT,
            content="I am just rambling without calling any tool.",
        ),
        Message(
            role=Role.ASSISTANT,
            content="Submitting HOLD now.",
            tool_calls=[
                ToolCall(
                    id="c_hold",
                    name="submit_signal",
                    arguments={
                        "ticker": "SPY",
                        "decision": "HOLD",
                        "confidence": 0.60,
                        "rationale": "Market uncertainty.",
                    },
                ),
            ],
        ),
    ]

    client = FakeLLMClient(responses=responses)
    settings = Settings(agent_max_steps=4, agent_max_cost_usd_per_decision=1.0)
    agent = ReActAgent(llm_client=client, tool_registry=registry, settings=settings)

    scratchpad = agent.run_sync("SPY")

    assert len(scratchpad.steps) == 2
    assert scratchpad.signal is not None
    assert scratchpad.signal.decision == SignalDecision.HOLD

    # Check Step 1 observations contained the nudge
    nudge_obs = scratchpad.steps[0].observations[0]
    assert nudge_obs.content is not None
    assert "No tool call was requested" in nudge_obs.content


@pytest.mark.issue_11
def test_react_loop_tool_error_recovery() -> None:
    """Test that uncaught tool exceptions are captured as observations so LLM can recover."""
    registry = ToolRegistry()

    def buggy_tool() -> None:
        msg = "Remote server timeout connecting to data feed"
        raise ConnectionError(msg)

    registry.register("buggy_tool", "Tool that fails", buggy_tool)

    responses = [
        Message(
            role=Role.ASSISTANT,
            content="Calling buggy tool.",
            tool_calls=[ToolCall(id="c_err", name="buggy_tool", arguments={})],
        ),
        Message(
            role=Role.ASSISTANT,
            content="Observed error. Submitting safe HOLD signal.",
            tool_calls=[
                ToolCall(
                    id="c_hold",
                    name="submit_signal",
                    arguments={
                        "ticker": "AAPL",
                        "decision": "HOLD",
                        "confidence": 0.50,
                        "rationale": "Could not fetch data due to timeout.",
                    },
                ),
            ],
        ),
    ]

    client = FakeLLMClient(responses=responses)
    settings = Settings(agent_max_steps=5, agent_max_cost_usd_per_decision=1.0)
    agent = ReActAgent(llm_client=client, tool_registry=registry, settings=settings)

    scratchpad = agent.run_sync("AAPL")

    assert len(scratchpad.steps) == 2
    assert scratchpad.signal is not None
    assert scratchpad.signal.decision == SignalDecision.HOLD

    # Observation in step 0 captures the exception cleanly
    err_obs = scratchpad.steps[0].observations[0]
    assert err_obs.role == Role.TOOL
    assert err_obs.content is not None
    assert "ConnectionError" in err_obs.content
    assert "Remote server timeout" in err_obs.content
