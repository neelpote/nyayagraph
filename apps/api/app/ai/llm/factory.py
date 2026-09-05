"""LLM provider factory.

Returns the correct LLMProvider subclass based on settings.llm_provider.
Adding a new provider (Llama, Mistral, Gemma, cloud API ?) requires only:
  1. Implementing LLMProvider in a new module.
  2. Adding an elif branch here.
Nothing else in the application needs to change.
"""
from __future__ import annotations

from functools import lru_cache

from .base import LLMProvider, LLMProviderError


def build_llm_provider() -> LLMProvider:
    """Construct the configured LLM provider from application settings.

    Raises ``LLMProviderError`` if the provider is unknown or misconfigured.
    """
    # Import here to avoid circular imports at module load time.
    from ...config import get_settings

    settings = get_settings()
    provider = (settings.llm_provider or "demo").lower().strip()

    if provider in {"demo", "deterministic", ""}:
        # Deterministic demo mode ? no real model.  CaseAgentService handles
        # this path directly; the factory should never be called in demo mode,
        # but we guard it here for safety.
        raise LLMProviderError(
            "LLM provider is set to demo/deterministic mode. "
            "Set LLM_PROVIDER=ollama and configure OLLAMA_BASE_URL to use a real model."
        )

    if provider == "ollama":
        from .qwen import QwenOllamaProvider  # concrete Qwen3-8B implementation

        ollama_url = settings.ollama_base_url or settings.llm_base_url or "http://localhost:11434"
        model = settings.llm_model or "qwen3:8b"
        temperature = getattr(settings, "llm_temperature", 0.1)
        max_tokens = getattr(settings, "llm_max_tokens", 2048)
        return QwenOllamaProvider(
            ollama_base_url=ollama_url,
            model=model,
            temperature=float(temperature),
            max_tokens=int(max_tokens),
        )

    if provider == "openai_compatible":
        # Keep the existing OpenAI-compatible path accessible through the new
        # abstraction for teams that still want a cloud API.
        from .openai_compat import OpenAICompatProvider

        return OpenAICompatProvider(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key,
            model=settings.llm_model,
            temperature=getattr(settings, "llm_temperature", 0.1),
            max_tokens=getattr(settings, "llm_max_tokens", 2048),
        )

    raise LLMProviderError(
        f"Unknown LLM_PROVIDER '{provider}'. "
        "Supported values: ollama, openai_compatible, demo."
    )


@lru_cache(maxsize=1)
def get_llm_provider() -> LLMProvider:
    """Cached singleton ? one provider instance per process.

    Call ``get_llm_provider.cache_clear()`` in tests to reset between cases.
    """
    return build_llm_provider()
