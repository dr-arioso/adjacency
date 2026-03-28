"""Built-in source monitoring annotation workflow for Adjacency."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal
from uuid import UUID, uuid4

from turnturnturn.base_purpose import SessionOwnerPurpose
from turnturnturn.delta import Delta
from turnturnturn.events import (
    HubEvent,
    HubEventType,
    ProposeDelta,
    ProposeDeltaPayload,
    PurposeEventType,
)

from adjacency.events import (
    WORKFLOW_COMPLETED,
    WorkflowCompleted,
    WorkflowCompletedPayload,
)
from adjacency.events import register_all as register_events
from adjacency.interaction_renderer import InteractionRenderer
from adjacency.profiles import LEXICAL_PROFILE_ID
from adjacency.profiles import register as register_profiles

SOURCE_MONITORING_NAMESPACE = "adjacency.source_monitoring"
SOURCE_MONITORING_WORKFLOW = "source_monitoring_annotation"
RESERVED_SELECTIONS = {"blank", "unknown", "escalate"}
SOURCE_MONITORING_UNKNOWN = "unknown"


def _now_ms() -> int:
    return int(time.time() * 1000)


@dataclass(frozen=True)
class SpeakerShortcut:
    """A speaker legend entry with the shortcut displayed to the annotator."""

    session_speaker_id: str
    display_label: str
    shortcut: str


@dataclass(frozen=True)
class SessionHeader:
    """Header state shown above the annotation surface."""

    workflow_name: str
    session_code: str | None
    source_label: str | None
    progress_label: str


@dataclass(frozen=True)
class InstructionPanel:
    """Persistent instructions and shortcut legend."""

    title: str
    body: tuple[str, ...]
    speaker_shortcuts: tuple[SpeakerShortcut, ...]


@dataclass(frozen=True)
class InterfaceAffordances:
    """Declarative UI affordances for an interaction surface."""

    editable_after_submit: bool = False
    visible_controls: frozenset[str] = field(
        default_factory=lambda: frozenset(
            {
                "speaker_choices",
                "unknown",
                "leave_blank",
                "request_review",
                "submit",
                "complete",
                "navigation",
            }
        )
    )
    required_controls: frozenset[str] = field(
        default_factory=lambda: frozenset({"speaker_choices", "submit"})
    )
    control_labels: dict[str, str] = field(
        default_factory=lambda: {
            "unknown": "Unknown",
            "leave_blank": "Leave blank",
            "request_review": "Request review",
            "submit": "Submit",
            "complete": "Complete",
            "navigate_up": "Previous",
            "navigate_down": "Next",
        }
    )
    shortcut_hints: dict[str, str] = field(
        default_factory=lambda: {
            "leave_blank": "Space",
            "unknown": "U",
            "request_review": "R",
            "submit": "Ctrl+Enter",
            "navigate_up": "Up",
            "navigate_down": "Down",
        }
    )


@dataclass(frozen=True)
class SourceMonitoringInputState:
    """Persisted state of protocol-defined input controls for a turn."""

    selection: str
    request_review: bool = False


@dataclass(frozen=True)
class TranscriptItemState:
    """Renderer-facing state for a single lexical turn."""

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
class TranscriptState:
    """Transcript roller state with a single focused utterance."""

    active_index: int
    frontier_index: int
    items: tuple[TranscriptItemState, ...]


@dataclass(frozen=True)
class FooterState:
    """Immediate next-step and completion state."""

    message: str
    can_complete: bool
    completion_block_reason: str | None


@dataclass(frozen=True)
class SourceMonitoringRenderRequest:
    """Source-monitoring-specific snapshot published to an interaction surface."""

    session: SessionHeader
    instructions: InstructionPanel
    affordances: InterfaceAffordances
    transcript: TranscriptState
    footer: FooterState


@dataclass(frozen=True)
class SourceMonitoringIntent:
    """User intent emitted from a source monitoring surface."""

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


@dataclass(frozen=True)
class SourceMonitoringSubmission:
    """A pending provenance write for a single annotated lexical turn."""

    source_turn_id: str
    ordinal: int
    state: SourceMonitoringInputState


@dataclass(frozen=True)
class SourceMonitoringTransition:
    """Controller output after applying a renderer intent."""

    submission: SourceMonitoringSubmission | None = None
    completed: bool = False


@dataclass
class _DraftTurnState:
    """Mutable controller-local state for one lexical turn."""

    source_turn_id: str
    ordinal: int
    utterance: str
    raw_source_tag: str | None
    viewed: bool = False
    draft_selection: str | None = None
    draft_request_review: bool = False
    persisted_state: SourceMonitoringInputState | None = None


def _speaker_shortcuts(count: int) -> tuple[str, ...]:
    """Return spaced numeric shortcuts for a small speaker roster."""
    if count <= 0:
        return ()
    if count == 1:
        return ("1",)
    if count == 2:
        return ("1", "0")
    if count == 3:
        return ("1", "5", "0")
    if count == 4:
        return ("1", "3", "7", "0")
    if count == 5:
        return ("1", "3", "5", "7", "0")
    base = ["1", "3", "5", "7", "9", "0", "2", "4", "6", "8"]
    return tuple(base[:count])


def _default_instructions() -> tuple[str, ...]:
    """Return the default instruction copy for source monitoring sessions."""
    return (
        "You will see one utterance at a time from a multi-turn interaction.",
        "Assign the utterance to the best available speaker when you can.",
        "Use Unknown when the available evidence is insufficient.",
        "Use Leave blank only to skip for now and return later.",
        "Request review when you want a second pass on a submitted item.",
    )


class SourceMonitoringWorkflowController:
    """Authoritative state machine for the source monitoring workflow."""

    def __init__(
        self,
        *,
        speakers: list[dict[str, Any]],
        turns: list[dict[str, Any]],
        session_code: str | None,
        source_label: str | None,
        affordances: InterfaceAffordances | None = None,
    ) -> None:
        """Initialize the authoritative workflow state for one imported CTO."""
        if not speakers:
            raise ValueError("source monitoring requires at least one speaker")
        if not turns:
            raise ValueError("source monitoring requires at least one turn")
        self._speakers = [dict(speaker) for speaker in speakers]
        self._speaker_ids = {
            str(speaker["session_speaker_id"]) for speaker in self._speakers
        }
        self._speaker_shortcuts = tuple(
            SpeakerShortcut(
                session_speaker_id=str(speaker["session_speaker_id"]),
                display_label=str(speaker["display_label"]),
                shortcut=shortcut,
            )
            for speaker, shortcut in zip(
                self._speakers, _speaker_shortcuts(len(self._speakers)), strict=False
            )
        )
        self._turns = [
            _DraftTurnState(
                source_turn_id=str(turn["source_turn_id"]),
                ordinal=int(turn["ordinal"]),
                utterance=str(turn["utterance"]),
                raw_source_tag=(
                    str(turn["raw_source_tag"]) if turn.get("raw_source_tag") else None
                ),
            )
            for turn in turns
        ]
        self._session_code = session_code
        self._source_label = source_label
        self._affordances = affordances or InterfaceAffordances()
        self._focus_index = 0
        self._frontier_index = 0
        self._turns[0].viewed = True
        self._footer_message = "Choose a speaker, mark Unknown, or skip this item."

    @property
    def speaker_shortcuts(self) -> tuple[SpeakerShortcut, ...]:
        """Expose stable speaker shortcut assignments for renderers."""
        return self._speaker_shortcuts

    def snapshot(self) -> SourceMonitoringRenderRequest:
        """Return an immutable renderer snapshot for the current controller state."""
        submitted_count = sum(
            1 for turn in self._turns if turn.persisted_state is not None
        )
        can_complete = self._frontier_index == len(self._turns) - 1
        completion_block_reason = None
        if not can_complete:
            completion_block_reason = "View every utterance before completing."
        elif self._first_incomplete_index() is not None:
            completion_block_reason = "Complete every blank utterance before finishing."

        items = []
        for index, turn in enumerate(self._turns):
            if index == self._focus_index:
                status = "active"
            elif not turn.viewed:
                status = "unviewed"
            elif turn.persisted_state is None:
                status = "blank"
            else:
                status = "submitted"
            selection_editable = (
                turn.persisted_state is None or self._affordances.editable_after_submit
            )
            request_review_editable = True
            items.append(
                TranscriptItemState(
                    source_turn_id=turn.source_turn_id,
                    ordinal=turn.ordinal,
                    utterance=turn.utterance,
                    raw_source_tag=turn.raw_source_tag,
                    status=status,
                    viewed=turn.viewed,
                    selection_editable=selection_editable,
                    request_review_editable=request_review_editable,
                    current_selection=turn.draft_selection,
                    request_review=turn.draft_request_review,
                )
            )

        return SourceMonitoringRenderRequest(
            session=SessionHeader(
                workflow_name=SOURCE_MONITORING_WORKFLOW,
                session_code=self._session_code,
                source_label=self._source_label,
                progress_label=f"{submitted_count} / {len(self._turns)} submitted",
            ),
            instructions=InstructionPanel(
                title="Instructions",
                body=_default_instructions(),
                speaker_shortcuts=self._speaker_shortcuts,
            ),
            affordances=self._affordances,
            transcript=TranscriptState(
                active_index=self._focus_index,
                frontier_index=self._frontier_index,
                items=tuple(items),
            ),
            footer=FooterState(
                message=self._footer_message,
                can_complete=can_complete,
                completion_block_reason=completion_block_reason,
            ),
        )

    def handle_intent(
        self, intent: SourceMonitoringIntent
    ) -> SourceMonitoringTransition:
        """Apply one renderer intent and return any required provenance action."""
        if intent.kind == "select_speaker":
            return self._select_speaker(intent.selection)
        if intent.kind == "select_unknown":
            return self._select_unknown()
        if intent.kind == "leave_blank":
            return self._leave_blank()
        if intent.kind == "toggle_request_review":
            return self._toggle_request_review()
        if intent.kind == "submit_annotation":
            return self._submit_annotation()
        if intent.kind == "navigate_up":
            return self._navigate(-1)
        if intent.kind == "navigate_down":
            return self._navigate(1)
        if intent.kind == "complete_workflow":
            return self._complete_workflow()
        raise ValueError(f"unsupported source monitoring intent {intent.kind!r}")

    def _select_speaker(self, selection: str | None) -> SourceMonitoringTransition:
        """Select a concrete speaker for the active utterance."""
        if selection is None:
            raise ValueError("select_speaker requires a speaker id")
        if selection not in self._speaker_ids:
            raise ValueError(f"unknown speaker id {selection!r}")
        turn = self._current_turn()
        if not self._selection_editable(turn):
            self._footer_message = "Submitted speaker selections are read-only."
            return SourceMonitoringTransition()
        turn.draft_selection = selection
        self._footer_message = f"Selected {selection}. Submit to persist."
        return SourceMonitoringTransition()

    def _select_unknown(self) -> SourceMonitoringTransition:
        """Mark the active utterance as complete but unknown."""
        turn = self._current_turn()
        if not self._selection_editable(turn):
            self._footer_message = "Submitted speaker selections are read-only."
            return SourceMonitoringTransition()
        turn.draft_selection = SOURCE_MONITORING_UNKNOWN
        self._footer_message = "Marked Unknown. Submit to persist."
        return SourceMonitoringTransition()

    def _leave_blank(self) -> SourceMonitoringTransition:
        """Skip the active utterance without creating provenance."""
        turn = self._current_turn()
        if turn.persisted_state is not None and not self._selection_editable(turn):
            self._footer_message = "Submitted speaker selections are read-only."
            return SourceMonitoringTransition()
        turn.draft_selection = None
        self._footer_message = "Skipped for now."
        return self._leave_current_turn(target_index=self._next_forward_index())

    def _toggle_request_review(self) -> SourceMonitoringTransition:
        """Toggle the persisted review flag for the focused utterance draft."""
        turn = self._current_turn()
        turn.draft_request_review = not turn.draft_request_review
        if turn.draft_request_review:
            self._footer_message = "Request review enabled for this item."
        else:
            self._footer_message = "Request review disabled for this item."
        return SourceMonitoringTransition()

    def _submit_annotation(self) -> SourceMonitoringTransition:
        """Persist the active utterance if it currently has submittable state."""
        turn = self._current_turn()
        protocol_state = self._protocol_input_state(turn)
        if protocol_state is None:
            self._footer_message = "Nothing to submit; skipped for now."
            return self._leave_current_turn(target_index=self._next_forward_index())
        self._footer_message = "Annotation submitted."
        return self._leave_current_turn(
            target_index=self._next_forward_index(),
            force_submit=True,
        )

    def _navigate(self, step: int) -> SourceMonitoringTransition:
        """Move through already-viewed utterances while preserving semantics."""
        target = self._focus_index + step
        if target < 0 or target > self._frontier_index:
            self._footer_message = "No more viewed utterances in that direction."
            return SourceMonitoringTransition()
        if not self._turns[target].viewed:
            self._footer_message = "You can only move through viewed utterances."
            return SourceMonitoringTransition()
        direction = "previous" if step < 0 else "next"
        self._footer_message = f"Moved to the {direction} viewed utterance."
        return self._leave_current_turn(target_index=target)

    def _complete_workflow(self) -> SourceMonitoringTransition:
        """Attempt completion, focusing the first incomplete item when blocked."""
        transition = self._leave_current_turn(target_index=self._focus_index)
        first_incomplete = self._first_incomplete_index()
        if self._frontier_index < len(self._turns) - 1:
            self._focus_index = self._frontier_index
            self._footer_message = "View every utterance before completing."
            return transition
        if first_incomplete is not None:
            self._focus_index = first_incomplete
            self._footer_message = "Finish every blank utterance before completing."
            return transition
        self._footer_message = "Workflow complete."
        return SourceMonitoringTransition(
            submission=transition.submission,
            completed=True,
        )

    def _leave_current_turn(
        self,
        *,
        target_index: int | None,
        force_submit: bool = False,
    ) -> SourceMonitoringTransition:
        """Apply leave-item semantics, including conditional resubmission."""
        turn = self._current_turn()
        submission = self._maybe_prepare_submission(turn, force_submit=force_submit)
        self._mark_viewed(self._focus_index)
        if target_index is not None:
            self._focus_index = target_index
            self._mark_viewed(target_index)
            if target_index > self._frontier_index:
                self._frontier_index = target_index
        return SourceMonitoringTransition(submission=submission)

    def _maybe_prepare_submission(
        self,
        turn: _DraftTurnState,
        *,
        force_submit: bool,
    ) -> SourceMonitoringSubmission | None:
        """Return a submission only when the item is submittable and dirty."""
        protocol_state = self._protocol_input_state(turn)
        if protocol_state is None:
            return None
        if not force_submit and protocol_state == turn.persisted_state:
            return None
        turn.persisted_state = protocol_state
        return SourceMonitoringSubmission(
            source_turn_id=turn.source_turn_id,
            ordinal=turn.ordinal,
            state=protocol_state,
        )

    def _protocol_input_state(
        self, turn: _DraftTurnState
    ) -> SourceMonitoringInputState | None:
        """Project a draft turn into the persisted protocol-defined input state."""
        if turn.draft_selection is None:
            return None
        return SourceMonitoringInputState(
            selection=turn.draft_selection,
            request_review=turn.draft_request_review,
        )

    def _selection_editable(self, turn: _DraftTurnState) -> bool:
        """Report whether the active speaker selection is editable in this workflow."""
        return turn.persisted_state is None or self._affordances.editable_after_submit

    def _mark_viewed(self, index: int) -> None:
        """Mark one transcript item as viewed."""
        self._turns[index].viewed = True

    def _current_turn(self) -> _DraftTurnState:
        """Return the currently focused mutable turn state."""
        return self._turns[self._focus_index]

    def _next_forward_index(self) -> int | None:
        """Return the next forward index in the strict linear workflow path."""
        if self._focus_index < self._frontier_index:
            return self._focus_index + 1
        if self._frontier_index < len(self._turns) - 1:
            return self._frontier_index + 1
        return None

    def _first_incomplete_index(self) -> int | None:
        """Return the first still-blank item, if any."""
        for index, turn in enumerate(self._turns):
            if turn.persisted_state is None:
                return index
        return None


class ScriptedSourceMonitoringRenderer(
    InteractionRenderer[SourceMonitoringRenderRequest, SourceMonitoringIntent]
):
    """Deterministic renderer that drives the workflow from scripted selections."""

    def __init__(self, decisions: list[str]) -> None:
        """Create a scripted renderer from a fixed sequence of selections."""
        if not decisions:
            raise ValueError("ScriptedSourceMonitoringRenderer requires decisions")
        self._decisions = decisions
        self._decision_index = 0
        self._intent_queue: list[SourceMonitoringIntent] = []
        self._prepared_turns: set[str] = set()

    async def publish(self, request: SourceMonitoringRenderRequest) -> None:
        """Queue the next scripted intents for the currently active item."""
        if self._intent_queue:
            return
        active = request.transcript.items[request.transcript.active_index]
        if (
            request.footer.can_complete
            and request.footer.completion_block_reason is None
            and all(item.viewed for item in request.transcript.items)
        ):
            self._intent_queue.append(SourceMonitoringIntent(kind="complete_workflow"))
            return
        if active.source_turn_id in self._prepared_turns:
            return
        decision = self._decisions[min(self._decision_index, len(self._decisions) - 1)]
        self._decision_index += 1
        self._prepared_turns.add(active.source_turn_id)
        if decision == "blank":
            self._intent_queue.append(SourceMonitoringIntent(kind="leave_blank"))
            return
        if decision == SOURCE_MONITORING_UNKNOWN:
            self._intent_queue.append(SourceMonitoringIntent(kind="select_unknown"))
        else:
            self._intent_queue.append(
                SourceMonitoringIntent(
                    kind="select_speaker",
                    source_turn_id=active.source_turn_id,
                    selection=decision,
                )
            )
        self._intent_queue.append(SourceMonitoringIntent(kind="submit_annotation"))

    async def next_intent(self) -> SourceMonitoringIntent:
        """Return the next scripted intent, waiting until one is queued."""
        while not self._intent_queue:
            await asyncio.sleep(0)
        return self._intent_queue.pop(0)


class ConsoleSourceMonitoringRenderer(
    InteractionRenderer[SourceMonitoringRenderRequest, SourceMonitoringIntent]
):
    """Console fallback implementing the same workflow contract as the web UI."""

    def __init__(self) -> None:
        """Create the console fallback renderer."""
        self._request: SourceMonitoringRenderRequest | None = None

    async def publish(self, request: SourceMonitoringRenderRequest) -> None:
        """Store the latest snapshot for the next console prompt round."""
        self._request = request

    async def next_intent(self) -> SourceMonitoringIntent:
        """Prompt for one console command and convert it into a renderer intent."""
        if self._request is None:
            raise RuntimeError("console renderer requires an initial snapshot")
        request = self._request
        active = request.transcript.items[request.transcript.active_index]
        speaker_lines = "\n".join(
            f"  [{entry.shortcut}] {entry.display_label}"
            for entry in request.instructions.speaker_shortcuts
        )
        prompt = (
            f"\n{request.session.workflow_name}\n"
            f"Session: {request.session.session_code or '<none>'}\n"
            f"Progress: {request.session.progress_label}\n"
            f"Turn {active.ordinal}: {active.utterance}\n"
            f"Raw source: {active.raw_source_tag or '<none>'}\n"
            f"Current selection: {active.current_selection or '<blank>'}\n"
            f"Request review: {'yes' if active.request_review else 'no'}\n"
            f"Speakers:\n{speaker_lines}\n"
            "Commands: speaker shortcut, u=unknown, <space>=blank, "
            "r=toggle review, s=submit, up/down=navigate, c=complete\n> "
        )
        while True:
            response = await asyncio.to_thread(input, prompt)
            if response == " ":
                return SourceMonitoringIntent(kind="leave_blank")
            normalized = response.strip().lower()
            if normalized == "":
                continue
            if normalized == "u":
                return SourceMonitoringIntent(kind="select_unknown")
            if normalized == "r":
                return SourceMonitoringIntent(kind="toggle_request_review")
            if normalized == "s":
                return SourceMonitoringIntent(kind="submit_annotation")
            if normalized == "c":
                return SourceMonitoringIntent(kind="complete_workflow")
            if normalized == "up":
                return SourceMonitoringIntent(kind="navigate_up")
            if normalized == "down":
                return SourceMonitoringIntent(kind="navigate_down")
            if normalized == "space":
                return SourceMonitoringIntent(kind="leave_blank")
            for entry in request.instructions.speaker_shortcuts:
                if normalized == entry.shortcut:
                    return SourceMonitoringIntent(
                        kind="select_speaker",
                        source_turn_id=active.source_turn_id,
                        selection=entry.session_speaker_id,
                    )
            print("Unrecognized command.")


ConsoleSourceMonitoringBackend = ConsoleSourceMonitoringRenderer
ScriptedSourceMonitoringBackend = ScriptedSourceMonitoringRenderer


class SourceMonitoringAnnotatorPurpose(SessionOwnerPurpose):
    """Combined session owner and annotator for the built-in source monitoring flow."""

    name = SOURCE_MONITORING_NAMESPACE

    def __init__(
        self,
        *,
        source_locator: str,
        renderer: InteractionRenderer[
            SourceMonitoringRenderRequest, SourceMonitoringIntent
        ],
        session_code: str | None = None,
        source_kind: str = "cto_json",
        affordances: InterfaceAffordances | None = None,
    ) -> None:
        """Create the combined owner/annotator for a source monitoring session."""
        super().__init__()
        self.id: UUID = uuid4()
        self._source_locator = source_locator
        self._source_kind = source_kind
        self._renderer = renderer
        self._affordances = affordances
        self._session_id: UUID = uuid4()
        self._session_code = session_code
        self.turn_id: UUID | None = None
        self._requested = False
        self._annotated = False
        self._closing_requested = False

    @property
    def session_id(self) -> UUID:
        """Expose the owner-managed live session id."""
        return self._session_id

    async def start_session(self) -> None:
        """Kick off the workflow by asking persistence to import the CTO JSON source."""
        if self._requested:
            return
        self._requested = True
        await self.request_cto(
            session_id=str(self._session_id),
            source_kind=self._source_kind,
            source_locator=self._source_locator,
            session_code=self._session_code,
        )

    async def _handle_event(self, event: HubEvent) -> None:
        """Drive annotation start and completion handling for this workflow."""
        if event.event_type == HubEventType.CTO_STARTED and not self._annotated:
            payload_dict = event.payload.as_dict()
            cto_index = payload_dict.get("cto_index")
            if not isinstance(cto_index, dict):
                return
            if cto_index.get("session_id") != str(self._session_id):
                return
            profile = cto_index.get("content_profile")
            if not isinstance(profile, dict) or profile.get("id") != LEXICAL_PROFILE_ID:
                return
            turn_id = cto_index.get("turn_id")
            if not isinstance(turn_id, str):
                return
            self.turn_id = UUID(turn_id)
            await self._annotate_live_cto(self.turn_id)
            return

        if event.event_type == WORKFLOW_COMPLETED and not self._closing_requested:
            payload_dict = event.payload.as_dict()
            session_id = payload_dict.get("session_id")
            if session_id != str(self._session_id):
                return
            self._closing_requested = True
            await self.request_session_end(str(self._session_id))

    async def _annotate_live_cto(self, turn_id: UUID) -> None:
        """Run the renderer/controller loop over the imported lexical CTO."""
        cto = self.hub.librarian.get_cto(turn_id)
        assert cto is not None, "cto_started should point at a live canonical CTO"
        controller = SourceMonitoringWorkflowController(
            speakers=cto.content["speakers"],
            turns=cto.content["turns"],
            session_code=self._session_code,
            source_label=Path(self._source_locator).name,
            affordances=self._affordances,
        )

        while True:
            await self._renderer.publish(controller.snapshot())
            intent = await self._renderer.next_intent()
            transition = controller.handle_intent(intent)
            if transition.submission is not None:
                await self._emit_annotation_delta(
                    turn_id=turn_id, submission=transition.submission
                )
            if transition.completed:
                self._annotated = True
                await self._emit_workflow_completed(final_state="annotation_completed")
                return

    def _normalize_selection(
        self, selection: str, speakers: list[dict[str, Any]]
    ) -> str:
        """Normalize one raw scripted selection against the speaker roster."""
        normalized = selection.strip() or "blank"
        if normalized in RESERVED_SELECTIONS:
            return normalized
        valid_ids = {speaker["session_speaker_id"] for speaker in speakers}
        if normalized in valid_ids:
            return normalized
        raise ValueError(
            f"invalid source monitoring selection {normalized!r}; "
            f"expected one of {sorted(valid_ids | RESERVED_SELECTIONS)!r}"
        )

    async def _emit_annotation_delta(
        self,
        *,
        turn_id: UUID,
        submission: SourceMonitoringSubmission,
    ) -> None:
        delta = Delta(
            delta_id=uuid4(),
            session_id=self._session_id,
            turn_id=turn_id,
            purpose_name=self.name,
            purpose_id=self.id,
            patch={
                submission.source_turn_id: [
                    {
                        "selection": submission.state.selection,
                        "request_review": submission.state.request_review,
                        "ordinal": submission.ordinal,
                    }
                ]
            },
        )
        event = ProposeDelta(
            event_type=PurposeEventType.PROPOSE_DELTA,
            event_id=uuid4(),
            created_at_ms=_now_ms(),
            purpose_id=self.id,
            purpose_name=self.name,
            hub_token=self._require_token(),
            payload=ProposeDeltaPayload(delta=delta),
        )
        await self.hub.take_turn(event)

    async def _emit_workflow_completed(self, *, final_state: str) -> None:
        """Emit the standard workflow terminal signal for this session."""
        event = WorkflowCompleted(
            purpose_id=self.id,
            purpose_name=self.name,
            hub_token=self._require_token(),
            payload=WorkflowCompletedPayload(
                final_state=final_state,
                session_id=str(self._session_id),
            ),
        )
        await self.hub.take_turn(event)


@dataclass
class SourceMonitoringSession:
    """Minimal session wrapper for the built-in source monitoring workflow."""

    annotator_purpose: SourceMonitoringAnnotatorPurpose

    async def start(self) -> None:
        """Register source-monitoring events/profiles and start the owner purpose."""
        register_events()
        register_profiles()
        await self.annotator_purpose.start_session()


def assemble_source_monitoring_session(
    annotator_purpose: SourceMonitoringAnnotatorPurpose,
) -> SourceMonitoringSession:
    """Return a runnable session wrapper for the built-in source monitoring flow."""
    return SourceMonitoringSession(annotator_purpose=annotator_purpose)
