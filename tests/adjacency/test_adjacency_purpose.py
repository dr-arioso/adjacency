"""Tests for AdjacencyPurpose lifecycle anchor."""
import pytest
from uuid import uuid4

from turnturnturn.hub import TTT
from turnturnturn.persistence import InMemoryPersistencePurpose
from turnturnturn.events import HubEventType

from adjacency.events import (
    register_all,
    PROTOCOL_COMPLETED_EVENT,
    ProtocolCompletedPayload,
    ProtocolCompletedEvent,
)
from adjacency.purposes.base import AdjacencyPurpose


@pytest.fixture(autouse=True)
def register_events():
    register_all()


@pytest.mark.asyncio
async def test_adjacency_purpose_starts_cto_on_purpose_started(ttt):
    """AdjacencyPurpose calls hub.start_turn() in on_purpose_started, creating the CTO."""
    content = {"dialog": "hello", "trace_pairs": []}
    purpose = AdjacencyPurpose(
        hub=ttt,
        content_profile="adjacency_test",
        content=content,
    )
    await ttt.start_purpose(purpose)

    # After start_purpose, AdjacencyPurpose should have called hub.start_turn()
    assert purpose.turn_id is not None
    cto = ttt.librarian.get_cto(purpose.turn_id)
    assert cto is not None


@pytest.mark.asyncio
async def test_adjacency_purpose_closes_on_protocol_completed(ttt):
    """AdjacencyPurpose calls ttt.close() when it receives ProtocolCompletedEvent."""
    persister = ttt.persistence_purpose
    content = {"dialog": "hello", "trace_pairs": []}
    purpose = AdjacencyPurpose(hub=ttt, content_profile="adjacency_test", content=content)
    await ttt.start_purpose(purpose)

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

    # Check SESSION_CLOSING was emitted — events list contains dicts with "event_type" string
    event_types = [e["event_type"] for e in persister.events]
    assert HubEventType.SESSION_CLOSING.value in event_types
