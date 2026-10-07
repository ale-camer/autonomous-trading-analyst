# Issue 10: Scratchpad & Trace Recorder

**Branch**: `feature/issue-10-scratchpad`
**Status**: To Do
**PR**: opened by `make finish-issue` → `develop` (Closes #10)
**Milestone**: M2 - ReAct Agent Core

## Objective
Implement a per-episode `Scratchpad` (short-term memory) to record LLM thoughts, tool calls, and tool observations with stable IDs, tracking tokens and accumulated cost. The scratchpad must be exportable as a complete decision trace for persistence, observability, and episodic memory.

## Acceptance Criteria
- [ ] `src/autonomous_trading_analyst/agent/trace.py` implements Pydantic models for `TraceStep` and `Scratchpad` (DecisionTrace).
- [ ] The scratchpad exposes a method to reconstruct the ordered list of conversation `Message` objects suitable for sending to the `LLMClient`.
- [ ] The scratchpad correctly accumulates tokens and USD cost across all steps in the current episode.
- [ ] The scratchpad can export the entire trace to a JSON-serializable dictionary.
- [ ] `src/autonomous_trading_analyst/agent/__init__.py` re-exports the new classes.
- [ ] `tests/unit/test_scratchpad.py` covers message appending, cost accumulation, context rebuilding, and trace exporting (marked `@pytest.mark.issue_10`).
- [ ] `pyproject.toml` registers the `issue_10` marker.
- [ ] `make check` and `make test-issue ID=10` pass.

## Implementation Tasks

### 1. Preparation & Branching
```bash
make start-issue ID=10 NAME=scratchpad
```

### 2. Trace Models & Scratchpad
- **File**: `src/autonomous_trading_analyst/agent/trace.py`
- **Change**: 
  - Create `TraceStep` model containing: the LLM `Message` (thoughts/tool calls), an optional dictionary of usage metrics (tokens, cost), and a list of observation `Message`s (tool results) resulting from that step.
  - Create the `Scratchpad` class holding the system prompt `Message` and a list of `TraceStep`s.
  - Expose `add_step(step: TraceStep)` and `get_messages() -> list[Message]` (which flattens the system prompt, LLM steps, and observations into the strict list of `Message`s required by the LLM).
  - Add properties for `total_cost_usd` and `total_tokens`.
  - Add an `export_trace() -> dict` method.

### 3. Agent Package Interface
- **File**: `src/autonomous_trading_analyst/agent/__init__.py`
- **Change**: Create the package and re-export `Scratchpad` and `TraceStep`.

### 4. Unit Tests
- **File**: `tests/unit/test_scratchpad.py`
- **Change**: Write tests to ensure that `get_messages()` correctly flattens the trace into a sequence of `Message` objects in the correct order. Test the accumulation of costs and the JSON export structure. Mark with `@pytest.mark.issue_10`.

### 5. Pytest Marker Registration
- **File**: `pyproject.toml`
- **Change**: Add the `issue_10: Scratchpad & trace recorder` marker under `[tool.pytest.ini_options]` `markers`.

### 6. Verification & Quality Gates
```bash
make test-issue ID=10
make check
```

### 7. Git & Issue Finish
```bash
make finish-issue ID=10 MSG="feat(agent): implement scratchpad and decision trace recorder"
```

## Decisions
- Store trace data in a rich structure (`TraceStep`) rather than just a flat list of `Message`s. This allows us to cleanly associate the LLM's decision, the cost of that specific decision, and the subsequent tool results together as a single logical step.
- `get_messages()` dynamically rebuilds the flat message list required by the LLM on every turn to ensure the LLM interface remains clean and decoupled from our internal tracing structure.
