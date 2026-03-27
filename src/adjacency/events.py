"""Adjacency custom event types for hub relay.

All types must be registered with TTT.register_event_type() before use.
Call adjacency.events.register_all() at session startup.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Literal
from uuid import UUID, uuid4

from turnturnturn.hub import TTT


def _now_ms() -> int:
    """Return the current Unix timestamp in milliseconds."""
    return int(time.time() * 1000)


# Event type string constants
PROMPT_SUBJECT = "adjacency.prompt_subject"
SUBJECT_RESPONSE = "adjacency.subject_response"
REQUEST_REVIEW = "adjacency.request_review"
REVIEW_RESPONSE = "adjacency.review_response"
WORKFLOW_COMPLETED = "adjacency.workflow_completed"

ALL_EVENT_TYPES = (
    PROMPT_SUBJECT,
    SUBJECT_RESPONSE,
    REQUEST_REVIEW,
    REVIEW_RESPONSE,
    WORKFLOW_COMPLETED,
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
class PromptSubjectPayload:
    """Payload for a prompt delivered to the Subject.

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
            "_schema": "adjacency.prompt_subject",
            "_v": 1,
            "question_key": self.question_key,
            "messages": self.messages,
            "response_kind": self.response_kind,
        }


@dataclass(frozen=True)
class SubjectResponsePayload:
    """Payload carrying the Subject's response to a prompt.

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
            "_schema": "adjacency.subject_response",
            "_v": 1,
            "question_key": self.question_key,
            "messages": self.messages,
        }


@dataclass(frozen=True)
class RequestReviewPayload:
    """Payload for a review request.

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
            "_schema": "adjacency.request_review",
            "_v": 1,
            "question_key": self.question_key,
            "messages": self.messages,
            "canonical_response": self.canonical_response,
        }


@dataclass(frozen=True)
class ReviewResponsePayload:
    """Payload carrying the Reviewer's verdict on a subject response.

    Attributes:
        question_key: Identifier for the question.
        response: Reviewer's verdict: "yes" or "no".
        escalate: Whether the reviewer also wants escalation or extra scrutiny.
        based_on_event_id: Event ID of the subject response being reviewed.

    Raises:
        ValueError: If response is not one of the two allowed values.
    """

    question_key: str
    response: Literal["yes", "no"]
    based_on_event_id: str
    escalate: bool = False

    def __post_init__(self) -> None:
        """Validate response field on construction."""
        if self.response not in ("yes", "no"):
            raise ValueError(
                f"ReviewResponsePayload.response must be 'yes' or 'no'; "
                f"got {self.response!r}"
            )

    def as_dict(self) -> dict[str, Any]:
        """Serialize to a schema-tagged dictionary.

        Returns:
            Dictionary with _schema, _v (version), and payload fields.
        """
        return {
            "_schema": "adjacency.review_response",
            "_v": 1,
            "question_key": self.question_key,
            "response": self.response,
            "escalate": self.escalate,
            "based_on_event_id": self.based_on_event_id,
        }


@dataclass(frozen=True)
class WorkflowCompletedPayload:
    """Payload emitted when the workflow reaches its terminal state.

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
            "_schema": "adjacency.workflow_completed",
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
        event_type_const: The event type string constant (e.g., "adjacency.prompt_subject").

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


#: Custom event for prompt delivery to the subject role.
PromptSubject = _make_event_class(PROMPT_SUBJECT)

#: Custom event carrying the subject role's response.
SubjectResponse = _make_event_class(SUBJECT_RESPONSE)

#: Custom event requesting a reviewer verdict.
RequestReview = _make_event_class(REQUEST_REVIEW)

#: Custom event carrying a reviewer verdict.
ReviewResponse = _make_event_class(REVIEW_RESPONSE)

#: Custom event emitted when a workflow reaches terminal state.
WorkflowCompleted = _make_event_class(WORKFLOW_COMPLETED)
