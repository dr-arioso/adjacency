"""Shared fixtures for adjacency tests.

No traceprobe imports here. Adjacency tests must run with traceprobe absent.
"""
import pytest
from turnturnturn.hub import TTT  # type: ignore[import-untyped]
from turnturnturn.persistence import InMemoryPersistencePurpose  # type: ignore[import-untyped]


@pytest.fixture
async def ttt() -> TTT:
    """A bootstrapped in-memory TTT hub with no traceprobe profile registered."""
    hub = TTT(registrations={})
    persistence = InMemoryPersistencePurpose()
    await hub.start_purpose(persistence)
    return hub
