"""Backend ABC — LLM provider adapter."""
from __future__ import annotations
import abc
from typing import Any


class Backend(abc.ABC):
    @abc.abstractmethod
    async def complete(
        self,
        messages: list[dict[str, Any]],
        *,
        system: str | None = None,
    ) -> str:
        """Send messages to the LLM and return the response text."""
