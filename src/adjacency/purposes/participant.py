"""Role-based ParticipantPurpose subclasses."""

from __future__ import annotations

from typing import Any, Literal, cast
from uuid import UUID, uuid4

from turnturnturn.base_purpose import BasePurpose  # type: ignore[import-untyped]
from turnturnturn.events import HubEvent  # type: ignore[import-untyped]
from turnturnturn.hub import TTT  # type: ignore[import-untyped]

from adjacency.events import (
    REVIEWER_REQUEST_EVENT,
    REVIEWER_RESPONSE_EVENT,
    STIMULUS_EVENT,
    STIMULUS_RESPONSE_EVENT,
    ReviewerResponseEvent,
    ReviewerResponsePayload,
    StimulusResponseEvent,
    StimulusResponsePayload,
)
from adjacency.participants.base import Participant


class ParticipantPurpose(BasePurpose):  # type: ignore[misc]
    """Base for role-specific participant Purposes.

    Subclasses declare may_emit and subscribes_to as class variables.
    Call emit() instead of hub.take_turn() to submit events.
    """

    may_emit: frozenset[str] = frozenset()
    subscribes_to: frozenset[str] = frozenset()

    def __init__(self, hub: TTT, participant: Participant) -> None:
        super().__init__()
        self.id: UUID = uuid4()
        self._hub = hub
        self._participant = participant

    async def emit(self, event: Any) -> None:
        """Submit a hub event, enforcing the may_emit contract."""
        if event.event_type not in self.may_emit:
            raise PermissionError(
                f"{type(self).__name__} is not permitted to emit {event.event_type!r}. "
                f"Allowed: {self.may_emit}"
            )
        await self._hub.take_turn(event)

    async def _handle_event(self, event: HubEvent) -> None:
        """Route incoming events to _on_addressed_event if subscribed."""
        if event.event_type in self.subscribes_to:
            await self._on_addressed_event(event)

    async def _on_addressed_event(self, event: HubEvent) -> None:
        """Override in subclasses to handle addressed events."""


class SubjectPurpose(ParticipantPurpose):
    """Purpose that forwards stimuli to the Subject Participant and emits responses."""

    name = "subject"
    subscribes_to = frozenset({STIMULUS_EVENT})
    may_emit = frozenset({STIMULUS_RESPONSE_EVENT})

    async def _on_addressed_event(self, event: HubEvent) -> None:
        """Receive a StimulusEvent, call the participant, and emit a StimulusResponseEvent."""
        payload = event.payload
        response_text = await self._participant.respond(
            messages=payload.messages,
            question_key=payload.question_key,
        )
        updated_messages = list(payload.messages) + [
            {"role": "assistant", "content": response_text}
        ]
        response_event = StimulusResponseEvent(
            purpose_id=self.id,
            purpose_name=self.name,
            hub_token=self.token,
            payload=StimulusResponsePayload(
                question_key=payload.question_key,
                messages=updated_messages,
            ),
        )
        await self.emit(response_event)


class ReviewerPurpose(ParticipantPurpose):
    """Purpose that forwards reviewer requests to the Reviewer Participant and emits verdicts."""

    name = "reviewer"
    subscribes_to = frozenset({REVIEWER_REQUEST_EVENT})
    may_emit = frozenset({REVIEWER_RESPONSE_EVENT})

    async def _on_addressed_event(self, event: HubEvent) -> None:
        """Receive a ReviewerRequestEvent, call the participant, and emit a ReviewerResponseEvent."""
        payload = event.payload
        verdict = await self._participant.assess(
            messages=payload.messages,
            question_key=payload.question_key,
            canonical=payload.canonical_response,
        )
        response_event = ReviewerResponseEvent(
            purpose_id=self.id,
            purpose_name=self.name,
            hub_token=self.token,
            payload=ReviewerResponsePayload(
                question_key=payload.question_key,
                response=cast(Literal["yes", "no", "escalate"], verdict),
                based_on_event_id=str(event.event_id),
            ),
        )
        await self.emit(response_event)
