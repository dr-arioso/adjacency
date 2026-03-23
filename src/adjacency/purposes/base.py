"""AdjacencyPurpose — session lifecycle anchor.

Responsibilities:
  - On purpose_started for this purpose: calls hub.start_turn() to create
    the exhibit CTO.
  - On ProtocolCompletedEvent: calls hub.close() to end the session.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from turnturnturn.base_purpose import BasePurpose  # type: ignore[import-untyped]
from turnturnturn.events import HubEvent, HubEventType  # type: ignore[import-untyped]
from turnturnturn.hub import TTT  # type: ignore[import-untyped]

from adjacency.events import PROTOCOL_COMPLETED_EVENT


class AdjacencyPurpose(BasePurpose):  # type: ignore[misc]
    """Session lifecycle anchor that owns the TTT turn lifecycle.

    Listens for its own PURPOSE_STARTED event to call hub.start_turn(),
    creating the study's CTO. Listens for ProtocolCompletedEvent to call
    hub.close(), ending the session.

    Args:
        hub: The TTT hub instance for this session.
        content_profile: Profile identifier for the CTO content field.
        content: Pre-loaded study content payload.
    """

    name = "adjacency"

    def __init__(
        self,
        hub: TTT,
        content_profile: str,
        content: dict[str, Any],
    ) -> None:
        super().__init__()
        self.id: UUID = uuid4()
        self._hub = hub
        self._content_profile = content_profile
        self._content = content
        self.turn_id: UUID | None = None
        self._close_called = False

    async def _handle_event(self, event: HubEvent) -> None:
        """Dispatch incoming hub events to lifecycle handlers."""
        if event.event_type == HubEventType.PURPOSE_STARTED:
            payload_dict = event.payload.as_dict()
            if str(payload_dict.get("purpose_id")) == str(self.id):
                await self._on_own_purpose_started()
        elif event.event_type == PROTOCOL_COMPLETED_EVENT:
            await self._on_protocol_completed()

    async def _on_own_purpose_started(self) -> None:
        """Called when this purpose's own PURPOSE_STARTED fires; starts the TTT turn."""
        token = self.token
        assert (
            token is not None
        ), "AdjacencyPurpose._on_own_purpose_started called before token was assigned"
        self.turn_id = await self._hub.start_turn(
            self._content_profile,
            self._content,
            token,
        )

    async def _on_protocol_completed(self) -> None:
        """Close the hub once the protocol is complete. Idempotent."""
        if not self._close_called:
            self._close_called = True
            await self._hub.close()
