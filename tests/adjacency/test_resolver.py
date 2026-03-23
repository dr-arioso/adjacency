"""Tests for ParticipantResolver protocol and DictResolver implementation."""
import pytest
from unittest.mock import MagicMock

from adjacency.participants.base import Participant
from adjacency.participants.resolver import DictResolver, ParticipantResolver


def _mock_participant() -> Participant:
    return MagicMock(spec=Participant)


def test_dict_resolver_resolve_known_role():
    subject = _mock_participant()
    resolver = DictResolver({"subject": subject})
    assert resolver.resolve("subject") is subject


def test_dict_resolver_resolve_unknown_role_raises():
    resolver = DictResolver({"subject": _mock_participant()})
    with pytest.raises(KeyError):
        resolver.resolve("reviewer")


def test_dict_resolver_supports_known_role():
    resolver = DictResolver({"subject": _mock_participant()})
    assert resolver.supports("subject") is True
    assert resolver.supports("reviewer") is False


def test_dict_resolver_available_roles():
    resolver = DictResolver({"subject": _mock_participant(), "reviewer": _mock_participant()})
    assert resolver.available_roles() == frozenset({"subject", "reviewer"})


def test_dict_resolver_available_roles_is_frozen():
    resolver = DictResolver({"subject": _mock_participant()})
    roles = resolver.available_roles()
    with pytest.raises((AttributeError, TypeError)):
        roles.add("other")  # type: ignore[attr-defined]


def test_dict_resolver_satisfies_participant_resolver_protocol():
    """DictResolver must satisfy the ParticipantResolver structural protocol."""
    resolver = DictResolver({"subject": _mock_participant()})
    assert isinstance(resolver, ParticipantResolver)
