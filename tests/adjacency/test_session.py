"""Tests for AdjacencyLibrarian and Session (via assemble_session)."""

import pytest

from adjacency.librarian import AdjacencyLibrarian
from adjacency.participants.resolver import DictResolver
from adjacency.participants.scripted import ScriptedParticipant
from adjacency.protocol import load_protocol
from adjacency.session_factory import assemble_session

MINIMAL_PROTOCOL = """
type: socratic_elicitation
framing:
  subject:
    system: "You are a helpful assistant."
    context: "Review this exchange."
  reviewer:
    system: null
ladder:
  - key: locus_visible
    subject_stimulus:
      variants: ["Do you notice anything?"]
    reviewer_question: "Did subject find anything?"
escalation:
  max_attempts_per_state: 2
  on_exhaustion: advance
completion:
  when: locus_visible
"""


def test_adjacency_librarian_participant_instructions():
    """AdjacencyLibrarian returns instructions by role name."""
    librarian = AdjacencyLibrarian(
        ttt_librarian=None,
        instructions={"subject": "You are a test subject.", "reviewer": "You review."},
    )
    assert librarian.participant_instructions("subject") == "You are a test subject."
    assert librarian.participant_instructions("reviewer") == "You review."
    assert librarian.participant_instructions("unknown") is None


@pytest.mark.asyncio
async def test_session_starts_and_all_purposes_registered(ttt):
    """assemble_session + start() registers at least 3 Purposes with the hub."""
    protocol = load_protocol(MINIMAL_PROTOCOL)
    resolver = DictResolver(
        {
            "subject": ScriptedParticipant(responses=["I notice a tense mismatch."]),
            "reviewer": ScriptedParticipant(responses=["yes"]),
        }
    )
    session = assemble_session(
        hub=ttt,
        content={},
        content_profile="adjacency_test",
        protocol=protocol,
        participant_resolver=resolver,
    )
    await session.start()
    assert len(ttt.registrations) >= 3
