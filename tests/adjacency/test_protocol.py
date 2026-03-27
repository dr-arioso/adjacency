import textwrap

import pytest

from adjacency.protocol import load_protocol

MINIMAL_PROTOCOL_YAML = textwrap.dedent("""
    type: socratic_elicitation

    framing:
      subject:
        system: "You are a careful assistant."
        context: "Review this excerpt."
      reviewer:
        system: null

    ladder:
      - key: locus_visible
        subject_stimulus:
          variants:
            - "Do you notice anything unusual?"
        reviewer_question: "Did subject find anything?"

      - key: locus_identified
        requires: [locus_visible]
        subject_stimulus:
          variants:
            - "What specifically changed?"
        reviewer_question: "Correct locus?"

    escalation:
      max_attempts_per_state: 3
      on_exhaustion: advance

    completion:
      when: locus_identified
""")


def test_protocol_loads_ladder_keys():
    proto = load_protocol(MINIMAL_PROTOCOL_YAML)
    assert [s.key for s in proto.ladder] == ["locus_visible", "locus_identified"]


def test_protocol_loads_escalation():
    proto = load_protocol(MINIMAL_PROTOCOL_YAML)
    assert proto.escalation.max_attempts_per_state == 3
    assert proto.escalation.on_exhaustion == "advance"


def test_protocol_completion_key():
    proto = load_protocol(MINIMAL_PROTOCOL_YAML)
    assert proto.completion_key == "locus_identified"


def test_protocol_requires_ordering_violation_raises():
    """locus_identified requires locus_visible but appears before it — ordering violation."""

    import yaml

    raw = yaml.safe_load(MINIMAL_PROTOCOL_YAML)
    # Swap the ladder order: locus_identified first, locus_visible second
    raw["ladder"] = [
        {
            "key": "locus_identified",
            "requires": ["locus_visible"],
            "subject_stimulus": {"variants": ["What changed?"]},
            "reviewer_question": "Correct locus?",
        },
        {
            "key": "locus_visible",
            "subject_stimulus": {"variants": ["Notice anything?"]},
            "reviewer_question": "Found anything?",
        },
    ]

    bad_yaml = yaml.dump(raw)
    with pytest.raises(ValueError, match="not yet declared"):
        load_protocol(bad_yaml)


def test_protocol_requires_unknown_key_raises():
    """requires references a key that doesn't exist in the ladder."""
    import yaml

    raw = yaml.safe_load(MINIMAL_PROTOCOL_YAML)
    raw["ladder"][-1]["requires"] = ["nonexistent_key"]
    bad_yaml = yaml.dump(raw)
    with pytest.raises(ValueError, match="not yet declared|unknown"):
        load_protocol(bad_yaml)
