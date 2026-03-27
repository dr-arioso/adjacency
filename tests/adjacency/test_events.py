# tests/adjacency/test_events.py
from uuid import uuid4

from adjacency.events import (
    PromptSubjectPayload,
    ReviewResponsePayload,
    WorkflowCompletedPayload,
)


def test_prompt_subject_payload_serialization():
    payload = PromptSubjectPayload(
        question_key="locus_visible",
        messages=[{"role": "user", "content": "Do you notice..."}],
        response_kind="free_text",
    )
    d = payload.as_dict()
    assert d["question_key"] == "locus_visible"
    assert d["response_kind"] == "free_text"
    assert isinstance(d["messages"], list)


def test_review_response_payload_valid_values():
    for val, escalate in (("yes", False), ("no", False), ("yes", True), ("no", True)):
        p = ReviewResponsePayload(
            question_key="locus_visible",
            response=val,
            escalate=escalate,
            based_on_event_id=str(uuid4()),
        )
        assert p.response == val
        assert p.escalate is escalate


def test_review_response_payload_rejects_invalid():
    import pytest

    with pytest.raises(ValueError):
        ReviewResponsePayload(
            question_key="locus_visible",
            response="maybe",
            based_on_event_id=str(uuid4()),
        )


def test_workflow_completed_payload_serialization():
    p = WorkflowCompletedPayload(final_state="mechanism_named", session_id=str(uuid4()))
    d = p.as_dict()
    assert d["final_state"] == "mechanism_named"
