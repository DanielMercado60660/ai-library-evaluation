"""Factory helpers for model adapter construction."""

from __future__ import annotations

from agents.config import MODEL_NAME
from agents.models.base import ModelAdapter
from agents.models.gemini_adapter import GeminiModelAdapter


def configured_model_name(model_name: str | None = None) -> str:
    """Resolve configured model name with sensible fallback."""
    return (model_name or MODEL_NAME or "gemini-3-flash-preview").strip() or "gemini-3-flash-preview"


def build_model_adapter(model_name: str | None = None) -> ModelAdapter:
    """Build adapter for configured provider.

    v2.1.2 keeps Gemini as the sole provider implementation while exposing the
    interface seam for future multi-provider expansion.
    """
    resolved_name = configured_model_name(model_name)
    return GeminiModelAdapter(resolved_name)
