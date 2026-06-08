"""Unified LLM client with optional disk cache."""

from __future__ import annotations

from typing import Any

from openai import OpenAI

from athena.config import Settings, get_settings
from athena.storage.cache import clear_llm_cache, get_llm_cache, make_cache_key

Message = dict[str, str]


class LLMClient:
    """OpenAI-compatible chat client (OpenAI / DeepSeek / Gemini)."""

    def __init__(self, settings: Settings | None = None, *, use_cache: bool = True):
        self.settings = settings or get_settings()
        self.use_cache = use_cache
        self._client: OpenAI | None = None

    def _resolve_provider(self, provider: str | None) -> str:
        return (provider or self.settings.default_llm_provider).lower()

    def _get_client(self, provider: str | None = None) -> OpenAI:
        p = self._resolve_provider(provider)
        if p == "deepseek":
            if not self.settings.deepseek_api_key:
                raise ValueError("DEEPSEEK_API_KEY is not set")
            return OpenAI(
                api_key=self.settings.deepseek_api_key,
                base_url=self.settings.deepseek_base_url,
            )
        if p == "gemini":
            if not self.settings.gemini_api_key:
                raise ValueError("GEMINI_API_KEY is not set")
            return OpenAI(
                api_key=self.settings.gemini_api_key,
                base_url=self.settings.gemini_base_url,
            )
        if not self.settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY is not set")
        return OpenAI(
            api_key=self.settings.openai_api_key,
            base_url=self.settings.openai_base_url,
        )

    def chat(
        self,
        messages: list[Message],
        model: str | None = None,
        *,
        provider: str | None = None,
        temperature: float = 0.2,
        max_tokens: int | None = 512,
        use_cache: bool | None = None,
        **kwargs: Any,
    ) -> str:
        """
        Send a chat completion request. Returns assistant text content.
        Identical requests are served from diskcache when enabled.
        """
        model = model or self.settings.default_llm_model
        cache_enabled = self.use_cache if use_cache is None else use_cache
        cache_kwargs = {
            "temperature": temperature,
            "max_tokens": max_tokens,
            "provider": self._resolve_provider(provider),
            **{k: v for k, v in kwargs.items() if k not in ("stream",)},
        }
        cache_key = make_cache_key(messages, model, **cache_kwargs)

        if cache_enabled:
            cached = get_llm_cache().get(cache_key)
            if cached is not None:
                return cached

        client = self._get_client(provider)
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )
        content = response.choices[0].message.content or ""

        if cache_enabled:
            get_llm_cache()[cache_key] = content

        return content

    @staticmethod
    def clear_cache() -> int:
        return clear_llm_cache()
