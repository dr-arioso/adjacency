# tests/adjacency/test_events.py
from uuid import uuid4

from adjacency.events import (
    ProtocolCompletedPayload,
    ReviewerResponsePayload,
    StimulusPayload,
)


def test_stimulus_payload_serialization():
    payload = StimulusPayload(
        question_key="locus_visible",
        messages=[{"role": "user", "content": "Do you notice..."}],
        response_kind="free_text",
    )
    d = payload.as_dict()
    assert d["question_key"] == "locus_visible"
    assert d["response_kind"] == "free_text"
    assert isinstance(d["messages"], list)


def test_reviewer_response_payload_valid_values():
    for val in ("yes", "no", "escalate"):
        p = ReviewerResponsePayload(
            question_key="locus_visible",
            response=val,
            based_on_event_id=str(uuid4()),
        )
        assert p.response == val


def test_reviewer_response_payload_rejects_invalid():
    import pytest

    with pytest.raises(ValueError):
        ReviewerResponsePayload(
            question_key="locus_visible",
            response="maybe",
            based_on_event_id=str(uuid4()),
        )


def test_protocol_completed_payload_serialization():
    p = ProtocolCompletedPayload(final_state="mechanism_named", session_id=str(uuid4()))
    d = p.as_dict()
    assert d["final_state"] == "mechanism_named"
