"""AnthropicBackend — wraps the anthropic SDK."""
from __future__ import annotations
from typing import Any
import anthropic
from adjacency.backends.base import Backend


class AnthropicBackend(Backend):
    """Backend adapter for the Anthropic Messages API.

    Uses the async Anthropic client. Pass model and any additional
    kwargs accepted by anthropic.AsyncAnthropic at construction time.

    Args:
        model: The Anthropic model identifier. Defaults to ``claude-opus-4-6``.
        **kwargs: Additional keyword arguments forwarded to
            ``anthropic.AsyncAnthropic`` (e.g., ``api_key``, ``base_url``).
    """

    def __init__(self, model: str = "claude-opus-4-6", **kwargs: Any) -> None:
        self._model = model
        self._client = anthropic.AsyncAnthropic(**kwargs)

    async def complete(
        self,
        messages: list[dict[str, Any]],
        *,
        system: str | None = None,
    ) -> str:
        """Send messages to the Anthropic API and return the first text block."""
        params: dict[str, Any] = {
            "model": self._model,
            "max_tokens": 2048,
            "messages": messages,
        }
        if system:
            params["system"] = system
        response = await self._client.messages.create(**params)
        text: str = response.content[0].text
        return text
