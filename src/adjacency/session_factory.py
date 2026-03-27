"""assemble_session — generic Adjacency session factory.

This is a study assembly seam, not the end-user authoring interface.
It is the programmatic substrate on which a future declarative/config-driven
path will be built. Callers today construct sessions explicitly; callers
tomorrow may be config-driven tooling composing the same call from declarations.

assemble_session() accepts dependencies, assembles a Session, and returns it.
It does not open files, register profiles, or touch hub bootstrap.
"""

from __future__ import annotations

from typing import Callable

from turnturnturn.hub import TTT

from adjacency.participants.resolver import ParticipantResolver
from adjacency.protocol import Protocol
from adjacency.purposes.base import AdjacencyPurpose
from adjacency.purposes.moderator import SocraticElicitationPurpose
from adjacency.purposes.participant import ReviewerPurpose, SubjectPurpose
from adjacency.session import Session

ModeratorFactory = Callable[[Protocol, AdjacencyPurpose], SocraticElicitationPurpose]


def _default_moderator_factory(
    protocol: Protocol,
    adjacency_purpose: AdjacencyPurpose,
) -> SocraticElicitationPurpose:
    return SocraticElicitationPurpose(
        protocol=protocol,
        adjacency_purpose=adjacency_purpose,
    )


def assemble_session(
    hub: TTT,
    adjacency_purpose: AdjacencyPurpose,
    protocol: Protocol,
    participant_resolver: ParticipantResolver,
    moderator_factory: ModeratorFactory | None = None,
) -> Session:
    """Assemble a Session from pre-loaded components and injected factories.

    Args:
        hub: Already-bootstrapped TTT hub. Caller owns hub bootstrap and
            profile registration — this function touches neither.
        adjacency_purpose: The already-constructed session-owner purpose for
            this study. It should be the same purpose passed to `TTT.start(...)`.
        protocol: Already-parsed Protocol object. Use adjacency.protocol.load_protocol
            or load_protocol_file before calling this function.
        participant_resolver: Resolves role names to Participant instances.
            Must support at least "subject" and "reviewer".
        moderator_factory: Optional callable ``(protocol, adjacency_purpose) ->
            SocraticElicitationPurpose`` subclass. Defaults to base
            SocraticElicitationPurpose. Pass a closure here to inject
            domain-specific moderators (e.g. TraceProbe's SocraticModerator).
    """
    if moderator_factory is None:
        moderator_factory = _default_moderator_factory

    subject_purpose = SubjectPurpose(
        participant=participant_resolver.resolve("subject")
    )
    reviewer_purpose = ReviewerPurpose(
        participant=participant_resolver.resolve("reviewer")
    )
    moderator = moderator_factory(protocol, adjacency_purpose)

    return Session(
        hub=hub,
        adjacency_purpose=adjacency_purpose,
        subject_purpose=subject_purpose,
        reviewer_purpose=reviewer_purpose,
        moderator=moderator,
    )
