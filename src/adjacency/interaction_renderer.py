"""Minimal interaction-renderer seam for human-facing workflow surfaces."""

from __future__ import annotations

from typing import Generic, Protocol, TypeVar

RequestT = TypeVar("RequestT", contravariant=True)
IntentT = TypeVar("IntentT", covariant=True)


class InteractionRenderer(Protocol, Generic[RequestT, IntentT]):
    """Bidirectional adapter between workflow state and an interaction surface."""

    async def publish(self, request: RequestT) -> None:
        """Publish a fresh immutable workflow snapshot to the surface."""

    async def next_intent(self) -> IntentT:
        """Wait for the next user intent from the surface."""
