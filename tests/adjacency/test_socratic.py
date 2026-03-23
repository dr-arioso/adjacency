# tests/adjacency/test_socratic.py
import pytest
from uuid import uuid4
from adjacency.protocol import load_protocol, LadderStep, Escalation, Protocol, Framing
from adjacency.purposes.moderator import LadderState
from turnturnturn.base_purpose import BasePurpose  # type: ignore[import-untyped]


# Used by hub-integrated tests
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

SIMPLE_LADDER = [
    LadderStep("locus_visible", ["Do you notice?", "Notice asymmetry?", "Assume wrong."],
               "Did subject find anything?"),
    LadderStep("locus_identified", ["What changed?", "What was lost?"],
               "Correct locus?", requires=["locus_visible"]),
    LadderStep("mechanism_named", ["What caused this?"],
               "Complete account?", requires=["locus_identified"]),
]
ESCALATION = Escalation(max_attempts_per_state=3, on_exhaustion="advance")


def test_ladder_state_initial():
    state = LadderState(ladder=SIMPLE_LADDER, escalation=ESCALATION)
    assert state.current_key == "locus_visible"
    assert state.current_variant_index == 0
    assert state.is_complete is False


def test_ladder_state_advances_on_yes():
    state = LadderState(ladder=SIMPLE_LADDER, escalation=ESCALATION)
    state.record_verdict("yes")
    assert state.current_key == "locus_identified"
    assert state.current_variant_index == 0


def test_ladder_state_escalates_on_no():
    state = LadderState(ladder=SIMPLE_LADDER, escalation=ESCALATION)
    state.record_verdict("no")
    assert state.current_key == "locus_visible"  # still on same step
    assert state.current_variant_index == 1      # next variant


def test_ladder_state_advances_on_exhaustion():
    state = LadderState(ladder=SIMPLE_LADDER, escalation=ESCALATION)
    state.record_verdict("no")  # variant 1
    state.record_verdict("no")  # variant 2
    state.record_verdict("no")  # exhausted (3 attempts, max_attempts_per_state=3)
    assert state.current_key == "locus_identified"


def test_ladder_state_complete_after_final_yes():
    state = LadderState(ladder=SIMPLE_LADDER, escalation=ESCALATION)
    state.record_verdict("yes")  # locus_visible done
    state.record_verdict("yes")  # locus_identified done
    state.record_verdict("yes")  # mechanism_named done
    assert state.is_complete is True


def test_ladder_state_escalate_verdict_stays_on_step():
    state = LadderState(ladder=SIMPLE_LADDER, escalation=ESCALATION)
    state.record_verdict("escalate")
    assert state.current_key == "locus_visible"
    assert state.current_variant_index == 1  # next variant, same as no


@pytest.mark.asyncio
async def test_socratic_elicitation_runs_one_pair_to_completion(ttt):
    """Full run: CTO started -> SocraticElicitation drives ladder -> ProtocolCompletedEvent emitted."""
    from adjacency.events import register_all, PROTOCOL_COMPLETED_EVENT
    from adjacency.purposes.base import AdjacencyPurpose
    from adjacency.purposes.moderator import SocraticElicitationPurpose
    from adjacency.purposes.participant import SubjectPurpose, ReviewerPurpose
    from adjacency.participants.scripted import ScriptedParticipant
    register_all()

    subject_p = ScriptedParticipant(responses=["I notice a tense issue."] * 10)
    reviewer_p = ScriptedParticipant(responses=["yes"] * 10)

    protocol = load_protocol(MINIMAL_PROTOCOL)  # single step ladder

    completed: list[str] = []

    class WatchPurpose(BasePurpose):
        name = "watcher"
        id = uuid4()

        async def _handle_event(self, event):
            if event.event_type == PROTOCOL_COMPLETED_EVENT:
                completed.append("done")

    adjacency_p = AdjacencyPurpose(hub=ttt, content_profile="adjacency_test",
                                    content={"dialog": "Human: hello\nLLM: hi", "trace_pairs": []})
    subject = SubjectPurpose(hub=ttt, participant=subject_p)
    reviewer = ReviewerPurpose(hub=ttt, participant=reviewer_p)
    socratic = SocraticElicitationPurpose(
        hub=ttt,
        protocol=protocol,
        adjacency_purpose=adjacency_p,
    )
    watcher = WatchPurpose()

    # Registration order matters: all Purposes that react to downstream events
    # must be registered before the Purpose that triggers the chain.
    # AdjacencyPurpose.start_turn() fires CTO_STARTED synchronously during its
    # PURPOSE_STARTED handler, which immediately triggers SocraticElicitationPurpose
    # to send the first StimulusEvent. Subject and Reviewer must already be
    # registered to receive that stimulus, so the order is:
    #   subject, reviewer, socratic -> adjacency_p (triggers CTO_STARTED + full chain)
    # All Purposes must be registered before AdjacencyPurpose, because
    # start_purpose(adjacency_p) triggers the entire chain synchronously:
    # PURPOSE_STARTED -> start_turn -> CTO_STARTED -> first stimulus ->
    # subject responds -> reviewer responds -> ProtocolCompletedEvent -> session closes.
    await ttt.start_purpose(subject)
    await ttt.start_purpose(reviewer)
    await ttt.start_purpose(socratic)
    await ttt.start_purpose(watcher)
    await ttt.start_purpose(adjacency_p)

    assert len(completed) == 1, "ProtocolCompletedEvent not received"
