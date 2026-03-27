"""AdjacencyPurpose — session lifecycle anchor.

Responsibilities:
  - On explicit start_session(): calls hub.start_turn() to create the
    exhibit CTO.
  - On WorkflowCompleted: emits request_session_end to request hub-managed shutdown.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from turnturnturn.base_purpose import SessionOwnerPurpose
from turnturnturn.events import HubEvent

from adjacency.events import WORKFLOW_COMPLETED


class AdjacencyPurpose(SessionOwnerPurpose):
    """Session lifecycle anchor that owns the TTT turn lifecycle.

    This is the explicit startup-time session owner for an adjacency-backed
    study. It starts the study CTO only when Session.start() tells it to, and
    later emits request_session_end when the protocol is complete.

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
        if event.event_type == WORKFLOW_COMPLETED:
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
        await self.request_session_end(str(self._session_id))
