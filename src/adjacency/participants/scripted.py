"""ScriptedParticipant — deterministic responses from a list. For testing."""
from __future__ import annotations

from typing import Any
from adjacency.participants.base import Participant


class ScriptedParticipant(Participant):
    """Returns responses in order from a fixed list. If exhausted, repeats the last one.

    Intended for deterministic testing of session flow without a live LLM.

    Args:
        responses: Ordered list of string responses to return. Must be non-empty.
            When exhausted, the last response is repeated indefinitely.
    """

    def __init__(self, responses: list[str]) -> None:
        if not responses:
            raise ValueError("ScriptedParticipant requires at least one response")
        self._responses = responses
        self._index = 0
        self.call_count = 0

    def _next(self) -> str:
        val = self._responses[min(self._index, len(self._responses) - 1)]
        self._index += 1
        self.call_count += 1
        return val

    async def respond(self, messages: list[dict[str, Any]], question_key: str) -> str:
        """Return the next scripted response, advancing the internal index."""
        return self._next()

    async def assess(self, messages: list[dict[str, Any]], question_key: str, canonical: str | None) -> str:
        """Return the next scripted verdict (yes/no/escalate); defaults to escalate if value is unrecognized."""
        val = self._next()
        return val if val in ("yes", "no", "escalate") else "escalate"
