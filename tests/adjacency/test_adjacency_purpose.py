"""Tests for AdjacencyPurpose lifecycle anchor."""

from uuid import uuid4

import pytest
from turnturnturn.events import HubEventType

from adjacency.events import (
    ProtocolCompletedEvent,
    ProtocolCompletedPayload,
    register_all,
)
from adjacency.purposes.base import AdjacencyPurpose


@pytest.fixture(autouse=True)
def register_events():
    """Ensure adjacency event types are registered before each test."""
    register_all()


@pytest.mark.asyncio
async def test_adjacency_purpose_starts_cto_on_start_session(ttt, adjacency_purpose):
    """AdjacencyPurpose starts the CTO when Session.start() tells it to."""
    adjacency_purpose._content = {"dialog": "hello", "trace_pairs": []}
    await adjacency_purpose.start_session()

    assert adjacency_purpose.turn_id is not None
    cto = ttt.librarian.get_cto(adjacency_purpose.turn_id)
    assert cto is not None


@pytest.mark.asyncio
async def test_adjacency_purpose_closes_on_protocol_completed(ttt, adjacency_purpose):
    """AdjacencyPurpose requests hub-managed shutdown when the protocol completes."""
    persister = ttt.persistence_purpose
    adjacency_purpose._content = {"dialog": "hello", "trace_pairs": []}
    await adjacency_purpose.start_session()

    completion = ProtocolCompletedEvent(
        purpose_id=adjacency_purpose.id,
        purpose_name=adjacency_purpose.name,
        hub_token=adjacency_purpose.token,
        payload=ProtocolCompletedPayload(
            final_state="mechanism_named",
            session_id=str(uuid4()),
        ),
    )
    await ttt.take_turn(completion)

    # Check the shutdown path was persisted end-to-end.
    event_types = [e["event_type"] for e in persister.events]
    assert "end_session" in event_types
    assert HubEventType.SESSION_CLOSING.value in event_types
    assert "purpose_completed" in event_types
    assert HubEventType.SESSION_CLOSE_PENDING.value in event_types


@pytest.mark.asyncio
async def test_adjacency_purpose_persists_predefined_session_code():
    """Caller-supplied session_code is propagated into session lifecycle payloads."""
    from turnturnturn.hub import TTT
    from turnturnturn.persistence import InMemoryPersistencePurpose

    purpose = AdjacencyPurpose(
        content_profile="adjacency_test",
        content={"dialog": "hello", "trace_pairs": []},
        session_code="alpha-42",
    )
    ttt = TTT.start(InMemoryPersistencePurpose(), session_owner_purpose=purpose)
    persister = ttt.persistence_purpose
    await purpose.start_session()

    completion = ProtocolCompletedEvent(
        purpose_id=purpose.id,
        purpose_name=purpose.name,
        hub_token=purpose.token,
        payload=ProtocolCompletedPayload(
            final_state="mechanism_named",
            session_id=str(uuid4()),
        ),
    )
    await ttt.take_turn(completion)

    payloads = {
        e["event_type"]: e["payload"]
        for e in persister.events
        if e["event_type"]
        in {
            HubEventType.SESSION_CLOSING.value,
            HubEventType.SESSION_CLOSE_PENDING.value,
        }
    }
    assert payloads[HubEventType.SESSION_CLOSING.value]["session_code"] == "alpha-42"
    assert (
        payloads[HubEventType.SESSION_CLOSE_PENDING.value]["session_code"] == "alpha-42"
    )
