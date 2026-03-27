"""OpenAI-compatible backend adapter for Adjacency."""

from __future__ import annotations

import os
from typing import Any, cast

from openai.types.chat import ChatCompletionContentPartText, ChatCompletionMessageParam

from adjacency.backends.base import Backend


class OpenAICompatibleBackend(Backend):
    """Adapter for OpenAI chat completions and compatible APIs.

    Args:
        model: Model identifier.
        base_url: Optional compatible endpoint URL. Omit for the official API.
        api_key: Optional explicit API key. Falls back to ``OPENAI_API_KEY``.
    """

    def __init__(
        self,
        model: str,
        *,
        base_url: str | None = None,
        api_key: str | None = None,
    ) -> None:
        import openai

        kwargs: dict[str, Any] = {
            "api_key": api_key or os.environ.get("OPENAI_API_KEY", "not-set"),
        }
        if base_url:
            kwargs["base_url"] = base_url
        self._model = model
        self._client = openai.AsyncOpenAI(**kwargs)

    def _uses_max_completion_tokens(self) -> bool:
        """Return True for model families that require max_completion_tokens."""
        return self._model.startswith(("o1", "o3", "gpt"))

    async def complete(
        self,
        messages: list[dict[str, Any]],
        *,
        system: str | None = None,
    ) -> str:
        """Send messages to the API and return the first text response."""
        chat_messages = cast(list[ChatCompletionMessageParam], list(messages))
        if system:
            chat_messages = [
                cast(ChatCompletionMessageParam, {"role": "system", "content": system}),
                *chat_messages,
            ]
        if self._uses_max_completion_tokens():
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=chat_messages,
                max_completion_tokens=2048,
            )
        else:
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=chat_messages,
                max_tokens=2048,
            )
        content = response.choices[0].message.content
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            text_parts = [
                part.text
                for part in content
                if isinstance(part, ChatCompletionContentPartText)
            ]
            if text_parts:
                return "".join(text_parts)
        if content is None:
            raise ValueError(
                f"OpenAI-compatible model {self._model!r} returned null content"
            )
        raise ValueError(
            f"OpenAI-compatible model {self._model!r} returned unsupported content"
        )
