"""Tests for assemble_session() generic session factory."""
import pytest

from adjacency.participants.resolver import DictResolver
from adjacency.participants.scripted import ScriptedParticipant
from adjacency.protocol import load_protocol
from adjacency.session import Session
from adjacency.session_factory import assemble_session

# Must match the profile_id registered in tests/conftest.py
_TEST_PROFILE = "adjacency_test"

MINIMAL_PROTOCOL = """
type: socratic_elicitation
framing:
  subject:
    system: null
    context: null
  reviewer:
    system: null
ladder:
  - key: q1
    subject_stimulus:
      variants: ["What do you notice?"]
    reviewer_question: "Did subject notice?"
escalation:
  max_attempts_per_state: 2
  on_exhaustion: advance
completion:
  when: q1
"""


def _resolver() -> DictResolver:
    return DictResolver({
        "subject": ScriptedParticipant(responses=["response"]),
        "reviewer": ScriptedParticipant(responses=["yes"]),
    })


def test_assemble_session_returns_session(ttt):
    protocol = load_protocol(MINIMAL_PROTOCOL)
    session = assemble_session(
        hub=ttt,
        content={},
        content_profile=_TEST_PROFILE,
        protocol=protocol,
        participant_resolver=_resolver(),
    )
    assert isinstance(session, Session)


def test_assemble_session_uses_injected_moderator_factory(ttt):
    """Injected moderator_factory is called with (hub, protocol, adjacency_purpose)."""
    from adjacency.purposes.moderator import SocraticElicitationPurpose
    from adjacency.purposes.base import AdjacencyPurpose

    protocol = load_protocol(MINIMAL_PROTOCOL)
    factory_calls: list[tuple] = []

    def spy_factory(hub, proto, adj_purpose):
        factory_calls.append((hub, proto, adj_purpose))
        return SocraticElicitationPurpose(hub=hub, protocol=proto, adjacency_purpose=adj_purpose)

    assemble_session(
        hub=ttt,
        content={},
        content_profile="test",
        protocol=protocol,
        participant_resolver=_resolver(),
        moderator_factory=spy_factory,
    )

    assert len(factory_calls) == 1
    assert factory_calls[0][0] is ttt
    assert factory_calls[0][1] is protocol
    assert isinstance(factory_calls[0][2], AdjacencyPurpose)


@pytest.mark.asyncio
async def test_assemble_session_and_start_registers_all_purposes(ttt):
    """End-to-end: assemble + start registers at least 4 Purposes."""
    protocol = load_protocol(MINIMAL_PROTOCOL)
    session = assemble_session(
        hub=ttt,
        content={},
        content_profile=_TEST_PROFILE,
        protocol=protocol,
        participant_resolver=_resolver(),
    )
    await session.start()
    assert len(ttt.registrations) >= 4
