"""Shared fixtures for adjacency tests.

No traceprobe imports here. Adjacency tests must run with traceprobe absent.
"""

import pytest
from turnturnturn.hub import TTT  # type: ignore[import-untyped]
from turnturnturn.persistence import (
    InMemoryPersistencePurpose,  # type: ignore[import-untyped]
)
from turnturnturn.profile import (  # type: ignore[import-untyped]
    Profile,
    ProfileRegistry,
)
from adjacency.purposes.base import AdjacencyPurpose

# Register a minimal permissive profile for adjacency tests.
# Empty fields = accepts any content dict without validation.
# Registered once at module load; safe to call multiple times (idempotent).
ProfileRegistry.register(Profile(profile_id="adjacency_test", fields={}))


@pytest.fixture
def adjacency_purpose() -> AdjacencyPurpose:
    """A session-owner purpose suitable for adjacency tests."""
    return AdjacencyPurpose(content_profile="adjacency_test", content={})


@pytest.fixture
def ttt(adjacency_purpose: AdjacencyPurpose) -> TTT:
    """A bootstrapped in-memory TTT hub with no traceprobe profile registered.

    Uses TTT.start() which loads built-in profiles via ProfileRegistry.load_defaults().
    The adjacency_test profile is registered at module level above.
    """
    import warnings

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        return TTT.start(
            InMemoryPersistencePurpose(),
            session_owner_purpose=adjacency_purpose,
        )
