"""SocraticElicitationPurpose — ladder driver for ModeratedMesh sessions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID, uuid4

from turnturnturn.base_purpose import BasePurpose  # type: ignore[import-untyped]
from turnturnturn.events import HubEvent, HubEventType  # type: ignore[import-untyped]

from adjacency.events import (
    REVIEWER_RESPONSE_EVENT,
    STIMULUS_RESPONSE_EVENT,
    ProtocolCompletedEvent,
    ProtocolCompletedPayload,
    ReviewerRequestEvent,
    ReviewerRequestPayload,
    StimulusEvent,
    StimulusPayload,
)
from adjacency.protocol import Escalation, LadderStep, Protocol


@dataclass
class LadderState:
    """Mutable ladder state for a single pair's elicitation run.

    Tracks the current step and variant index, and records resolved keys
    as the interviewer advances through the ladder.
    """

    ladder: list[LadderStep]
    escalation: Escalation
    _step_index: int = field(default=0, init=False)
    _variant_index: int = field(default=0, init=False)
    _resolved: list[str] = field(default_factory=list, init=False)

    @property
    def current_key(self) -> str | None:
        """The key of the current ladder step, or None if the ladder is exhausted."""
        if self._step_index >= len(self.ladder):
            return None
        return self.ladder[self._step_index].key

    @property
    def current_step(self) -> LadderStep | None:
        """The current LadderStep, or None if the ladder is exhausted."""
        if self._step_index >= len(self.ladder):
            return None
        return self.ladder[self._step_index]

    @property
    def current_variant_index(self) -> int:
        """The zero-based index of the current stimulus variant."""
        return self._variant_index

    @property
    def is_complete(self) -> bool:
        """True when all ladder steps have been processed."""
        return self._step_index >= len(self.ladder)

    @property
    def resolved_keys(self) -> list[str]:
        """List of ladder step keys that received a 'yes' verdict, in order."""
        return list(self._resolved)

    def current_stimulus_variant(self) -> str | None:
        """Return the current stimulus variant text, clamped to the last variant."""
        step = self.current_step
        if step is None:
            return None
        idx = min(self._variant_index, len(step.subject_stimulus_variants) - 1)
        return step.subject_stimulus_variants[idx]

    def record_verdict(self, verdict: str) -> None:
        """Advance state based on reviewer verdict: 'yes', 'no', or 'escalate'."""
        step = self.current_step
        if step is None:
            return

        if verdict == "yes":
            self._resolved.append(step.key)
            self._step_index += 1
            self._variant_index = 0
            return

        # 'no' or 'escalate' — try next variant or exhaust
        self._variant_index += 1
        if self._variant_index >= self.escalation.max_attempts_per_state:
            if self.escalation.on_exhaustion == "advance":
                self._step_index += 1
                self._variant_index = 0
            # 'terminal' case: leave state as-is (caller ends session)


class SocraticElicitationPurpose(BasePurpose):  # type: ignore[misc]
    """Drives the Socratic elicitation ladder for a study session.

    Responds to CTO_STARTED to initialize ladder state and send the first
    stimulus. Responds to STIMULUS_RESPONSE_EVENT to request reviewer
    assessment. Responds to REVIEWER_RESPONSE_EVENT to advance or complete
    the ladder, then the gestalt phase, then emit ProtocolCompletedEvent.

    Override _interpolate() and _get_canonical_response() in subclasses
    to inject domain-specific content.

    Args:
        hub: The TTT hub for this session.
        protocol: The parsed Protocol driving this elicitation.
        adjacency_purpose: The AdjacencyPurpose that owns the TTT turn lifecycle.
    """

    name = "socratic_elicitation"

    def __init__(
        self,
        protocol: Protocol,
        adjacency_purpose: Any,
    ) -> None:
        super().__init__()
        self.id: UUID = uuid4()
        self._protocol = protocol
        self._adjacency_purpose = adjacency_purpose
        self._ladder_state: LadderState | None = None
        self._messages: list[dict] = []  # type: ignore[type-arg]
        self._session_id: str = str(uuid4())
        self._in_gestalt = False
        self._gestalt_index = 0

    async def _handle_event(self, event: HubEvent) -> None:
        """Dispatch hub events to the appropriate lifecycle handler."""
        if event.event_type == HubEventType.CTO_STARTED:
            await self._on_cto_started()
        elif event.event_type == STIMULUS_RESPONSE_EVENT:
            await self._on_stimulus_response(event)
        elif event.event_type == REVIEWER_RESPONSE_EVENT:
            await self._on_reviewer_response(event)

    async def _on_cto_started(self) -> None:
        """Initialize ladder state and send the first stimulus when the CTO is ready."""
        self._ladder_state = LadderState(
            ladder=self._protocol.ladder,
            escalation=self._protocol.escalation,
        )
        framing = self._protocol.framing
        if framing.subject_system:
            self._messages = [{"role": "system", "content": framing.subject_system}]
        else:
            self._messages = []
        if framing.subject_context:
            self._messages.append({"role": "user", "content": framing.subject_context})
        await self._send_next_stimulus()

    async def _send_next_stimulus(self) -> None:
        """Send the next ladder stimulus event to the Subject."""
        assert self._ladder_state is not None
        if self._ladder_state.is_complete:
            await self._start_gestalt_or_complete()
            return
        variant = self._ladder_state.current_stimulus_variant()
        assert variant is not None, "_send_next_stimulus called when ladder is complete"
        current_key = self._ladder_state.current_key
        assert (
            current_key is not None
        ), "_send_next_stimulus called when ladder is complete"
        prompt = self._interpolate(variant)
        self._messages.append({"role": "user", "content": prompt})
        event = StimulusEvent(
            purpose_id=self.id,
            purpose_name=self.name,
            hub_token=self.token,
            payload=StimulusPayload(
                question_key=current_key,
                messages=list(self._messages),
                response_kind="free_text",
            ),
        )
        await self.hub.take_turn(event)

    async def _on_stimulus_response(self, event: HubEvent) -> None:
        """Forward the stimulus response to the Reviewer for assessment."""
        payload = event.payload
        self._messages = list(payload.messages)
        # CRITICAL: use payload.question_key, not current_step.key
        # current_step is None when ladder is complete (gestalt phase)
        canonical = self._get_canonical_response(payload.question_key)
        req = ReviewerRequestEvent(
            purpose_id=self.id,
            purpose_name=self.name,
            hub_token=self.token,
            payload=ReviewerRequestPayload(
                question_key=payload.question_key,
                messages=list(self._messages),
                canonical_response=canonical,
            ),
        )
        await self.hub.take_turn(req)

    async def _on_reviewer_response(self, event: HubEvent) -> None:
        """Advance ladder or gestalt state based on the Reviewer's verdict."""
        assert self._ladder_state is not None
        verdict = event.payload.response
        if self._in_gestalt:
            await self._advance_gestalt()
            return
        self._ladder_state.record_verdict(verdict)
        if self._ladder_state.is_complete:
            await self._start_gestalt_or_complete()
        else:
            await self._send_next_stimulus()

    async def _start_gestalt_or_complete(self) -> None:
        """Begin the gestalt phase if steps remain, otherwise emit protocol completion."""
        if self._protocol.gestalt and self._gestalt_index < len(self._protocol.gestalt):
            self._in_gestalt = True
            await self._send_gestalt_stimulus()
        else:
            await self._emit_completed()

    async def _send_gestalt_stimulus(self) -> None:
        """Send the current gestalt stimulus to the Subject."""
        step = self._protocol.gestalt[self._gestalt_index]
        prompt = self._interpolate(step.stimulus)
        self._messages.append({"role": "user", "content": prompt})
        event = StimulusEvent(
            purpose_id=self.id,
            purpose_name=self.name,
            hub_token=self.token,
            payload=StimulusPayload(
                question_key=step.key,
                messages=list(self._messages),
                response_kind="free_text",
            ),
        )
        await self.hub.take_turn(event)

    async def _advance_gestalt(self) -> None:
        """Advance to the next gestalt step, or emit completion if exhausted."""
        self._gestalt_index += 1
        if self._gestalt_index < len(self._protocol.gestalt):
            await self._send_gestalt_stimulus()
        else:
            await self._emit_completed()

    async def _emit_completed(self) -> None:
        """Emit ProtocolCompletedEvent to signal end of the study session."""
        state = self._ladder_state
        final_key = (
            state.resolved_keys[-1]
            if state and state.resolved_keys
            else self._protocol.completion_key
        )
        event = ProtocolCompletedEvent(
            purpose_id=self.id,
            purpose_name=self.name,
            hub_token=self.token,
            payload=ProtocolCompletedPayload(
                final_state=final_key,
                session_id=self._session_id,
            ),
        )
        await self.hub.take_turn(event)

    def _interpolate(self, text: str) -> str:
        """Substitute {{variable}} placeholders. Override in subclasses."""
        return text

    def _get_canonical_response(self, question_key: str | None) -> str | None:
        """Look up canonical response for the given question key. Override in TraceProbe subclass."""
        return None
