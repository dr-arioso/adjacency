"""Gemini backend adapter for Adjacency."""

from __future__ import annotations

import os
from typing import Any

from adjacency.backends.base import Backend


class GeminiBackend(Backend):
    """Adapter for Gemini via ``google-genai``.

    Args:
        model: Gemini model identifier.
        api_key: Optional explicit API key. Falls back to ``GOOGLE_API_KEY``.
        thinking_budget: Optional reasoning budget for supported models.
    """

    def __init__(
        self,
        model: str,
        *,
        api_key: str | None = None,
        thinking_budget: int | None = None,
    ) -> None:
        from google import genai

        resolved_api_key = api_key or os.environ.get("GOOGLE_API_KEY")
        if not resolved_api_key:
            raise ValueError(
                "GeminiBackend requires GOOGLE_API_KEY or an explicit api_key"
            )
        self._model = model
        self._thinking_budget = thinking_budget
        self._client = genai.Client(api_key=resolved_api_key)

    async def complete(
        self,
        messages: list[dict[str, Any]],
        *,
        system: str | None = None,
    ) -> str:
        """Send messages to Gemini and return the generated text."""
        from google.genai import types as genai_types

        contents: list[dict[str, Any]] = []
        for message in messages:
            role = "model" if message["role"] == "assistant" else message["role"]
            contents.append({"role": role, "parts": [{"text": message["content"]}]})

        kwargs: dict[str, Any] = {"max_output_tokens": 2048}
        if system:
            kwargs["system_instruction"] = system
        if self._thinking_budget is not None:
            kwargs["thinking_config"] = genai_types.ThinkingConfig(
                thinking_budget=self._thinking_budget
            )
        response = await self._client.aio.models.generate_content(
            model=self._model,
            contents=contents,
            config=genai_types.GenerateContentConfig(**kwargs),
        )
        if not response.text:
            raise ValueError(f"Gemini model {self._model!r} returned empty text")
        return response.text
