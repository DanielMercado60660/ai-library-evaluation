"""Gemini implementation of the model adapter contract."""

from __future__ import annotations

from agents.models.base import ModelAdapter


class GeminiModelAdapter(ModelAdapter):
    """Adapter for Gemini model references."""

    @property
    def provider(self) -> str:
        return "gemini"

    def to_adk_model_ref(self) -> str:
        return self.model_name
