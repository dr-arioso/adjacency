"""LLMParticipant — delegates respond() and assess() to a Backend."""

from __future__ import annotations

from typing import Any

from adjacency.backends.base import Backend
from adjacency.participants.base import Participant


class LLMParticipant(Participant):
    """Participant backed by a live LLM via a Backend adapter.

    Delegates both respond() and assess() to the provided Backend,
    injecting a system prompt if supplied.

    Args:
        backend: The LLM provider adapter to use for completions.
        system_prompt: Optional system-level instruction injected into every request.
    """

    def __init__(self, backend: Backend, system_prompt: str | None = None) -> None:
        self._backend = backend
        self._system_prompt = system_prompt

    async def respond(self, messages: list[dict[str, Any]], question_key: str) -> str:
        """Forward the conversation to the backend and return the model response."""
        # Filter out system messages from the messages list — injected via system param
        user_messages = [m for m in messages if m.get("role") != "system"]
        return await self._backend.complete(
            user_messages,
            system=self._system_prompt,
        )

    async def assess(
        self, messages: list[dict[str, Any]], question_key: str, canonical: str | None
    ) -> str:
        """LLM-as-judge: return yes/no, optionally with an escalate suffix."""
        user_messages = [m for m in messages if m.get("role") != "system"]
        judge_prompt = (
            f"Based on the conversation above, did the subject correctly answer: "
            f"'{question_key}'? Reply with only one of: yes, no, yes_escalate, no_escalate."
        )
        response = await self._backend.complete(
            user_messages + [{"role": "user", "content": judge_prompt}],
        )
        first_token = response.strip().lower().split()[0] if response.strip() else ""
        return (
            first_token
            if first_token in ("yes", "no", "yes_escalate", "no_escalate")
            else "no_escalate"
        )
