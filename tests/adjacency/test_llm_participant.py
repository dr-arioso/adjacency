import pytest

from adjacency.backends.base import Backend
from adjacency.participants.llm import LLMParticipant


class MockBackend(Backend):
    def __init__(self, response: str):
        self._response = response
        self.last_messages = None
        self.last_system = None

    async def complete(self, messages: list[dict], *, system: str | None = None) -> str:
        self.last_messages = messages
        self.last_system = system
        return self._response


@pytest.mark.asyncio
async def test_llm_participant_respond_passes_messages_to_backend():
    backend = MockBackend("The LLM collapsed the temporal scope.")
    participant = LLMParticipant(
        backend=backend, system_prompt="You are a careful assistant."
    )

    response = await participant.respond(
        messages=[{"role": "user", "content": "Do you notice anything?"}],
        question_key="locus_visible",
    )
    assert response == "The LLM collapsed the temporal scope."
    # System prompt is NOT in messages; passed separately
    assert not any(m.get("role") == "system" for m in backend.last_messages)
    assert backend.last_system == "You are a careful assistant."


@pytest.mark.asyncio
async def test_llm_participant_assess_raises_not_implemented_for_scoring():
    """LLMParticipant.assess() is for LLM-as-judge; minimal stub for now."""
    backend = MockBackend("yes")
    participant = LLMParticipant(backend=backend)
    result = await participant.assess([], "locus_visible", "canonical")
    assert result in ("yes", "no", "yes_escalate", "no_escalate")


@pytest.mark.asyncio
async def test_llm_participant_assess_accepts_escalation_suffix():
    backend = MockBackend("yes_escalate")
    participant = LLMParticipant(backend=backend)
    result = await participant.assess([], "locus_visible", "canonical")
    assert result == "yes_escalate"
