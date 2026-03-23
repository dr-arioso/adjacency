"""Participant ABC — response generation only; no hub awareness."""

from __future__ import annotations

import abc
from typing import Any


class Participant(abc.ABC):
    """Generates responses for a ParticipantPurpose. Not a TTT actor."""

    @abc.abstractmethod
    async def respond(self, messages: list[dict[str, Any]], question_key: str) -> str:
        """Generate a response given the current messages list."""

    @abc.abstractmethod
    async def assess(
        self, messages: list[dict[str, Any]], question_key: str, canonical: str | None
    ) -> str:
        """Score a subject response. Returns 'yes', 'no', or 'escalate'."""
