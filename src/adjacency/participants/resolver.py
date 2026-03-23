"""ParticipantResolver protocol and DictResolver implementation."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from adjacency.participants.base import Participant


@runtime_checkable
class ParticipantResolver(Protocol):
    """Resolves workflow role names to Participant implementations.

    Implementations must support resolve(), supports(), and available_roles().
    This is a structural protocol — no inheritance required.
    """

    def resolve(self, role_name: str) -> Participant:
        """Return the Participant for role_name. Raises KeyError if not found."""
        ...

    def supports(self, role_name: str) -> bool:
        """Return True if this resolver can resolve role_name."""
        ...

    def available_roles(self) -> frozenset[str]:
        """Return the set of role names this resolver can resolve."""
        ...


class DictResolver:
    """Resolves roles from a plain dict mapping of role name to Participant."""

    def __init__(self, roles: dict[str, Participant]) -> None:
        self._roles = dict(roles)

    def resolve(self, role_name: str) -> Participant:
        """Return the Participant for role_name. Raises KeyError if not found."""
        if role_name not in self._roles:
            raise KeyError(
                f"No participant configured for role {role_name!r}. "
                f"Available: {sorted(self._roles)}"
            )
        return self._roles[role_name]

    def supports(self, role_name: str) -> bool:
        """Return True if role_name is in the registry."""
        return role_name in self._roles

    def available_roles(self) -> frozenset[str]:
        """Return a frozen set of all registered role names."""
        return frozenset(self._roles)
