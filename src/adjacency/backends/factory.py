"""Generic LLM backend factory for Adjacency."""

from __future__ import annotations

from typing import Any

from adjacency.backends.anthropic import AnthropicBackend
from adjacency.backends.base import Backend
from adjacency.backends.gemini import GeminiBackend
from adjacency.backends.ollama import OllamaBackend
from adjacency.backends.openai_compatible import OpenAICompatibleBackend


def make_llm_backend(spec: str, **kwargs: Any) -> Backend:
    """Build an Adjacency backend from a provider-qualified spec string.

    Supported specs:
    - ``anthropic/<model>``
    - ``openai/<model>``
    - ``openai_compatible/<model>``
    - ``gemini/<model>``
    - ``ollama/<model>``
    """

    if "/" not in spec:
        raise ValueError(f"LLM backend spec must be '<family>/<model>'; got {spec!r}")
    family, model = spec.split("/", 1)
    if not model:
        raise ValueError(f"LLM backend spec is missing a model name: {spec!r}")

    if family == "anthropic":
        return AnthropicBackend(model=model, **_pick(kwargs, "api_key", "base_url"))
    if family == "openai":
        return OpenAICompatibleBackend(
            model=model,
            **_pick(kwargs, "api_key", "base_url"),
        )
    if family == "openai_compatible":
        return OpenAICompatibleBackend(
            model=model,
            **_pick(kwargs, "api_key", "base_url"),
        )
    if family == "gemini":
        return GeminiBackend(
            model=model,
            **_pick(kwargs, "api_key", "thinking_budget"),
        )
    if family == "ollama":
        return OllamaBackend(model=model, **_pick(kwargs, "host"))
    raise ValueError(
        f"Unknown backend family {family!r}; expected anthropic, openai, "
        "openai_compatible, gemini, or ollama"
    )


def _pick(kwargs: dict[str, Any], *names: str) -> dict[str, Any]:
    """Return only selected kwargs whose values are not None."""
    return {name: kwargs[name] for name in names if kwargs.get(name) is not None}
