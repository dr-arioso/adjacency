"""Adjacency custom event types for hub relay.

All types must be registered with TTT.register_event_type() before use.
Call adjacency.events.register_all() at session startup.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal
from uuid import UUID, uuid4
import time

from turnturnturn.hub import TTT  # type: ignore[import-untyped]


def _now_ms() -> int:
    """Return the current Unix timestamp in milliseconds."""
    return int(time.time() * 1000)


# Event type string constants
STIMULUS_EVENT = "adjacency.stimulus"
STIMULUS_RESPONSE_EVENT = "adjacency.stimulus_response"
REVIEWER_REQUEST_EVENT = "adjacency.reviewer_request"
REVIEWER_RESPONSE_EVENT = "adjacency.reviewer_response"
PROTOCOL_COMPLETED_EVENT = "adjacency.protocol_completed"

ALL_EVENT_TYPES = (
    STIMULUS_EVENT,
    STIMULUS_RESPONSE_EVENT,
    REVIEWER_REQUEST_EVENT,
    REVIEWER_RESPONSE_EVENT,
    PROTOCOL_COMPLETED_EVENT,
)


def register_all() -> None:
    """Register all Adjacency event types with TTT's custom event relay.

    Must be called at session startup before any events are emitted.
    Each event type is registered as multicast.
    """
    for et in ALL_EVENT_TYPES:
        TTT.register_event_type(et, multicast=True)


# ---------------------------------------------------------------------------
# Payload dataclasses
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class StimulusPayload:
    """Payload for a stimulus event delivered to the Subject.

    Attributes:
        question_key: Identifier for the question within the protocol.
        messages: Message list in OpenAI chat format.
        response_kind: Expected response format, e.g., "free_text".
    """

    question_key: str
    messages: list[dict[str, Any]]
    response_kind: str

    def as_dict(self) -> dict[str, Any]:
        """Serialize to a schema-tagged dictionary.

        Returns:
            Dictionary with _schema, _v (version), and payload fields.
        """
        return {
            "_schema": "adjacency.stimulus",
            "_v": 1,
            "question_key": self.question_key,
            "messages": self.messages,
            "response_kind": self.response_kind,
        }


@dataclass(frozen=True)
class StimulusResponsePayload:
    """Payload carrying the Subject's response to a stimulus.

    Attributes:
        question_key: Identifier for the question.
        messages: Message list with Subject's response appended.
    """

    question_key: str
    messages: list[dict[str, Any]]

    def as_dict(self) -> dict[str, Any]:
        """Serialize to a schema-tagged dictionary.

        Returns:
            Dictionary with _schema, _v (version), and payload fields.
        """
        return {
            "_schema": "adjacency.stimulus_response",
            "_v": 1,
            "question_key": self.question_key,
            "messages": self.messages,
        }


@dataclass(frozen=True)
class ReviewerRequestPayload:
    """Payload for a reviewer assessment request.

    Attributes:
        question_key: Identifier for the question.
        messages: Curated context for the reviewer (message list).
        canonical_response: Expected response for experimental pairs;
            None for control pairs or null gestalt.
    """

    question_key: str
    messages: list[dict[str, Any]]
    canonical_response: str | None

    def as_dict(self) -> dict[str, Any]:
        """Serialize to a schema-tagged dictionary.

        Returns:
            Dictionary with _schema, _v (version), and payload fields.
        """
        return {
            "_schema": "adjacency.reviewer_request",
            "_v": 1,
            "question_key": self.question_key,
            "messages": self.messages,
            "canonical_response": self.canonical_response,
        }


@dataclass(frozen=True)
class ReviewerResponsePayload:
    """Payload carrying the Reviewer's verdict on a stimulus response.

    Attributes:
        question_key: Identifier for the question.
        response: Reviewer's verdict: "yes", "no", or "escalate".
        based_on_event_id: Event ID of the stimulus response being reviewed.

    Raises:
        ValueError: If response is not one of the three allowed values.
    """

    question_key: str
    response: Literal["yes", "no", "escalate"]
    based_on_event_id: str

    def __post_init__(self) -> None:
        """Validate response field on construction."""
        if self.response not in ("yes", "no", "escalate"):
            raise ValueError(
                f"ReviewerResponsePayload.response must be 'yes', 'no', or 'escalate'; "
                f"got {self.response!r}"
            )

    def as_dict(self) -> dict[str, Any]:
        """Serialize to a schema-tagged dictionary.

        Returns:
            Dictionary with _schema, _v (version), and payload fields.
        """
        return {
            "_schema": "adjacency.reviewer_response",
            "_v": 1,
            "question_key": self.question_key,
            "response": self.response,
            "based_on_event_id": self.based_on_event_id,
        }


@dataclass(frozen=True)
class ProtocolCompletedPayload:
    """Payload emitted when the protocol reaches its terminal state.

    Attributes:
        final_state: The final resolved ladder key.
        session_id: Identifier for the session that completed.
    """

    final_state: str
    session_id: str

    def as_dict(self) -> dict[str, Any]:
        """Serialize to a schema-tagged dictionary.

        Returns:
            Dictionary with _schema, _v (version), and payload fields.
        """
        return {
            "_schema": "adjacency.protocol_completed",
            "_v": 1,
            "final_state": self.final_state,
            "session_id": self.session_id,
        }


# ---------------------------------------------------------------------------
# Event dataclasses (implement PurposeEventProtocol)
# ---------------------------------------------------------------------------

def _make_event_class(event_type_const: str) -> type:
    """Factory for creating event dataclasses implementing PurposeEventProtocol.

    Generates a frozen dataclass with standard event fields: purpose_id,
    purpose_name, hub_token, payload, event_type, event_id, and created_at_ms.

    Args:
        event_type_const: The event type string constant (e.g., "adjacency.stimulus").

    Returns:
        A frozen dataclass type with event_type set to the constant.
    """
    @dataclass(frozen=True)
    class _Event:
        """Base event class with standard protocol event fields."""

        purpose_id: UUID
        purpose_name: str
        hub_token: str
        payload: Any
        event_type: str = field(default=event_type_const, init=False)
        event_id: UUID = field(default_factory=uuid4)
        created_at_ms: int = field(default_factory=_now_ms)

    class_name = event_type_const.replace(".", "_").title().replace("_", "")
    _Event.__name__ = class_name
    _Event.__qualname__ = class_name
    return _Event


#: Event for stimulus delivery to Subject.
StimulusEvent = _make_event_class(STIMULUS_EVENT)

#: Event for Subject's response to stimulus.
StimulusResponseEvent = _make_event_class(STIMULUS_RESPONSE_EVENT)

#: Event requesting Reviewer assessment.
ReviewerRequestEvent = _make_event_class(REVIEWER_REQUEST_EVENT)

#: Event carrying Reviewer's response.
ReviewerResponseEvent = _make_event_class(REVIEWER_RESPONSE_EVENT)

#: Event emitted at protocol completion.
ProtocolCompletedEvent = _make_event_class(PROTOCOL_COMPLETED_EVENT)
