"""Tests for SubjectPurpose, ReviewerPurpose, and ParticipantPurpose base."""

import time
from uuid import uuid4

import pytest
from turnturnturn.events import HubEvent

from adjacency.events import (
    PROMPT_SUBJECT,
    REQUEST_REVIEW,
    REVIEW_RESPONSE,
    SUBJECT_RESPONSE,
    PromptSubjectPayload,
    RequestReviewPayload,
    register_all,
)
from adjacency.purposes.participant import ReviewerPurpose, SubjectPurpose


def make_hub_event(event_type, payload):
    """Create a HubEvent for direct delivery to a Purpose (bypasses hub validation).

    hub_token and downlink_signature are left None so the event can be passed
    directly to _handle_event() without BasePurpose.take_turn() validation.
    """
    return HubEvent(
        event_type=event_type,
        event_id=uuid4(),
        created_at_ms=int(time.time() * 1000),
        payload=payload,
    )


@pytest.fixture(autouse=True)
def setup_events():
    register_all()


@pytest.mark.asyncio
async def test_subject_purpose_calls_participant_on_stimulus(ttt):
    """SubjectPurpose delegates to participant.respond() when PromptSubject is received."""
    from adjacency.participants.scripted import ScriptedParticipant

    participant = ScriptedParticipant(responses=["The LLM mishandled the tense."])
    subject = SubjectPurpose(participant=participant)
    await ttt.start_purpose(subject)

    stimulus_payload = PromptSubjectPayload(
        question_key="locus_visible",
        messages=[{"role": "user", "content": "Do you notice..."}],
        response_kind="free_text",
    )
    event = make_hub_event(PROMPT_SUBJECT, stimulus_payload)
    await subject._handle_event(event)

    assert participant.call_count == 1


@pytest.mark.asyncio
async def test_reviewer_purpose_calls_participant_assess_on_request(ttt):
    """ReviewerPurpose delegates to participant.assess() when RequestReview is received."""
    from adjacency.participants.scripted import ScriptedParticipant

    participant = ScriptedParticipant(responses=["yes"])
    reviewer = ReviewerPurpose(participant=participant)
    await ttt.start_purpose(reviewer)

    request_payload = RequestReviewPayload(
        question_key="locus_visible",
        messages=[{"role": "user", "content": "Did subject identify misalignment?"}],
        canonical_response="The LLM treats future-tense as present-tense",
    )
    event = make_hub_event(REQUEST_REVIEW, request_payload)
    await reviewer._handle_event(event)

    assert participant.call_count == 1


def test_subject_purpose_may_emit_only_stimulus_response():
    assert SUBJECT_RESPONSE in SubjectPurpose.may_emit
    assert REVIEW_RESPONSE not in SubjectPurpose.may_emit


def test_reviewer_purpose_may_emit_only_reviewer_response():
    assert REVIEW_RESPONSE in ReviewerPurpose.may_emit
    assert SUBJECT_RESPONSE not in ReviewerPurpose.may_emit


def test_reviewer_purpose_normalizes_yes_escalate():
    response, escalate = ReviewerPurpose._normalize_assessment("yes_escalate")
    assert response == "yes"
    assert escalate is True


def test_reviewer_purpose_normalizes_plain_escalate_to_no_plus_flag():
    response, escalate = ReviewerPurpose._normalize_assessment("escalate")
    assert response == "no"
    assert escalate is True
