# Issue 7: Tool Registry & JSON Schemas

**Branch**: `feature/issue-7-tool-registry`
**Status**: Done
**PR**: opened by `make finish-issue` → `develop` (Closes #7)
**Milestone**: M1 - Foundations & Market Tools

## Objective
Implement a centralized `ToolRegistry` that generates LLM-compatible JSON schemas (for OpenAI, Anthropic, and Gemini function calling) and safely executes market data, technical indicators, anomaly detection, and research tools, completing Milestone 1.

## Acceptance Criteria
- [x] `src/autonomous_trading_analyst/tools/registry.py` implements `ToolDefinition` and `ToolRegistry` with automatic JSON schema generation and safe execution
- [x] `src/autonomous_trading_analyst/tools/builtins.py` implements standard market tools (price quote, historical bars, technical indicators, anomalies, research) and exposes `build_market_tools_registry`
- [x] `src/autonomous_trading_analyst/tools/__init__.py` re-exports registry classes and market tools factory
- [x] `tests/unit/test_tool_registry.py` covers tool registration, schema validity, execution with fake providers, and robust error handling (marked `@pytest.mark.issue_7`)
- [x] `pyproject.toml` registers the `issue_7` marker
- [x] `make check` and `make test-issue ID=7` pass

## Implementation Tasks

### 1. Preparation & Branching
```bash
make start-issue ID=7 NAME=tool-registry
```

### 2. Tool Registry Core & Schema Generation
- **File**: `src/autonomous_trading_analyst/tools/registry.py`
- **Change**: Define `ToolDefinition` model (name, description, parameters_schema) and `ToolRegistry` class. Provide registration decorators/methods that extract parameter types and docstrings to create standard JSON Schema function signatures. Implement safe `execute(name, arguments)` returning formatted string observations while capturing tool exceptions.

### 3. Built-in Market Tools & Factory
- **File**: `src/autonomous_trading_analyst/tools/builtins.py`
- **Change**: Implement callable tool wrappers for `get_latest_price`, `get_historical_bars`, `get_technical_indicators`, `get_market_anomalies`, and `get_financial_research`. Implement `build_market_tools_registry` factory allowing dependency injection of `MarketDataProvider` and `ResearchClient`.

### 4. Tools Package Interface
- **File**: `src/autonomous_trading_analyst/tools/__init__.py`
- **Change**: Re-export `ToolDefinition`, `ToolRegistry`, and `build_market_tools_registry`.

### 5. Tool Registry Unit Tests
- **File**: `tests/unit/test_tool_registry.py`
- **Change**: Test registration mechanics, JSON schema correctness for LLM function calling, safe error handling on missing tools or failing functions, and end-to-end execution of all 5 built-in tools against fake providers. Mark with `@pytest.mark.issue_7`.

### 6. Pytest Marker Registration
- **File**: `pyproject.toml`
- **Change**: Register the `issue_7` marker (`issue_7: Tool registry and JSON schemas`) under `[tool.pytest.ini_options]` `markers`.

### 7. Verification & Quality Gates
```bash
make test-issue ID=7
make check
```

### 8. Git & Issue Finish
```bash
make finish-issue ID=7 MSG="feat(tools): implement tool registry and JSON schema generation for M1 tools"
```

### 9. Milestone Finish
```bash
make finish-milestone MILESTONE=M1
```

## Decisions
- Generate JSON schemas for tool parameters using Pydantic argument models or typed function signatures to ensure direct compatibility with OpenAI, Anthropic, and Gemini function calling specs.
- Wrap tool execution in `ToolRegistry.execute` so any tool errors (e.g. data unavailable, timeout) return clear error strings rather than raising uncaught exceptions, allowing the ReAct agent to observe and recover gracefully.
- Provide dependency injection in `build_market_tools_registry` so providers can be swapped between live and fake implementations seamlessly.
