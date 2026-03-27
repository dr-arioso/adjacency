"""Ollama backend adapter for Adjacency."""

from __future__ import annotations

import asyncio
from typing import Any

from adjacency.backends.base import Backend


class OllamaBackend(Backend):
    """Adapter for local or remote Ollama chat inference.

    Args:
        model: Ollama model name, e.g. ``qwen2.5:14b``.
        host: Optional Ollama host URL. Defaults to the local daemon.
    """

    def __init__(self, model: str, *, host: str | None = None) -> None:
        import ollama  # noqa: F401

        self._model = model
        self._host = host

    async def complete(
        self,
        messages: list[dict[str, Any]],
        *,
        system: str | None = None,
    ) -> str:
        """Send chat messages to Ollama in a worker thread and return the text."""
        import ollama

        payload = list(messages)
        if system:
            payload = [{"role": "system", "content": system}] + payload

        def _chat() -> str:
            client = ollama.Client(host=self._host) if self._host else ollama.Client()
            response = client.chat(
                model=self._model,
                messages=payload,
                options={"num_predict": 2048},
            )
            content_obj = response.message.content
            if not isinstance(content_obj, str) or not content_obj:
                raise ValueError(f"Ollama model {self._model!r} returned empty content")
            content: str = content_obj
            return content

        return await asyncio.to_thread(_chat)
