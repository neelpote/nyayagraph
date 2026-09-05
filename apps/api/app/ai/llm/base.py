"""Abstract base class for all LLM providers.

The rest of the application uses only this interface.  Swapping the underlying
model (Ollama/Qwen, OpenAI-compatible, Llama, Mistral, ?) requires adding a new
subclass and registering it in factory.py ? nothing else changes.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


class LLMProviderError(RuntimeError):
    """Raised when the LLM provider is misconfigured or unreachable."""


@dataclass(frozen=True)
class LLMRequest:
    """Structured request sent to any LLM provider."""
    system_prompt: str
    user_prompt: str
    # Pre-formatted evidence context string (already authorisation-filtered).
    context: str = ""
    temperature: float = 0.1
    max_tokens: int = 2048
    # Extra key=value pairs forwarded to providers that support them.
    options: dict = field(default_factory=dict)


@dataclass(frozen=True)
class LLMResponse:
    """Normalised response from any LLM provider."""
    content: str
    model: str
    provider: str
    # Token counts are best-effort; providers that don't report them return 0.
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: float = 0.0


class LLMProvider(ABC):
    """Provider-agnostic interface every concrete implementation must satisfy."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Human-readable provider identifier, e.g. 'ollama', 'openai'."""

    @property
    @abstractmethod
    def model_name(self) -> str:
        """The model identifier as the provider understands it, e.g. 'qwen3:8b'."""

    @abstractmethod
    def generate(self, request: LLMRequest) -> LLMResponse:
        """Send *request* to the model and return the normalised response.

        Implementations must:
        - Raise ``LLMProviderError`` on connectivity or configuration problems.
        - Never expose stack traces or secrets in the raised message.
        - Return in a reasonable timeout (implementations enforce this internally).
        """

    @abstractmethod
    def health(self) -> dict:
        """Return a health-check dict with at minimum ``{"status": "healthy"|"unhealthy"}``."""
