# Issue 8: LLM Client Abstraction & Fake

**Branch**: `feature/issue-8-llm-client`
**Status**: To Do
**PR**: opened by `make finish-issue` → `develop` (Closes #8)
**Milestone**: M2 - ReAct Agent Core

## Objective
Provide a provider-agnostic `LLMClient` interface with normalized messages, tool definitions, tool calls, and token usage tracking. Implement a `FakeLLMClient` that accepts scripted responses to enable deterministic, fast, and cost-free unit testing for the agent core.

## Acceptance Criteria
- [ ] `src/autonomous_trading_analyst/llm/messages.py` implements Pydantic models for roles, messages, and tool calls.
- [ ] `src/autonomous_trading_analyst/llm/client.py` defines the abstract `LLMClient` protocol/interface returning normalized messages and token metrics.
- [ ] `src/autonomous_trading_analyst/llm/fake.py` implements `FakeLLMClient` capable of sequential mock responses and erroring out when exhausted.
- [ ] `src/autonomous_trading_analyst/llm/__init__.py` re-exports the client and models.
- [ ] `tests/unit/test_llm_fake.py` covers message structuring, sequential responses, and depletion errors (marked `@pytest.mark.issue_8`).
- [ ] `pyproject.toml` registers the `issue_8` marker.
- [ ] `make check` and `make test-issue ID=8` pass.

## Implementation Tasks

### 1. Preparation & Branching
```bash
make start-issue ID=8 NAME=llm-client
```

### 2. Message Models
- **File**: `src/autonomous_trading_analyst/llm/messages.py`
- **Change**: Define `Role` (system, user, assistant, tool), `ToolCall`, and `Message` models using Pydantic for strict typing and validation across all providers.

### 3. LLM Client Abstraction
- **File**: `src/autonomous_trading_analyst/llm/client.py`
- **Change**: Define `LLMClient` protocol with an async `generate` (or `chat`) method. It takes a list of `Message`s and an optional list of `ToolDefinition` dicts/schemas, returning a tuple of `(Message, dict)` for response and token usage.

### 4. Fake LLM Client
- **File**: `src/autonomous_trading_analyst/llm/fake.py`
- **Change**: Implement `FakeLLMClient(LLMClient)` initialized with a list of mock responses. On each call, pop and return the next message. Raise `RuntimeError` if responses are exhausted. Record inputs in `self.received_messages` for later test assertions.

### 5. LLM Package Interface
- **File**: `src/autonomous_trading_analyst/llm/__init__.py`
- **Change**: Re-export models, `LLMClient`, and `FakeLLMClient`.

### 6. Fake LLM Unit Tests
- **File**: `tests/unit/test_llm_fake.py`
- **Change**: Test sequential delivery of mock messages, exhaustion error, and history tracking. Mark with `@pytest.mark.issue_8`.

### 7. Pytest Marker Registration
- **File**: `pyproject.toml`
- **Change**: Register the `issue_8` marker (`issue_8: LLM client abstraction & fake`) under `[tool.pytest.ini_options]` `markers`.

### 8. Verification & Quality Gates
```bash
make test-issue ID=8
make check
```

### 9. Git & Issue Finish
```bash
make finish-issue ID=8 MSG="feat(llm): implement llm client abstraction and fake client"
```

## Decisions
- Model schemas explicitly with Pydantic for provider translation later on (OpenAI vs Anthropic format mappings).
- Maintain a fake client with a deterministic queue of responses to make the ReAct agent's loop testing entirely predictable and independent of external API latencies or costs.
- Track received messages internally in `FakeLLMClient` to let tests assert what context the agent sent.
