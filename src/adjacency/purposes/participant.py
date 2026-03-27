"""Role-based ParticipantPurpose subclasses."""

from __future__ import annotations

import re
from typing import Any, Literal, cast
from uuid import UUID, uuid4

from turnturnturn.base_purpose import BasePurpose
from turnturnturn.events import HubEvent

from adjacency.events import (
    PROMPT_SUBJECT,
    REQUEST_REVIEW,
    REVIEW_RESPONSE,
    SUBJECT_RESPONSE,
    PromptSubjectPayload,
    RequestReviewPayload,
    ReviewResponse,
    ReviewResponsePayload,
    SubjectResponse,
    SubjectResponsePayload,
)
from adjacency.participants.base import Participant


class ParticipantPurpose(BasePurpose):
    """Base for role-specific participant Purposes.

    Subclasses declare may_emit and subscribes_to as class variables.
    Call emit() instead of hub.take_turn() to submit events.
    """

    may_emit: frozenset[str] = frozenset()
    subscribes_to: frozenset[str] = frozenset()

    def __init__(self, participant: Participant) -> None:
        super().__init__()
        self.id: UUID = uuid4()
        self._participant = participant

    async def emit(self, event: Any) -> None:
        """Submit a hub event, enforcing the may_emit contract."""
        if event.event_type not in self.may_emit:
            raise PermissionError(
                f"{type(self).__name__} is not permitted to emit {event.event_type!r}. "
                f"Allowed: {self.may_emit}"
            )
        await self.hub.take_turn(event)

    async def _handle_event(self, event: HubEvent) -> None:
        """Route incoming events to _on_addressed_event if subscribed."""
        if event.event_type in self.subscribes_to:
            await self._on_addressed_event(event)

    async def _on_addressed_event(self, event: HubEvent) -> None:
        """Override in subclasses to handle addressed events."""


class SubjectPurpose(ParticipantPurpose):
    """Purpose that forwards stimuli to the Subject Participant and emits responses."""

    name = "subject"
    subscribes_to = frozenset({PROMPT_SUBJECT})
    may_emit = frozenset({SUBJECT_RESPONSE})

    async def _on_addressed_event(self, event: HubEvent) -> None:
        """Receive a PromptSubject, call the participant, and emit a SubjectResponse."""
        payload = cast(PromptSubjectPayload, event.payload)
        response_text = await self._participant.respond(
            messages=payload.messages,
            question_key=payload.question_key,
        )
        updated_messages = list(payload.messages) + [
            {"role": "assistant", "content": response_text}
        ]
        response_event = SubjectResponse(
            purpose_id=self.id,
            purpose_name=self.name,
            hub_token=self._require_token(),
            payload=SubjectResponsePayload(
                question_key=payload.question_key,
                messages=updated_messages,
            ),
        )
        await self.emit(response_event)


class ReviewerPurpose(ParticipantPurpose):
    """Purpose that forwards reviewer requests to the Reviewer Participant and emits verdicts."""

    name = "reviewer"
    subscribes_to = frozenset({REQUEST_REVIEW})
    may_emit = frozenset({REVIEW_RESPONSE})

    @staticmethod
    def _normalize_assessment(verdict: str) -> tuple[Literal["yes", "no"], bool]:
        """Normalize reviewer output into a verdict plus optional escalation flag.

        Accepted forms:
        - `yes`
        - `no`
        - `escalate` -> coerced to `("no", True)` for backward compatibility
        - `yes_escalate`, `yes+escalate`, `escalate_yes`
        - `no_escalate`, `no+escalate`, `escalate_no`
        """
        tokens = {
            token for token in re.split(r"[^a-z]+", verdict.strip().lower()) if token
        }
        has_yes = "yes" in tokens
        has_no = "no" in tokens
        has_escalate = "escalate" in tokens

        if has_yes and has_no:
            raise ValueError(
                f"reviewer verdict cannot contain both yes and no: {verdict!r}"
            )
        if has_yes:
            return "yes", has_escalate
        if has_no:
            return "no", has_escalate
        if has_escalate:
            return "no", True
        raise ValueError(
            f"reviewer verdict must contain yes, no, or escalate; got {verdict!r}"
        )

    async def _on_addressed_event(self, event: HubEvent) -> None:
        """Receive a reviewer request and emit the normalized reviewer response."""
        payload = cast(RequestReviewPayload, event.payload)
        verdict = await self._participant.assess(
            messages=payload.messages,
            question_key=payload.question_key,
            canonical=payload.canonical_response,
        )
        normalized_response, escalate = self._normalize_assessment(verdict)
        response_event = ReviewResponse(
            purpose_id=self.id,
            purpose_name=self.name,
            hub_token=self._require_token(),
            payload=ReviewResponsePayload(
                question_key=payload.question_key,
                response=normalized_response,
                escalate=escalate,
                based_on_event_id=str(event.event_id),
            ),
        )
        await self.emit(response_event)
