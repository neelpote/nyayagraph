"""Qwen3-8B provider via Ollama.

Ollama exposes an OpenAI-compatible /v1/chat/completions endpoint AND its own
/api/chat endpoint.  We use /api/chat because it gives us Ollama-native options
(num_predict, temperature) without depending on the OpenAI shim.

Architecture:
    User question
        ? (already authorisation-filtered by caller)
    QwenOllamaProvider.generate()
        ?
    POST http://<OLLAMA_BASE_URL>/api/chat
        ?
    JSON response ? LLMResponse
"""
from __future__ import annotations

import json
import time
from urllib.request import Request, urlopen
from urllib.error import URLError

from .base import LLMProvider, LLMProviderError, LLMRequest, LLMResponse


# Maximum bytes we read from Ollama to prevent memory exhaustion on rogue responses.
_MAX_RESPONSE_BYTES = 4 * 1024 * 1024  # 4 MiB

# Ollama-specific options that map well onto Qwen3-8B generation quality/speed.
_QWEN_DEFAULTS = {
    "temperature": 0.1,
    "top_p": 0.9,
    "repeat_penalty": 1.1,
    # Suppress Qwen3 chain-of-thought thinking tokens so the model returns
    # the final answer only.  This is the /no-think mode for Qwen3.
    "stop": ["<think>", "</think>"],
}


class QwenOllamaProvider(LLMProvider):
    """Sends requests to a locally running Ollama instance serving Qwen3-8B.

    Configuration is injected at construction time so the class remains
    independently testable without touching global settings.
    """

    def __init__(
        self,
        ollama_base_url: str,
        model: str = "qwen3:8b",
        temperature: float = 0.1,
        max_tokens: int = 2048,
        timeout: int = 120,
    ) -> None:
        if not ollama_base_url:
            raise LLMProviderError("OLLAMA_BASE_URL is required for the ollama provider")
        self._base_url = ollama_base_url.rstrip("/")
        self._model = model
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._timeout = timeout

    # ------------------------------------------------------------------
    # LLMProvider interface
    # ------------------------------------------------------------------

    @property
    def provider_name(self) -> str:
        return "ollama"

    @property
    def model_name(self) -> str:
        return self._model

    def generate(self, request: LLMRequest) -> LLMResponse:
        """Call Ollama /api/chat and return a normalised LLMResponse."""
        messages = self._build_messages(request)
        payload = {
            "model": self._model,
            "messages": messages,
            "stream": False,
            "options": {
                **_QWEN_DEFAULTS,
                "temperature": request.temperature if request.temperature >= 0 else self._temperature,
                "num_predict": request.max_tokens if request.max_tokens > 0 else self._max_tokens,
                **request.options,
            },
            # Request JSON output format where the caller uses it.
            # format is only set when the user prompt explicitly asks for JSON.
            **({"format": "json"} if '"json"' in request.user_prompt.lower() or "json" in request.user_prompt.lower() else {}),
        }
        url = f"{self._base_url}/api/chat"
        raw_request = Request(
            url,
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        t0 = time.monotonic()
        try:
            with urlopen(raw_request, timeout=self._timeout) as resp:  # nosec B310 ? configured internal endpoint
                raw = resp.read(_MAX_RESPONSE_BYTES)
        except URLError as exc:
            raise LLMProviderError(
                "The AI service (Ollama) is temporarily unavailable. Please try again."
            ) from exc
        except Exception as exc:
            raise LLMProviderError(
                "The AI service returned an unexpected error. Please try again."
            ) from exc
        latency_ms = (time.monotonic() - t0) * 1000

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise LLMProviderError("AI service returned malformed data.") from exc

        content = self._extract_content(data)
        usage = data.get("usage") or {}
        return LLMResponse(
            content=content,
            model=data.get("model", self._model),
            provider=self.provider_name,
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            latency_ms=round(latency_ms, 1),
        )

    def health(self) -> dict:
        """Check that Ollama is reachable and the configured model is available."""
        base = {
            "provider": self.provider_name,
            "model": self._model,
        }
        # /api/tags lists all local models.
        tags_url = f"{self._base_url}/api/tags"
        tags_request = Request(tags_url, method="GET")
        try:
            with urlopen(tags_request, timeout=5) as resp:  # nosec B310
                data = json.loads(resp.read(256 * 1024))
        except Exception:
            return {**base, "status": "unhealthy", "detail": "Ollama is unreachable"}

        models = [m.get("name", "") for m in data.get("models", [])]
        # Ollama model names include the tag, e.g. "qwen3:8b".
        model_available = any(
            self._model in name or name.startswith(self._model.split(":")[0])
            for name in models
        )
        if not model_available:
            return {
                **base,
                "status": "unhealthy",
                "detail": f"Model '{self._model}' not found in Ollama. Run: ollama pull {self._model}",
                "available_models": models,
            }
        return {**base, "status": "healthy"}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_messages(request: LLMRequest) -> list[dict]:
        """Assemble the Ollama messages list.

        Structure:
          system  ? NyayaGraph system prompt
          user    ? evidence context + question
        The evidence context is injected into the user turn rather than the
        system prompt so it varies per request without polluting the system
        instruction.
        """
        user_content = request.user_prompt
        if request.context:
            user_content = f"{request.context}\n\n---\n\nQUESTION:\n{request.user_prompt}"
        messages = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})
        messages.append({"role": "user", "content": user_content})
        return messages

    @staticmethod
    def _extract_content(data: dict) -> str:
        """Pull the assistant reply text from Ollama's /api/chat response."""
        try:
            content = data["message"]["content"]
            if not isinstance(content, str):
                raise ValueError("content is not a string")
            # Strip Qwen3 thinking tokens if the model leaked them.
            # They appear between <think>?</think> and should not be shown.
            import re
            content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
            return content
        except (KeyError, TypeError, ValueError) as exc:
            raise LLMProviderError("AI service returned an unrecognisable response structure.") from exc
