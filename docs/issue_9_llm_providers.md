# Issue 9: LLM Providers & Cost Tracking

**Branch**: `feature/issue-9-llm-providers`
**Status**: To Do
**PR**: opened by `make finish-issue` → `develop` (Closes #9)
**Milestone**: M2 - ReAct Agent Core

## Objective
Implement concrete `LLMClient` adapters for OpenAI, Anthropic, and Google Gemini that support function calling correctly. Add a factory to inject the right provider based on application settings, and integrate cost tracking to calculate USD cost per invocation using token usage and pricing tables.

## Acceptance Criteria
- [ ] `src/autonomous_trading_analyst/llm/pricing.py` contains pricing tables per model and calculates `cost_usd`.
- [ ] `src/autonomous_trading_analyst/llm/providers/openai_client.py` implements OpenAI client handling function calls.
- [ ] `src/autonomous_trading_analyst/llm/providers/anthropic_client.py` implements Anthropic client.
- [ ] `src/autonomous_trading_analyst/llm/providers/gemini_client.py` implements Gemini client.
- [ ] `src/autonomous_trading_analyst/llm/factory.py` implements `get_llm_client` utilizing `Settings`.
- [ ] The `generate()` methods must return the `Message` and an extended `usage` dict including `cost_usd`.
- [ ] Unit tests for cost calculation and factory in `tests/unit/test_llm_providers.py` (marked `@pytest.mark.issue_9`).
- [ ] `pyproject.toml` registers the `issue_9` marker.
- [ ] `make check` and `make test-issue ID=9` pass.

## Implementation Tasks

### 1. Preparation & Branching
```bash
make start-issue ID=9 NAME=llm-providers
```

### 2. Pricing & Cost Tracking
- **File**: `src/autonomous_trading_analyst/llm/pricing.py`
- **Change**: Define a constant dictionary mapping model names to their prompt/completion USD costs per 1M tokens. Create a function `calculate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float` that returns the USD float value.

### 3. Provider Implementations
- **Files**: `src/autonomous_trading_analyst/llm/providers/` (crear módulo).
- **Change**: 
  - `openai_client.py`, `anthropic_client.py`, `gemini_client.py`.
  - Implement `LLMClient` for each provider using sus respectivos SDKs (si aplica) o por HTTPX.
  - Mapear nuestra estructura `Message` normalizada a la estructura de la API nativa, y las respuestas de la API a nuestro `Message`.
  - Mapear las definiciones de Tools al formato de cada API (function calling).
  - Incluir la invocación a `calculate_cost` y meter `cost_usd` en el dict de uso que retorna.

### 4. Client Factory
- **File**: `src/autonomous_trading_analyst/llm/factory.py`
- **Change**: Implement `get_llm_client(settings) -> LLMClient` that initializes the right provider (`openai`, `anthropic`, `gemini`, o `fake`) based on the `settings.llm.provider` configuration. Debe usar las API keys de la configuración.

### 5. Package Interface
- **File**: `src/autonomous_trading_analyst/llm/__init__.py`
- **Change**: Re-export `get_llm_client` y la lógica de provider/factory.

### 6. Pytest Marker & Tests
- **File**: `tests/unit/test_llm_providers.py`
- **Change**: Test the cost calculator and factory logic. Mock the APIs so no real network requests are made.
- **File**: `pyproject.toml`
- **Change**: Add the `issue_9: LLM providers & cost tracking` marker.

### 7. Verification & Quality Gates
```bash
make test-issue ID=9
make check
```

### 8. Git & Issue Finish
```bash
make finish-issue ID=9 MSG="feat(llm): implement concrete llm providers and cost tracking"
```

## Decisions
- Maintain hardcoded pricing tables in `pricing.py` as they rarely change, but make it easy to update.
- Isolate provider-specific SDK logic in their respective files to prevent mixing dependencies and keeping `LLMClient` agnostic.
- The `factory` provides a seamless entry point for the ReAct agent without knowing the underlying model.
