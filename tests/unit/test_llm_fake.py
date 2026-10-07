import asyncio

import pytest

from autonomous_trading_analyst.llm import FakeLLMClient, Message, Role, ToolCall


@pytest.mark.issue_8
def test_fake_llm_client_responses():
    """Test that the fake client returns responses sequentially."""
    msg1 = Message(role=Role.ASSISTANT, content="First response")
    msg2 = Message(role=Role.ASSISTANT, content="Second response")

    client = FakeLLMClient(responses=[msg1, msg2])

    input_msgs = [Message(role=Role.USER, content="Hello")]

    res1, usage1 = asyncio.run(client.generate(messages=input_msgs))
    assert res1.content == "First response"
    assert usage1["total_tokens"] == 30

    res2, _usage2 = asyncio.run(client.generate(messages=input_msgs))
    assert res2.content == "Second response"

    # Check history
    assert len(client.received_messages) == 2
    assert client.received_messages[0] == input_msgs


@pytest.mark.issue_8
def test_fake_llm_client_exhaustion():
    """Test that the fake client raises RuntimeError when out of responses."""
    client = FakeLLMClient(responses=[Message(role=Role.ASSISTANT, content="Only response")])

    asyncio.run(client.generate(messages=[Message(role=Role.USER, content="Hi")]))

    with pytest.raises(RuntimeError, match="No more mock responses available"):
        asyncio.run(client.generate(messages=[Message(role=Role.USER, content="Again")]))


@pytest.mark.issue_8
def test_fake_llm_client_tool_calls():
    """Test fake client returning a tool call message."""
    tool_call_msg = Message(
        role=Role.ASSISTANT,
        tool_calls=[ToolCall(id="call_123", name="get_latest_price", arguments={"symbol": "AAPL"})],
    )

    client = FakeLLMClient(responses=[tool_call_msg])

    res, _ = asyncio.run(client.generate(messages=[Message(role=Role.USER, content="Price AAPL?")]))

    assert res.role == Role.ASSISTANT
    assert res.tool_calls is not None
    assert len(res.tool_calls) == 1
    assert res.tool_calls[0].name == "get_latest_price"
    assert res.tool_calls[0].arguments == {"symbol": "AAPL"}
