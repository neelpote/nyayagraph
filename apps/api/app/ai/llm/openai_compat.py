"""OpenAI-compatible provider adapter.

Wraps the existing OpenAICompatibleClient so it satisfies the LLMProvider
interface.  This keeps the legacy cloud-API path working without any changes
to the original providers.py code.
"""
from __future__ import annotations

import json
import time

from .base import LLMProvider, LLMProviderError, LLMRequest, LLMResponse


class OpenAICompatProvider(LLMProvider):
    """LLMProvider backed by any OpenAI-compatible /chat/completions endpoint."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        temperature: float = 0.1,
        max_tokens: int = 2048,
    ) -> None:
        if not base_url:
            raise LLMProviderError("LLM_BASE_URL is required for openai_compatible provider")
        if not model:
            raise LLMProviderError("LLM_MODEL is required for openai_compatible provider")
        self._base_url = base_url
        self._api_key = api_key
        self._model = model
        self._temperature = temperature
        self._max_tokens = max_tokens

    @property
    def provider_name(self) -> str:
        return "openai_compatible"

    @property
    def model_name(self) -> str:
        return self._model

    def generate(self, request: LLMRequest) -> LLMResponse:
        # Re-use the existing low-level HTTP client from providers.py.
        from ..providers import OpenAICompatibleClient, AIProviderError

        client = OpenAICompatibleClient(self._base_url, self._api_key)
        user_content = request.user_prompt
        if request.context:
            user_content = f"{request.context}\n\n---\n\nQUESTION:\n{request.user_prompt}"
        messages = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})
        messages.append({"role": "user", "content": user_content})
        payload: dict = {
            "model": self._model,
            "temperature": request.temperature if request.temperature >= 0 else self._temperature,
            "max_tokens": request.max_tokens if request.max_tokens > 0 else self._max_tokens,
            "messages": messages,
        }
        t0 = time.monotonic()
        try:
            data = client.post("chat/completions", payload)
        except AIProviderError as exc:
            raise LLMProviderError(str(exc)) from exc
        latency_ms = (time.monotonic() - t0) * 1000
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMProviderError("OpenAI-compatible provider returned an unrecognised response.") from exc
        usage = data.get("usage") or {}
        return LLMResponse(
            content=str(content),
            model=self._model,
            provider=self.provider_name,
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            latency_ms=round(latency_ms, 1),
        )

    def health(self) -> dict:
        """Best-effort health check ? just verify the endpoint is reachable."""
        from ..providers import OpenAICompatibleClient, AIProviderError

        base = {"provider": self.provider_name, "model": self._model}
        client = OpenAICompatibleClient(self._base_url, self._api_key)
        try:
            client.post("models", {})
            return {**base, "status": "healthy"}
        except AIProviderError:
            # Many endpoints don't support /models; treat as indeterminate.
            return {**base, "status": "unknown", "detail": "Could not verify model listing endpoint"}
        except Exception:
            return {**base, "status": "unhealthy", "detail": "Provider endpoint is unreachable"}
