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
    The session-owner purpose is expected to have been registered already as
    part of TTT.start(); start() registers the remaining purposes and then
    explicitly tells the owner to start the session.

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

        Subject, Reviewer, and Moderator must already be registered before the
        owner starts the first turn so they can receive the resulting CTO/event
        chain.
        """
        register_all()
        await self._hub.start_purpose(self._subject_purpose)
        await self._hub.start_purpose(self._reviewer_purpose)
        await self._hub.start_purpose(self._moderator)
        await self._adjacency_purpose.start_session()
