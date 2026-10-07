"""Model adapter abstractions for agent runtime configuration."""

from __future__ import annotations

from abc import ABC, abstractmethod


class ModelAdapter(ABC):
    """Base adapter contract for model-provider specific configuration."""

    def __init__(self, model_name: str) -> None:
        self._model_name = model_name

    @property
    def model_name(self) -> str:
        """Resolved provider model name."""
        return self._model_name

    @property
    @abstractmethod
    def provider(self) -> str:
        """Provider identifier (gemini, openai, anthropic, ...)."""

    @abstractmethod
    def to_adk_model_ref(self) -> str:
        """Return model identifier consumable by ADK `LlmAgent`."""
