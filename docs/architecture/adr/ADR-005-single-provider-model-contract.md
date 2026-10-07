# ADR-005: Single-Provider Model Contract for v2.0

## Status

Accepted

## Context

The `docs/architecture/MODEL_ABSTRACTION.md` document describes a multi-provider `BaseLLM` abstraction with `GeminiLLM`, `OpenAILLM`, `AnthropicLLM`, and `OllamaLLM` adapter implementations, a factory pattern, and a provider-agnostic configuration layer. This is valuable future work for cross-model benchmark comparison (`v2.1`), but for v2.0 Local Hosted Alpha the system uses Google ADK's `LlmAgent` with a single configurable model name.

Current implementation:
- `agents/src/agents/config.py`: `MODEL_NAME = os.getenv("MODEL_NAME", "gemini-3.0-flash")`
- `GOOGLE_API_KEY` is the sole credential required
- Agents are instantiated via `google.adk.agents.LlmAgent` with `model=MODEL_NAME`
- `agents/src/agents/utils/adk_runtime.py` uses `InMemoryRunner` for execution
- No `BaseLLM` interface, no factory, no provider switching exists in code

Building a full provider abstraction layer before validating the evaluation methodology through local alpha usage would be premature optimization.

## Decision

v2.0 ships with Gemini as the sole LLM provider. The agent layer uses Google ADK directly. `MODEL_NAME` is configurable for model variant switching (e.g., `gemini-3.0-flash` vs `gemini-3.0-pro`) but not for cross-provider switching. `MODEL_ABSTRACTION.md` remains as a Planned roadmap document for `v2.1`.

The v2.0 model contract is:
1. `MODEL_NAME` env var defaults to `gemini-3.0-flash`
2. `GOOGLE_API_KEY` is the sole LLM credential
3. No `MODEL_PROVIDER` configuration exists
4. Agents use `google.adk.agents.LlmAgent` directly
5. `InMemoryRunner` provides the execution runtime

Contract tests in `tests/scenarios/test_model_memory_contract.py` enforce these constraints.

## Consequences

**Positive:**
- Reduces v2.0 scope to focus on operator workflow validation
- Prevents premature abstraction before evaluation methodology is proven through use
- Contract tests catch accidental drift toward multi-provider code

**Negative:**
- Cannot compare model behavior across providers until `v2.1`
- `MODEL_ABSTRACTION.md` remains aspirational

## References

- `docs/architecture/MODEL_ABSTRACTION.md` (Doc Status: Planned)
- `agents/src/agents/config.py`
- `agents/src/agents/utils/adk_runtime.py`
- `tests/scenarios/test_model_memory_contract.py`
