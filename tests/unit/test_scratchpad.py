import pytest

from autonomous_trading_analyst.agent.trace import Scratchpad, TraceStep
from autonomous_trading_analyst.llm.messages import Message, Role


@pytest.mark.issue_10
def test_scratchpad_get_messages() -> None:
    """Test flattening the scratchpad into a message list."""
    system = Message(role=Role.SYSTEM, content="You are a helpful assistant.")
    scratchpad = Scratchpad(system_prompt=system)

    llm_msg = Message(role=Role.ASSISTANT, content="I will search now.")
    obs_msg = Message(role=Role.TOOL, content="Result: 42")

    step = TraceStep(llm_message=llm_msg, observations=[obs_msg])
    scratchpad.add_step(step)

    messages = scratchpad.get_messages()
    assert len(messages) == 3
    assert messages[0] == system
    assert messages[1] == llm_msg
    assert messages[2] == obs_msg


@pytest.mark.issue_10
def test_scratchpad_cost_and_tokens() -> None:
    """Test computation of total cost and tokens."""
    scratchpad = Scratchpad()

    step1 = TraceStep(
        llm_message=Message(role=Role.ASSISTANT, content="Step 1"),
        usage={"cost_usd": 0.5, "total_tokens": 100},
    )
    step2 = TraceStep(
        llm_message=Message(role=Role.ASSISTANT, content="Step 2"),
        usage={"cost_usd": 0.25, "total_tokens": 50},
    )
    step3 = TraceStep(llm_message=Message(role=Role.ASSISTANT, content="Step 3"), usage=None)

    scratchpad.add_step(step1)
    scratchpad.add_step(step2)
    scratchpad.add_step(step3)

    assert scratchpad.total_cost_usd == 0.75
    assert scratchpad.total_tokens == 150


@pytest.mark.issue_10
def test_scratchpad_export() -> None:
    """Test exporting the trace to a dictionary."""
    system = Message(role=Role.SYSTEM, content="Hello")
    scratchpad = Scratchpad(system_prompt=system)

    step = TraceStep(
        llm_message=Message(role=Role.ASSISTANT, content="Test"),
        usage={"cost_usd": 0.1, "total_tokens": 10},
    )
    scratchpad.add_step(step)

    exported = scratchpad.export_trace()
    assert isinstance(exported, dict)
    assert "system_prompt" in exported
    assert exported["system_prompt"] is not None
    assert exported["system_prompt"]["content"] == "Hello"
    assert len(exported["steps"]) == 1
    assert exported["steps"][0]["llm_message"]["content"] == "Test"
    assert exported["steps"][0]["usage"]["cost_usd"] == 0.1
