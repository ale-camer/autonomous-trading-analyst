# Issue 11: ReAct Loop & Signal Contract

**Branch**: `feature/issue-11-react-loop`
**Status**: To Do
**PR**: opened by `make finish-issue` → `develop` (Closes #11)
**Milestone**: M2 - ReAct Agent Core

## Objective
Implement the explicit ReAct (Reasoning and Acting) orchestration loop. The agent must continuously reason (Thought), call market tools (Action), and read their results (Observation) until it reaches a conclusion. It must gracefully handle errors, respect configured step and cost budgets, and terminate its episode by invoking a special `submit_signal` tool.

## Acceptance Criteria
- [x] `src/autonomous_trading_analyst/agent/signal.py` defines the `TradingSignal` Pydantic model (decision: BUY/SELL/HOLD, confidence, rationale).
- [x] `src/autonomous_trading_analyst/agent/loop.py` implements the `ReActAgent` orchestration cycle.
- [x] The agent builds a strict `system_prompt` outlining its persona, tools, budgets, and the requirement to use `submit_signal`.
- [x] The loop enforces `agent_max_steps` and `agent_max_cost_usd_per_decision` from `Settings`.
- [x] `tests/unit/test_react_loop.py` mocks the `LLMClient` to simulate a successful loop, a step-budget termination, and a cost-budget termination (marked `@pytest.mark.issue_11`).
- [x] `pyproject.toml` registers the `issue_11` marker.
- [x] `make check` and `make test-issue ID=11` pass.

## Implementation Tasks

### 1. Preparation & Branching
```bash
make start-issue ID=11 NAME=react-loop
```

### 2. Signal Contract
- **File**: `src/autonomous_trading_analyst/agent/signal.py`
- **Change**: Define `SignalDecision(StrEnum)` with values `BUY`, `SELL`, `HOLD`. Define `TradingSignal(BaseModel)` containing `ticker` (str), `decision` (SignalDecision), `confidence` (float from 0.0 to 1.0), and `rationale` (str).

### 3. ReAct Loop Core
- **File**: `src/autonomous_trading_analyst/agent/loop.py`
- **Change**: Implement `ReActAgent`.
  - `__init__(self, llm_client, tool_registry, settings)`
  - Dynamically inject a `submit_signal` tool definition into the list of tools passed to the LLM (its JSON schema should match `TradingSignal`).
  - `run(ticker: str) -> Scratchpad:`
    - Create a `Scratchpad` and set the initial system prompt.
    - Loop up to `settings.agent_max_steps`. Stop early if `scratchpad.total_cost_usd >= settings.agent_max_cost_usd_per_decision`.
    - Call `LLMClient.generate(messages, tools)`. Add the `TraceStep` to the `Scratchpad`.
    - Process tool calls:
      - If `submit_signal` is called: parse the arguments, record the final state, and `break` the loop to return the trace.
      - If a market tool is called: `execute` it via `ToolRegistry`. Record the result (or the captured error string) as a `Role.TOOL` observation so the LLM can see it and recover.
    - If no tool is requested and no signal is submitted, automatically append a system observation nudging the LLM to either use a tool or call `submit_signal` to prevent it from stalling.

### 4. Agent Package Interface
- **File**: `src/autonomous_trading_analyst/agent/__init__.py`
- **Change**: Re-export `ReActAgent`, `TradingSignal`, and `SignalDecision`.

### 5. Unit Tests
- **File**: `tests/unit/test_react_loop.py`
- **Change**: Use `FakeLLMClient` with a scripted sequence of `Message`s to test:
  1. A successful sequence: Thought -> Market Tool Call -> Thought -> `submit_signal`.
  2. A budget termination: Agent hits `max_steps` before submitting a signal.
  3. A cost termination: Agent hits `max_cost_usd` limit.
  Mark tests with `@pytest.mark.issue_11`.

### 6. Pytest Marker Registration
- **File**: `pyproject.toml`
- **Change**: Add the `issue_11: ReAct loop & signal contract` marker under `[tool.pytest.ini_options]` `markers`.

### 7. Verification & Quality Gates
```bash
make test-issue ID=11
make check
```

### 8. Git & Issue Finish
```bash
make finish-issue ID=11 MSG="feat(agent): implement react loop and signal contract"
```

## Decisions
- Injecting `submit_signal` as a "tool" rather than asking the LLM to output pure JSON at the end gives the ReAct loop a deterministic structural endpoint. When the LLM decides it has enough context, it fires the tool, allowing the loop to easily intercept the final verdict.
- Any uncaught exception from a tool must be mapped to a string and fed back as a `TOOL` message. This makes the agent extremely robust; it will read the error and try a different parameter or tool on the next turn.
