# Source Monitoring Web UI

This document defines the first web UI and renderer contract for
`source_monitoring_annotation`.

The goals are:

- implement a single-page annotation surface in NiceGUI
- preserve the existing mesh/provenance model
- keep workflow logic out of the UI layer
- define a renderer contract that can later support console, remote-human,
  and API-facing interaction surfaces

This is an implementation spec, not a product-vision note.

## Scope

In scope for v1:

- local single-user annotation only
- NiceGUI web interface
- one active utterance at a time
- incremental per-utterance persistence
- `request review` as a persisted flag only
- strict completion gating

Explicitly deferred:

- multi-user coordination
- resumable `save for later`
- actual review workflow execution
- editable submitted speaker assignments
- bulk transcript navigation/jump list
- output/export views

## Architecture Boundary

`InteractionRenderer` is a bidirectional adapter with two stable seams:

- Purpose-facing contract
- backend/surface-facing contract

The workflow Purpose must not know whether the interaction surface is:

- NiceGUI
- console/TUI
- remote human session
- API client
- LLM-backed interaction

The UI/surface layer must not know workflow internals beyond the structured
request snapshot it is asked to render.

The intended shape is:

```text
Purpose <-> InteractionRenderer <-> Backend / Surface
```

For this workflow, the concrete backend/surface is NiceGUI.

## Renderer Contract

The renderer contract is:

- snapshot in
- one user intent out

The renderer receives a full workflow-state snapshot plus declarative UI
affordance config. It returns one structured user intent at a time.

The renderer must not mutate authoritative workflow state directly.

### Purpose-Facing Request Shape

The first concrete request type should look conceptually like this:

```python
@dataclass(frozen=True)
class SourceMonitoringRenderRequest:
    session: SessionHeader
    instructions: InstructionPanel
    affordances: InterfaceAffordances
    transcript: TranscriptState
    footer: FooterState
```

With the following conceptual substructures:

```python
@dataclass(frozen=True)
class SessionHeader:
    workflow_name: str
    session_code: str | None
    source_label: str | None
    progress_label: str


@dataclass(frozen=True)
class InstructionPanel:
    title: str
    body: list[str]
    speaker_shortcuts: list[SpeakerShortcut]


@dataclass(frozen=True)
class InterfaceAffordances:
    editable_after_submit: bool
    visible_controls: frozenset[str]
    required_controls: frozenset[str]
    control_labels: dict[str, str]
    shortcut_hints: dict[str, str]


@dataclass(frozen=True)
class TranscriptState:
    active_index: int
    frontier_index: int
    items: list[TranscriptItemState]


@dataclass(frozen=True)
class TranscriptItemState:
    source_turn_id: str
    ordinal: int
    utterance: str
    raw_source_tag: str | None
    status: Literal["unviewed", "active", "submitted", "blank"]
    viewed: bool
    selection_editable: bool
    request_review_editable: bool
    current_selection: str | None
    request_review: bool


@dataclass(frozen=True)
class FooterState:
    message: str
    can_complete: bool
    completion_block_reason: str | None
```

The renderer should be able to render the UI entirely from this snapshot.

### User Intent Shape

The renderer returns one of a small set of structured intents:

```python
@dataclass(frozen=True)
class RendererIntent:
    kind: Literal[
        "select_speaker",
        "select_unknown",
        "leave_blank",
        "toggle_request_review",
        "submit_annotation",
        "navigate_up",
        "navigate_down",
        "complete_workflow",
    ]
    source_turn_id: str | None = None
    selection: str | None = None
```

Rules:

- `select_speaker` selects a speaker candidate for the active item only
- `select_unknown` chooses the explicit complete-but-unknown state
- `leave_blank` bypasses the active item without creating provenance
- `toggle_request_review` toggles review for the focused/viewed item
- `submit_annotation` creates a new provenance record
- `navigate_up` and `navigate_down` do not create provenance records
- `complete_workflow` requests completion gating and validation

## Declarative vs Code-Owned Behavior

The UI should not hard-code which controls exist. The request snapshot should
declare:

- which controls are visible
- which controls are required
- the visible labels/help text
- keyboard shortcut hints
- workflow-level `editable_after_submit`

However, workflow logic remains code-owned:

- active item progression
- completion rules
- navigation rules
- provenance emission timing
- normalization
- latest-write-wins semantics

YAML/config is appropriate later for:

- instructions text
- labels
- button visibility
- shortcut hints

It is not appropriate in v1 for:

- validation logic
- provenance rules
- state machine transitions

## Single-Page Layout

The first interface is a single-page NiceGUI layout with four regions:

### Header

The header should show:

- workflow name
- session code
- source label if present
- progress, such as `3 / 12 submitted`

### Right-Side Instructions Panel

The right panel should persist while the user annotates. It should contain:

- short instructions
- speaker legend
- shortcut hints
- brief rule reminders

Example reminders:

- choose the speaker when clear
- use blank only to skip for now
- request review when uncertain

### Central Transcript Roller

The center of the interface is the primary work area.

Design intent:

- active utterance sits in the center like the inspection window in a slot
  machine roller
- previously viewed utterances remain visible above/below, dimmed
- unviewed utterances are not yet scroll-targets

Behavior:

- initial state may show a spinner while waiting for content
- once content is available, the first utterance becomes active
- after submit, the utterance rolls upward and becomes read-only by default
- previously blank items may later be filled and submitted

### Footer / Immediate Next-Step Area

The footer should show:

- immediate next instruction
- validation or completion messages
- `Submit`
- `Complete`
- later, `Save for later` when that feature exists

## Interaction Model

### Speaker Selection

Speaker choices use numeric shortcut keys that are intentionally separated
from each other.

Examples:

- two speakers: `1` and `0`
- three speakers: `1`, `5`, and `0`

The visible UI should show those bindings next to the labels.

### Unknown / Blank / Review / Submit

Bindings:

- `u` -> `Unknown`
- `Space` -> `Leave blank`
- `r` -> toggle `Request review`
- `Ctrl+Enter` -> submit annotation

`Space` is reserved for blank bypass inside the annotation workspace and
must not also activate a focused submit button.

The UI may also expose:

- click/tap submit
- tooltip hints
- secondary accelerator hints such as `Alt+S` / `Option+S`

But the primary keyboard submit path in v1 is `Ctrl+Enter`.

### Navigation

Bindings:

- `Up` -> focus previous viewed item
- `Down` -> focus next viewed item
- mouse wheel -> move through the viewed roller when focused

Rules:

- navigation is strict linear progression with limited review
- the user cannot jump ahead to unviewed items
- previously viewed items may be revisited
- revisiting does not itself emit provenance

## Submission and Provenance

The authoritative record is incremental, not batch-at-end.

Each submitted annotation emits a new provenance record.

The first persisted payload shape should contain:

- `source_turn_id`
- `ordinal`
- `selection`
- `request_review`

This is intentionally small. The full transcript and source content remain in
the CTO; the per-submit record captures the annotation decision.

### Rules

- If the user selects a speaker and submits, emit one annotation delta.
- If the user chooses blank and advances, do not emit an event.
- If the user later returns to a blank item and submits a speaker, emit one
  new annotation delta.
- If the user revisits a submitted item and toggles `request_review` on, then
  leaves that item, re-submit that item with the review flag set.
- Re-submitting creates a new provenance record.
- Reviewing/navigating alone does not.
- Latest write wins for the authoritative record.

## Editability Rules

Workflow-level setting:

- `editable_after_submit: bool`

For `source_monitoring_annotation` v1:

- `editable_after_submit = false`

That means:

- speaker choice is not editable after submit
- `request_review` can still be toggled on after submit
- previously blank items are still submittable because they were never
  submitted in the first place

## Completion Semantics

Completion is strict.

`Complete` becomes meaningful only when every utterance has a non-blank final
state.

Rules:

- `unknown` counts as complete
- `request_review=true` still counts as complete
- `blank` does not count as complete
- if the user clicks `Complete` while blanks remain, the UI focuses the first
  blank item and shows a completion-block message
- once the workflow is truly complete, it emits `WorkflowCompleted`

## NiceGUI Notes

NiceGUI is the v1 surface because it is:

- Python-native
- easy to run locally
- suitable for remote sessions later
- sufficient for a stateful single-page tool without introducing a separate
  frontend build system yet

This document does not require the eventual renderer abstraction to remain
NiceGUI-specific. The request/intent contract is the portability seam.

## Deferred Questions

The following stay out of the first implementation:

- resumable saved sessions
- multi-user annotation or adjudication
- actual review queue execution
- rich typo-suggestion UX for free-text annotators
- jump-to-index transcript navigation
- transcript editing after submit

These should be handled in later workflow-specific follow-on specs rather than
folded into the first NiceGUI implementation.
