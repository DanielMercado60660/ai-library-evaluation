## Doc Header
- Doc Status: Planned
- Owner: AI Librarian Team
- Last Verified: 2026-02-08
- Scope: Model abstraction reference
- Source of Truth: docs/status/PROJECT_STATUS.md
- Supersedes: N/A
- Related Workstream: adk-agents

> Last verified against code/docs on 2026-02-08. This reference may include implemented and planned content; use Doc Status for interpretation.

# Model Abstraction Layer

This document describes the LLM provider abstraction that enables testing with different models.

## Design Goals

1. **Swap models easily** — Change from Gemini to GPT-4 with one config change
2. **Compare behavior** — Run same scenarios with different models
3. **Future-proof** — Add new providers without touching agent code
4. **Consistent interface** — Agents don't care which model they're using

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         AGENT LAYER                              │
│                                                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐            │
│  │ Front Desk  │  │   Catalog   │  │     ILL     │            │
│  │    Agent    │  │    Agent    │  │    Agent    │            │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘            │
│         │                │                │                     │
│         └────────────────┼────────────────┘                     │
│                          │                                      │
│                          ▼                                      │
│               ┌─────────────────────┐                          │
│               │      BaseLLM        │  ← Abstract interface     │
│               │    (interface)      │                          │
│               └──────────┬──────────┘                          │
│                          │                                      │
└──────────────────────────┼──────────────────────────────────────┘
                           │
┌──────────────────────────┼──────────────────────────────────────┐
│                          │     PROVIDER LAYER                    │
│                          │                                      │
│    ┌─────────────────────┼─────────────────────┐               │
│    │                     │                     │               │
│    ▼                     ▼                     ▼               │
│ ┌──────────┐      ┌──────────┐         ┌──────────┐          │
│ │ GeminiLLM│      │ OpenAILLM│         │  Local   │          │
│ │          │      │          │         │   LLM    │          │
│ └────┬─────┘      └────┬─────┘         └────┬─────┘          │
│      │                 │                     │                │
│      ▼                 ▼                     ▼                │
│  ┌────────┐       ┌────────┐          ┌────────┐            │
│  │ Gemini │       │ OpenAI │          │ Ollama │            │
│  │  API   │       │  API   │          │  API   │            │
│  └────────┘       └────────┘          └────────┘            │
│                                                               │
└───────────────────────────────────────────────────────────────┘
```

---

## Base Interface

```python
# core/llm/base.py

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import AsyncIterator


@dataclass
class ToolCall:
    """A tool/function call from the model."""
    
    id: str                  # Unique ID for this call
    name: str                # Tool name
    arguments: dict          # Parsed arguments


@dataclass  
class LLMResponse:
    """Response from an LLM."""
    
    text: str | None                  # Text response (if any)
    tool_calls: list[ToolCall]        # Tool calls (if any)
    finish_reason: str                # "stop", "tool_calls", "length", etc.
    
    # Usage tracking
    tokens_in: int | None
    tokens_out: int | None
    
    # For debugging
    raw_response: dict | None = None


class BaseLLM(ABC):
    """Abstract interface for LLM providers."""
    
    provider: str            # "gemini", "openai", "anthropic", "local"
    model: str               # Model identifier
    
    @abstractmethod
    async def generate(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        system_prompt: str | None = None,
        temperature: float = 0.3,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        """
        Generate a response.
        
        Args:
            messages: Conversation history [{role: "user"|"assistant"|"tool", content: ...}]
            tools: Tool definitions in OpenAI format
            system_prompt: System instructions
            temperature: Sampling temperature
            max_tokens: Max response length
            
        Returns:
            LLMResponse with text and/or tool calls
        """
        ...
    
    @abstractmethod
    async def generate_stream(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        system_prompt: str | None = None,
        temperature: float = 0.3,
        max_tokens: int | None = None,
    ) -> AsyncIterator[LLMResponse]:
        """Stream response chunks."""
        ...
    
    def count_tokens(self, text: str) -> int:
        """Estimate token count. Override for accurate counting."""
        # Rough estimate: ~4 chars per token
        return len(text) // 4
```

---

## Provider Implementations

### Gemini

```python
# core/llm/gemini.py

from google import genai
from google.genai import types
from core.llm.base import BaseLLM, LLMResponse, ToolCall


class GeminiLLM(BaseLLM):
    """Google Gemini implementation."""
    
    provider = "gemini"
    
    def __init__(
        self,
        api_key: str,
        model: str = "gemini-3.0-flash",
    ):
        self.client = genai.Client(api_key=api_key)
        self.model = model
    
    async def generate(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        system_prompt: str | None = None,
        temperature: float = 0.3,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        # Convert messages to Gemini format
        contents = self._convert_messages(messages)
        
        # Build config
        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=temperature,
            max_output_tokens=max_tokens,
        )
        
        # Add tools if provided
        if tools:
            config.tools = self._convert_tools(tools)
        
        # Generate
        response = self.client.models.generate_content(
            model=self.model,
            contents=contents,
            config=config,
        )
        
        return self._parse_response(response)
    
    def _convert_messages(self, messages: list[dict]) -> list[types.Content]:
        """Convert from OpenAI format to Gemini format."""
        
        contents = []
        
        for msg in messages:
            role = msg["role"]
            
            if role == "user":
                contents.append(types.Content(
                    role="user",
                    parts=[types.Part(text=msg["content"])],
                ))
            
            elif role == "assistant":
                parts = []
                
                if msg.get("content"):
                    parts.append(types.Part(text=msg["content"]))
                
                if msg.get("tool_calls"):
                    for tc in msg["tool_calls"]:
                        parts.append(types.Part(
                            function_call=types.FunctionCall(
                                name=tc["name"],
                                args=tc["arguments"],
                            )
                        ))
                
                contents.append(types.Content(role="model", parts=parts))
            
            elif role == "tool":
                contents.append(types.Content(
                    role="user",
                    parts=[types.Part(
                        function_response=types.FunctionResponse(
                            name=msg["name"],
                            response={"result": msg["content"]},
                        )
                    )],
                ))
        
        return contents
    
    def _convert_tools(self, tools: list[dict]) -> list[types.Tool]:
        """Convert from OpenAI tool format to Gemini format."""
        
        function_declarations = []
        
        for tool in tools:
            func = tool.get("function", tool)
            
            function_declarations.append(types.FunctionDeclaration(
                name=func["name"],
                description=func.get("description", ""),
                parameters=func.get("parameters", {}),
            ))
        
        return [types.Tool(function_declarations=function_declarations)]
    
    def _parse_response(self, response) -> LLMResponse:
        """Parse Gemini response to LLMResponse."""
        
        candidate = response.candidates[0]
        
        text = None
        tool_calls = []
        
        for part in candidate.content.parts:
            if part.text:
                text = (text or "") + part.text
            
            if part.function_call:
                fc = part.function_call
                tool_calls.append(ToolCall(
                    id=f"call_{len(tool_calls)}",
                    name=fc.name,
                    arguments=dict(fc.args),
                ))
        
        # Determine finish reason
        if tool_calls:
            finish_reason = "tool_calls"
        else:
            finish_reason = "stop"
        
        return LLMResponse(
            text=text,
            tool_calls=tool_calls,
            finish_reason=finish_reason,
            tokens_in=response.usage_metadata.prompt_token_count if response.usage_metadata else None,
            tokens_out=response.usage_metadata.candidates_token_count if response.usage_metadata else None,
            raw_response=response,
        )
```

### OpenAI (Future)

```python
# core/llm/openai.py

import openai
from core.llm.base import BaseLLM, LLMResponse, ToolCall


class OpenAILLM(BaseLLM):
    """OpenAI GPT implementation."""
    
    provider = "openai"
    
    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o",
    ):
        self.client = openai.AsyncOpenAI(api_key=api_key)
        self.model = model
    
    async def generate(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        system_prompt: str | None = None,
        temperature: float = 0.3,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        # Build messages list
        api_messages = []
        
        if system_prompt:
            api_messages.append({"role": "system", "content": system_prompt})
        
        api_messages.extend(messages)
        
        # Build request
        kwargs = {
            "model": self.model,
            "messages": api_messages,
            "temperature": temperature,
        }
        
        if max_tokens:
            kwargs["max_tokens"] = max_tokens
        
        if tools:
            kwargs["tools"] = [{"type": "function", "function": t} for t in tools]
        
        # Call API
        response = await self.client.chat.completions.create(**kwargs)
        
        return self._parse_response(response)
    
    def _parse_response(self, response) -> LLMResponse:
        """Parse OpenAI response."""
        
        choice = response.choices[0]
        message = choice.message
        
        tool_calls = []
        if message.tool_calls:
            for tc in message.tool_calls:
                tool_calls.append(ToolCall(
                    id=tc.id,
                    name=tc.function.name,
                    arguments=json.loads(tc.function.arguments),
                ))
        
        return LLMResponse(
            text=message.content,
            tool_calls=tool_calls,
            finish_reason=choice.finish_reason,
            tokens_in=response.usage.prompt_tokens,
            tokens_out=response.usage.completion_tokens,
            raw_response=response,
        )
```

### Anthropic (Future)

```python
# core/llm/anthropic.py

import anthropic
from core.llm.base import BaseLLM, LLMResponse, ToolCall


class AnthropicLLM(BaseLLM):
    """Anthropic Claude implementation."""
    
    provider = "anthropic"
    
    def __init__(
        self,
        api_key: str,
        model: str = "claude-sonnet-4-20250514",
    ):
        self.client = anthropic.AsyncAnthropic(api_key=api_key)
        self.model = model
    
    async def generate(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        system_prompt: str | None = None,
        temperature: float = 0.3,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        # Convert messages to Anthropic format
        api_messages = self._convert_messages(messages)
        
        # Build request
        kwargs = {
            "model": self.model,
            "messages": api_messages,
            "max_tokens": max_tokens or 4096,
            "temperature": temperature,
        }
        
        if system_prompt:
            kwargs["system"] = system_prompt
        
        if tools:
            kwargs["tools"] = self._convert_tools(tools)
        
        # Call API
        response = await self.client.messages.create(**kwargs)
        
        return self._parse_response(response)
    
    def _convert_tools(self, tools: list[dict]) -> list[dict]:
        """Convert to Anthropic tool format."""
        
        return [
            {
                "name": t["name"],
                "description": t.get("description", ""),
                "input_schema": t.get("parameters", {"type": "object", "properties": {}}),
            }
            for t in tools
        ]
    
    def _parse_response(self, response) -> LLMResponse:
        """Parse Anthropic response."""
        
        text = None
        tool_calls = []
        
        for block in response.content:
            if block.type == "text":
                text = (text or "") + block.text
            elif block.type == "tool_use":
                tool_calls.append(ToolCall(
                    id=block.id,
                    name=block.name,
                    arguments=block.input,
                ))
        
        return LLMResponse(
            text=text,
            tool_calls=tool_calls,
            finish_reason=response.stop_reason,
            tokens_in=response.usage.input_tokens,
            tokens_out=response.usage.output_tokens,
            raw_response=response,
        )
```

### Local Models (Ollama)

```python
# core/llm/local.py

import httpx
from core.llm.base import BaseLLM, LLMResponse, ToolCall


class OllamaLLM(BaseLLM):
    """Local model via Ollama."""
    
    provider = "local"
    
    def __init__(
        self,
        model: str = "llama3.1:8b",
        base_url: str = "http://localhost:11434",
    ):
        self.model = model
        self.base_url = base_url
    
    async def generate(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        system_prompt: str | None = None,
        temperature: float = 0.3,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        # Build messages
        api_messages = []
        
        if system_prompt:
            api_messages.append({"role": "system", "content": system_prompt})
        
        api_messages.extend(messages)
        
        # Build request
        payload = {
            "model": self.model,
            "messages": api_messages,
            "stream": False,
            "options": {
                "temperature": temperature,
            },
        }
        
        if max_tokens:
            payload["options"]["num_predict"] = max_tokens
        
        if tools:
            payload["tools"] = tools
        
        # Call Ollama
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/chat",
                json=payload,
                timeout=120.0,
            )
            response.raise_for_status()
            data = response.json()
        
        return self._parse_response(data)
    
    def _parse_response(self, data: dict) -> LLMResponse:
        """Parse Ollama response."""
        
        message = data["message"]
        
        tool_calls = []
        if message.get("tool_calls"):
            for i, tc in enumerate(message["tool_calls"]):
                tool_calls.append(ToolCall(
                    id=f"call_{i}",
                    name=tc["function"]["name"],
                    arguments=tc["function"]["arguments"],
                ))
        
        return LLMResponse(
            text=message.get("content"),
            tool_calls=tool_calls,
            finish_reason="stop" if not tool_calls else "tool_calls",
            tokens_in=data.get("prompt_eval_count"),
            tokens_out=data.get("eval_count"),
            raw_response=data,
        )
```

---

## Factory

```python
# core/llm/factory.py

from core.llm.base import BaseLLM


def create_llm(provider: str, **kwargs) -> BaseLLM:
    """
    Create an LLM instance.
    
    Args:
        provider: "gemini", "openai", "anthropic", "local"
        **kwargs: Provider-specific arguments
        
    Returns:
        Configured LLM instance
    """
    
    match provider:
        case "gemini":
            from core.llm.gemini import GeminiLLM
            return GeminiLLM(**kwargs)
        
        case "openai":
            from core.llm.openai import OpenAILLM
            return OpenAILLM(**kwargs)
        
        case "anthropic":
            from core.llm.anthropic import AnthropicLLM
            return AnthropicLLM(**kwargs)
        
        case "local":
            from core.llm.local import OllamaLLM
            return OllamaLLM(**kwargs)
        
        case _:
            raise ValueError(f"Unknown provider: {provider}")


def create_llm_from_config(config: dict) -> BaseLLM:
    """Create LLM from config dict."""
    
    provider = config.pop("provider")
    return create_llm(provider, **config)
```

---

## Configuration

### Environment Variables

```bash
# .env

# Gemini (default)
GOOGLE_API_KEY=your-api-key
MODEL_PROVIDER=gemini
MODEL_NAME=gemini-3.0-flash

# OpenAI (alternative)
# OPENAI_API_KEY=your-api-key
# MODEL_PROVIDER=openai
# MODEL_NAME=gpt-4o

# Anthropic (alternative)
# ANTHROPIC_API_KEY=your-api-key
# MODEL_PROVIDER=anthropic
# MODEL_NAME=claude-sonnet-4-20250514

# Local (alternative)
# MODEL_PROVIDER=local
# MODEL_NAME=llama3.1:8b
# OLLAMA_BASE_URL=http://localhost:11434
```

### Config File

```yaml
# config/llm.yaml

# Default configuration
default:
  provider: gemini
  model: gemini-3.0-flash
  temperature: 0.3

# Model-specific configs for comparison testing
models:
  gemini-flash:
    provider: gemini
    model: gemini-3.0-flash
    temperature: 0.3
    
  gemini-pro:
    provider: gemini
    model: gemini-3.0-pro
    temperature: 0.3
    
  gpt-4o:
    provider: openai
    model: gpt-4o
    temperature: 0.3
    
  claude-sonnet:
    provider: anthropic
    model: claude-sonnet-4-20250514
    temperature: 0.3
    
  llama-local:
    provider: local
    model: llama3.1:8b
    temperature: 0.3
```

---

## Usage in Agents

```python
# agents/base.py

class BaseAgent(ABC):
    """Abstract base for agents."""
    
    def __init__(
        self,
        library_id: str,
        agent_id: str,
        llm: BaseLLM,              # Injected, not created
        decision_logger: DecisionLogger,
    ):
        self.library_id = library_id
        self.agent_id = agent_id
        self.llm = llm
        self.decision_logger = decision_logger
    
    async def process(self, message: str, context: dict) -> str:
        """Process a message."""
        
        messages = [{"role": "user", "content": message}]
        
        response = await self.llm.generate(
            messages=messages,
            tools=self.tools,
            system_prompt=self._get_system_prompt(),
        )
        
        # ... handle response ...


# Usage
llm = create_llm(provider="gemini", api_key=os.getenv("GOOGLE_API_KEY"))
agent = CatalogAgent(library_id="hanno", agent_id="catalog", llm=llm, ...)
```

---

## Testing Different Models

```python
# eval/model_comparison.py

async def compare_models_on_scenario(
    scenario: BaseScenario,
    model_configs: list[dict],
) -> dict[str, ScenarioResult]:
    """Run one scenario with multiple models."""
    
    results = {}
    
    for config in model_configs:
        model_name = config.get("model", config.get("provider"))
        
        # Create LLM
        llm = create_llm_from_config(config.copy())
        
        # Create agent
        agent = FrontDeskAgent(
            library_id="hanno",
            agent_id="front_desk",
            llm=llm,
            decision_logger=decision_logger,
        )
        
        # Run scenario
        result = await runner.run_scenario(scenario, agent)
        results[model_name] = result
    
    return results


# Example usage
results = await compare_models_on_scenario(
    HallucinationNonExistentBook("The Ivory Concordance"),
    [
        {"provider": "gemini", "api_key": "...", "model": "gemini-3.0-flash"},
        {"provider": "openai", "api_key": "...", "model": "gpt-4o"},
        {"provider": "local", "model": "llama3.1:8b"},
    ],
)

for model, result in results.items():
    print(f"{model}: {result.outcome.value} (score: {result.score:.2f})")
```

---

## Adding a New Provider

To add support for a new LLM provider:

1. Create `core/llm/{provider}.py`
2. Implement `BaseLLM` interface
3. Handle message format conversion
4. Handle tool format conversion
5. Parse responses to `LLMResponse`
6. Add to factory in `core/llm/factory.py`
7. Add config example to documentation

The key challenge is usually tool/function calling format, which varies between providers.
