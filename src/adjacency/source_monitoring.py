"""Built-in source monitoring annotation workflow for Adjacency."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID, uuid4

from turnturnturn.base_purpose import SessionOwnerPurpose
from turnturnturn.delta import Delta
from turnturnturn.events import (
    DeltaProposalEvent,
    DeltaProposalPayload,
    HubEvent,
    HubEventType,
    PurposeEventType,
)

from adjacency.profiles import LEXICAL_PROFILE_ID
from adjacency.profiles import register as register_profiles

SOURCE_MONITORING_NAMESPACE = "adjacency.source_monitoring"
RESERVED_SELECTIONS = {"blank", "unknown", "escalate"}


def _now_ms() -> int:
    return int(time.time() * 1000)


class SourceMonitoringBackend(Protocol):
    """Decision surface for the source monitoring annotation workflow."""

    async def annotate_turn(
        self,
        *,
        speakers: list[dict[str, Any]],
        turn: dict[str, Any],
        turn_index: int,
        total_turns: int,
    ) -> str: ...


class ScriptedSourceMonitoringBackend:
    """Deterministic backend that returns scripted annotation selections."""

    def __init__(self, decisions: list[str]) -> None:
        if not decisions:
            raise ValueError("ScriptedSourceMonitoringBackend requires decisions")
        self._decisions = decisions
        self._index = 0

    async def annotate_turn(
        self,
        *,
        speakers: list[dict[str, Any]],
        turn: dict[str, Any],
        turn_index: int,
        total_turns: int,
    ) -> str:
        decision = self._decisions[min(self._index, len(self._decisions) - 1)]
        self._index += 1
        return decision


class ConsoleSourceMonitoringBackend:
    """Minimal console backend for the v1 source monitoring workflow."""

    async def annotate_turn(
        self,
        *,
        speakers: list[dict[str, Any]],
        turn: dict[str, Any],
        turn_index: int,
        total_turns: int,
    ) -> str:
        speaker_lines = "\n".join(
            f"  - {speaker['session_speaker_id']}: {speaker['display_label']}"
            for speaker in speakers
        )
        prompt = (
            f"\nTurn {turn_index}/{total_turns}\n"
            f"Raw source: {turn.get('raw_source_tag', '<none>')}\n"
            f"Utterance: {turn['utterance']}\n"
            "Speakers:\n"
            f"{speaker_lines}\n"
            "Enter a session_speaker_id or one of: blank, unknown, escalate\n"
            "> "
        )
        while True:
            response = await asyncio.to_thread(input, prompt)
            normalized = response.strip() or "blank"
            if normalized in RESERVED_SELECTIONS or any(
                speaker["session_speaker_id"] == normalized for speaker in speakers
            ):
                return normalized


class SourceMonitoringAnnotatorPurpose(SessionOwnerPurpose):
    """Combined session owner and annotator for the built-in source monitoring flow."""

    name = SOURCE_MONITORING_NAMESPACE

    def __init__(
        self,
        *,
        source_locator: str,
        backend: SourceMonitoringBackend,
        session_code: str | None = None,
        source_kind: str = "cto_json",
    ) -> None:
        super().__init__()
        self.id: UUID = uuid4()
        self._source_locator = source_locator
        self._source_kind = source_kind
        self._backend = backend
        self._session_id: UUID = uuid4()
        self._session_code = session_code
        self.turn_id: UUID | None = None
        self._requested = False
        self._completed = False

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
        """Begin annotation when the imported lexical CTO becomes live."""
        if event.event_type != HubEventType.CTO_STARTED or self._completed:
            return
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

    async def _annotate_live_cto(self, turn_id: UUID) -> None:
        cto = self.hub.librarian.get_cto(turn_id)
        assert cto is not None, "cto_started should point at a live canonical CTO"
        speakers = cto.content["speakers"]
        turns = cto.content["turns"]
        total_turns = len(turns)

        for turn_index, turn in enumerate(turns, start=1):
            selection = await self._backend.annotate_turn(
                speakers=speakers,
                turn=turn,
                turn_index=turn_index,
                total_turns=total_turns,
            )
            normalized = self._normalize_selection(selection, speakers)
            await self._emit_annotation_delta(
                turn_id=turn_id,
                source_turn_id=turn["source_turn_id"],
                ordinal=turn["ordinal"],
                selection=normalized,
            )

        self._completed = True
        await self.end_session(str(self._session_id))

    def _normalize_selection(
        self, selection: str, speakers: list[dict[str, Any]]
    ) -> str:
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
        source_turn_id: str,
        ordinal: int,
        selection: str,
    ) -> None:
        delta = Delta(
            delta_id=uuid4(),
            session_id=self._session_id,
            turn_id=turn_id,
            purpose_name=self.name,
            purpose_id=self.id,
            patch={
                source_turn_id: [
                    {
                        "selection": selection,
                        "ordinal": ordinal,
                    }
                ]
            },
        )
        event = DeltaProposalEvent(
            event_type=PurposeEventType.DELTA_PROPOSAL,
            event_id=uuid4(),
            created_at_ms=_now_ms(),
            purpose_id=self.id,
            purpose_name=self.name,
            hub_token=self._require_token(),
            payload=DeltaProposalPayload(delta=delta),
        )
        await self.hub.take_turn(event)


@dataclass
class SourceMonitoringSession:
    """Minimal session wrapper for the built-in source monitoring workflow."""

    annotator_purpose: SourceMonitoringAnnotatorPurpose

    async def start(self) -> None:
        register_profiles()
        await self.annotator_purpose.start_session()


def assemble_source_monitoring_session(
    annotator_purpose: SourceMonitoringAnnotatorPurpose,
) -> SourceMonitoringSession:
    """Return a runnable session wrapper for the built-in source monitoring flow."""
    return SourceMonitoringSession(annotator_purpose=annotator_purpose)
