"""Protocol dataclass and loader for socratic_elicitation protocol YAML.

Provides parsing and validation for protocol YAML files that define the
socratic escalation ladder, gestalt questions, control baseline, and
role-specific framing for a study session.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import yaml


@dataclass(frozen=True)
class LadderStep:
    """A single step in the socratic escalation ladder.

    Represents a state in the protocol FSM where the Subject receives
    a stimulus variant and the Reviewer provides a yes/no/escalate verdict.

    Attributes:
        key: Unique identifier for this ladder step.
        subject_stimulus_variants: List of variant strings for the stimulus;
            one is selected at random per elicitation.
        reviewer_question: Question text for the Reviewer's assessment.
        requires: List of ladder step keys that must be resolved (answered 'yes')
            before this step becomes accessible. Enforces a partial ordering.
    """

    key: str
    subject_stimulus_variants: list[str]
    reviewer_question: str
    requires: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class GestaltStep:
    """A gestalt (holistic) step addressed to a specific role.

    A higher-level question that tests understanding of the entire exchange
    after the ladder is resolved.

    Attributes:
        key: Unique identifier for this gestalt step.
        addressed_to: Role name ("subject" or "reviewer") receiving the question.
        stimulus: The question or prompt text.
        reviewer_question: Reviewer assessment question if addressed_to is "subject",
            or the question the reviewer answers if addressed_to is "reviewer".
    """

    key: str
    addressed_to: str
    stimulus: str
    reviewer_question: str


@dataclass(frozen=True)
class ControlSection:
    """Subject prompt and review question for control (baseline) pairs.

    Used for comparison with experimental pairs; control pairs do not
    carry canonical_misalignment.

    Attributes:
        subject_stimulus_variants: List of variant strings for the control stimulus.
        reviewer_question: Question the Reviewer answers for control pairs.
    """

    subject_stimulus_variants: list[str]
    reviewer_question: str


@dataclass(frozen=True)
class Escalation:
    """Escalation policy: max attempts per ladder state and exhaustion behavior.

    Attributes:
        max_attempts_per_state: Maximum number of times the Reviewer can return
            "escalate" for a single ladder step before exhaustion is triggered.
        on_exhaustion: Action to take when escalation is exhausted:
            "advance" moves to the next accessible ladder step,
            "terminal" ends the protocol immediately.
    """

    max_attempts_per_state: int
    on_exhaustion: str


@dataclass(frozen=True)
class Framing:
    """System-level framing text for each role.

    Provides system prompts and context that shape how the Subject and
    Reviewer approach their tasks.

    Attributes:
        subject_system: Optional system prompt for the Subject model.
        subject_context: Optional contextual preamble for the Subject.
        reviewer_system: Optional system prompt for the Reviewer model.
    """

    subject_system: str | None
    subject_context: str | None
    reviewer_system: str | None


@dataclass(frozen=True)
class Protocol:
    """Parsed, validated representation of a socratic_elicitation protocol YAML.

    This is the result of load_protocol() or load_protocol_file(); it contains
    all metadata and structural data needed to run a session.

    Attributes:
        protocol_type: Always "socratic_elicitation".
        framing: Role-specific system prompts and context.
        ladder: List of ladder steps in definition order.
        gestalt: List of gestalt steps to administer after ladder resolution.
        control: Control baseline section, or None if no control pairs.
        escalation: Escalation policy (max attempts, exhaustion behavior).
        completion_key: The ladder key that, when resolved to 'yes', completes the protocol.
        terminology: Mapping of placeholder strings to their definitions.
        variables: Mapping of template variables to their values.
    """

    protocol_type: str
    framing: Framing
    ladder: list[LadderStep]
    gestalt: list[GestaltStep]
    control: ControlSection | None
    escalation: Escalation
    completion_key: str
    terminology: dict[str, str]
    variables: dict[str, str]


def load_protocol(yaml_text: str) -> Protocol:
    """Parse and validate a protocol YAML string.

    Validates:
        - protocol type is "socratic_elicitation"
        - ladder requires ordering (no forward references)
        - completion_key exists in the ladder

    Args:
        yaml_text: The full protocol YAML as a string.

    Returns:
        A Protocol instance ready for use.

    Raises:
        ValueError: If the YAML is invalid, the protocol type is unsupported,
            a requires dependency is unmet, or completion_key is not found.
    """
    raw = yaml.safe_load(yaml_text)

    if raw.get("type") != "socratic_elicitation":
        raise ValueError(
            f"Protocol loader only supports type 'socratic_elicitation'; "
            f"got {raw.get('type')!r}"
        )

    # Framing
    f = raw.get("framing", {})
    subj = f.get("subject", {}) or {}
    framing = Framing(
        subject_system=subj.get("system"),
        subject_context=subj.get("context"),
        reviewer_system=(f.get("reviewer") or {}).get("system"),
    )

    # Ladder — validate requires: ordering
    declared_keys: set[str] = set()
    ladder_steps: list[LadderStep] = []
    for step_raw in raw.get("ladder", []):
        key = step_raw["key"]
        requires = step_raw.get("requires", []) or []
        for req in requires:
            if req not in declared_keys:
                raise ValueError(
                    f"Ladder step {key!r}: requires {req!r}, which is not yet declared "
                    f"(ordering violation or unknown ladder key)"
                )
        declared_keys.add(key)
        variants = step_raw.get("subject_stimulus", {}).get("variants", [])
        ladder_steps.append(
            LadderStep(
                key=key,
                subject_stimulus_variants=variants,
                reviewer_question=step_raw["reviewer_question"],
                requires=requires,
            )
        )

    # Gestalt
    gestalt_steps = [
        GestaltStep(
            key=g["key"],
            addressed_to=g["addressed_to"],
            stimulus=g["stimulus"],
            reviewer_question=g["reviewer_question"],
        )
        for g in raw.get("gestalt", []) or []
    ]

    # Control
    control_raw = raw.get("control")
    control = None
    if control_raw:
        control = ControlSection(
            subject_stimulus_variants=control_raw["subject_stimulus"]["variants"],
            reviewer_question=control_raw["reviewer_question"],
        )

    # Escalation
    esc_raw = raw["escalation"]
    escalation = Escalation(
        max_attempts_per_state=esc_raw["max_attempts_per_state"],
        on_exhaustion=esc_raw["on_exhaustion"],
    )

    # Completion
    completion_raw = raw["completion"]
    completion_key = (
        completion_raw["when"]
        if isinstance(completion_raw["when"], str)
        else completion_raw["when"][-1]
    )
    if completion_key not in declared_keys:
        raise ValueError(
            f"completion.when refers to unknown ladder key {completion_key!r}"
        )

    return Protocol(
        protocol_type="socratic_elicitation",
        framing=framing,
        ladder=ladder_steps,
        gestalt=gestalt_steps,
        control=control,
        escalation=escalation,
        completion_key=completion_key,
        terminology=raw.get("terminology", {}) or {},
        variables=raw.get("variables", {}) or {},
    )


def load_protocol_file(path: str) -> Protocol:
    """Read a protocol YAML file from disk and return a parsed Protocol.

    Args:
        path: Absolute or relative path to the protocol YAML file.

    Returns:
        A Protocol instance.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the YAML is invalid (see load_protocol for details).
    """
    with open(path) as f:
        return load_protocol(f.read())
