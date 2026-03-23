"""AdjacencyLibrarian — wraps ttt.librarian; adds per-role participant instructions.

Provides a thin wrapper around the TTT librarian with additional
role-keyed instruction lookup that the TTT layer has no concept of.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID


class AdjacencyLibrarian:
    """Thin wrapper around a TTT librarian with per-role instruction lookup.

    Delegates CTO (Conversational Turn Object) retrieval to the underlying
    TTT librarian and adds role-keyed participant instructions that the
    TTT layer has no concept of.

    Attributes:
        _ttt_librarian: The TTT librarian instance, or None if not available.
        _instructions: Mapping of role name (e.g., "subject", "reviewer")
            to instruction string.
    """

    def __init__(
        self,
        ttt_librarian: Any,
        instructions: dict[str, str],
    ) -> None:
        """Initialize the librarian wrapper.

        Args:
            ttt_librarian: The TTT librarian instance, or None if not available.
            instructions: Mapping of role name to instruction string.
        """
        self._ttt_librarian = ttt_librarian
        self._instructions = instructions

    def get_cto(self, turn_id: UUID) -> Any:
        """Return the CTO for the given turn, delegating to the TTT librarian.

        Args:
            turn_id: The UUID of the turn.

        Returns:
            The CTO object from the TTT librarian, or None if the librarian
            is unavailable.
        """
        if self._ttt_librarian is None:
            return None
        return self._ttt_librarian.get_cto(turn_id)

    def participant_instructions(self, role: str) -> str | None:
        """Return role-specific instructions, or None if not found.

        Args:
            role: The role name (e.g., "subject", "reviewer").

        Returns:
            The instruction string for the role, or None if not found.
        """
        return self._instructions.get(role)
