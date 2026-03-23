"""Session — holds assembled Purposes and registers them with the hub."""

from __future__ import annotations

from turnturnturn.hub import TTT  # type: ignore[import-untyped]

from adjacency.events import register_all
from adjacency.purposes.base import AdjacencyPurpose
from adjacency.purposes.moderator import SocraticElicitationPurpose
from adjacency.purposes.participant import ReviewerPurpose, SubjectPurpose


class Session:
    """Assembled study session: holds constructed Purposes, ready to be started.

    Do not construct directly — use assemble_session() in session_factory.py.
    Registration order in start() is load-bearing and must not change.

    Args:
        hub: The TTT hub for this session.
        adjacency_purpose: The lifecycle anchor purpose.
        subject_purpose: The Subject role purpose.
        reviewer_purpose: The Reviewer role purpose.
        moderator: The SocraticElicitationPurpose (or subclass) driving the ladder.
    """

    def __init__(
        self,
        hub: TTT,
        adjacency_purpose: AdjacencyPurpose,
        subject_purpose: SubjectPurpose,
        reviewer_purpose: ReviewerPurpose,
        moderator: SocraticElicitationPurpose,
    ) -> None:
        self._hub = hub
        self._adjacency_purpose = adjacency_purpose
        self._subject_purpose = subject_purpose
        self._reviewer_purpose = reviewer_purpose
        self._moderator = moderator

    async def start(self) -> None:
        """Register all Purposes with the hub in the required load-bearing order.

        AdjacencyPurpose must be last: registering it fires PURPOSE_STARTED, which
        triggers start_turn(), which emits CTO_STARTED, which drives the full chain.
        Subject, Reviewer, and Moderator must already be registered to receive it.
        """
        register_all()
        await self._hub.start_purpose(self._subject_purpose)
        await self._hub.start_purpose(self._reviewer_purpose)
        await self._hub.start_purpose(self._moderator)
        await self._hub.start_purpose(self._adjacency_purpose)
