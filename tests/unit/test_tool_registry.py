"""Unit tests for tool registry and built-in market tools."""

import json

import pytest
from pydantic import BaseModel, Field

from autonomous_trading_analyst.tools import (
    ToolRegistry,
    build_market_tools_registry,
)
from autonomous_trading_analyst.tools.market_data import FakeMarketDataProvider
from autonomous_trading_analyst.tools.research import FakeResearchClient


class SampleArgs(BaseModel):
    name: str = Field(description="Target name")
    multiplier: int = Field(default=2, description="Factor")


@pytest.mark.issue_7
def test_tool_registry_registration_and_schemas() -> None:
    """ToolRegistry accurately records definitions and exports LLM function schemas."""
    registry = ToolRegistry()

    def sample_func(name: str, multiplier: int = 2) -> str:
        return f"{name} * {multiplier}"

    registry.register(
        name="sample_tool",
        description="A sample tool for testing",
        handler=sample_func,
        args_schema=SampleArgs,
    )

    tools = registry.list_tools()
    assert len(tools) == 1
    assert tools[0].name == "sample_tool"
    assert "sample tool" in tools[0].description

    schemas = registry.get_function_schemas()
    assert len(schemas) == 1
    fn = schemas[0]["function"]
    assert fn["name"] == "sample_tool"
    assert "properties" in fn["parameters"]
    assert "name" in fn["parameters"]["properties"]


@pytest.mark.issue_7
def test_tool_registry_execution_and_resilience() -> None:
    """ToolRegistry safely executes tools, handles JSON strings, and captures errors."""
    registry = ToolRegistry()

    def greet(name: str, multiplier: int = 1) -> str:
        return f"Hello, {name}!" * multiplier

    registry.register("greet", "Greets person", greet, args_schema=SampleArgs)

    # 1. Success with dict
    res1 = registry.execute("greet", {"name": "Alice", "multiplier": 1})
    assert res1 == "Hello, Alice!"

    # 2. Success with stringified JSON
    res2 = registry.execute("greet", json.dumps({"name": "Bob", "multiplier": 1}))
    assert res2 == "Hello, Bob!"

    # 3. Nonexistent tool
    err1 = registry.execute("unknown_tool", {})
    assert "Error: Tool 'unknown_tool' not found" in err1

    # 4. Invalid JSON string
    err2 = registry.execute("greet", "{invalid_json")
    assert "Error: Arguments for tool 'greet' are not valid JSON" in err2

    # 5. Schema validation error
    err3 = registry.execute("greet", {"multiplier": 5})  # missing required 'name'
    assert "Error: Invalid arguments for tool 'greet'" in err3

    # 6. Handler exception is caught gracefully
    def fail_func() -> None:
        msg = "Fatal internal calculation failure"
        raise RuntimeError(msg)

    registry.register("failing_tool", "Fails always", fail_func)
    err4 = registry.execute("failing_tool", {})
    assert "Error executing tool 'failing_tool': RuntimeError" in err4


@pytest.mark.issue_7
def test_build_market_tools_registry_with_fakes() -> None:
    """build_market_tools_registry registers all M1 tools and executes with fake providers."""
    market_provider = FakeMarketDataProvider(default_price=150.0)
    market_provider.seed_latest_price("AAPL", 220.50)

    research_client = FakeResearchClient()

    registry = build_market_tools_registry(
        market_data_provider=market_provider,
        research_client=research_client,
    )

    tools = registry.list_tools()
    tool_names = {t.name for t in tools}
    expected = {
        "get_latest_price",
        "get_historical_bars",
        "get_technical_indicators",
        "get_market_anomalies",
        "get_financial_research",
    }
    assert expected.issubset(tool_names)

    # 1. Test get_latest_price
    price_obs = registry.execute("get_latest_price", {"ticker": "AAPL"})
    assert "220.5" in price_obs
    assert "AAPL" in price_obs

    # 2. Test get_historical_bars
    bars_obs = registry.execute("get_historical_bars", {"ticker": "AAPL", "days": 5})
    assert "close" in bars_obs

    # 3. Test get_technical_indicators
    indicators_obs = registry.execute(
        "get_technical_indicators", {"ticker": "AAPL", "lookback_days": 30}
    )
    assert "close_price" in indicators_obs

    # 4. Test get_market_anomalies
    anomalies_obs = registry.execute(
        "get_market_anomalies", {"ticker": "AAPL", "lookback_days": 30}
    )
    assert "is_anomaly" in anomalies_obs

    # 5. Test get_financial_research
    research_obs = registry.execute(
        "get_financial_research", {"ticker": "AAPL", "query": "Quarterly earnings"}
    )
    assert "sentiment" in research_obs
    assert "AAPL" in research_obs
