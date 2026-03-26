"""AdjacencyPurpose — session lifecycle anchor.

Responsibilities:
  - On explicit start_session(): calls hub.start_turn() to create the
    exhibit CTO.
  - On ProtocolCompletedEvent: emits end_session to request hub-managed shutdown.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from turnturnturn.base_purpose import SessionOwnerPurpose  # type: ignore[import-untyped]
from turnturnturn.events import (  # type: ignore[import-untyped]
    HubEvent,
)

from adjacency.events import PROTOCOL_COMPLETED_EVENT


class AdjacencyPurpose(SessionOwnerPurpose):  # type: ignore[misc]
    """Session lifecycle anchor that owns the TTT turn lifecycle.

    This is the explicit startup-time session owner for an adjacency-backed
    study. It starts the study CTO only when Session.start() tells it to, and
    later emits end_session when the protocol is complete.

    Args:
        content_profile: Profile identifier for the CTO content field.
        content: Pre-loaded study content payload.
    """

    name = "adjacency"

    def __init__(
        self,
        content_profile: str,
        content: dict[str, Any],
        session_code: str | None = None,
    ) -> None:
        super().__init__()
        self.id: UUID = uuid4()
        self._content_profile = content_profile
        self._content = content
        self._session_id: UUID = uuid4()
        self._session_code = session_code
        self.turn_id: UUID | None = None

    async def _handle_event(self, event: HubEvent) -> None:
        """Dispatch incoming hub events to lifecycle handlers."""
        if event.event_type == PROTOCOL_COMPLETED_EVENT:
            await self._on_protocol_completed()

    async def start_session(self) -> None:
        """Start the study CTO once the rest of the session mesh is registered."""
        if self.turn_id is not None:
            return
        token = self.token
        assert (
            token is not None
        ), "AdjacencyPurpose.start_session called before token was assigned"
        self.turn_id = await self.hub.start_turn(
            self._content_profile,
            self._content,
            token,
            session_id=self._session_id,
            session_code=self._session_code,
        )

    async def _on_protocol_completed(self) -> None:
        """Request hub-managed shutdown once the protocol is complete."""
        await self.end_session(str(self._session_id))
