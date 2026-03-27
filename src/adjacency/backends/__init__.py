"""Backend adapters exposed by Adjacency."""

from .anthropic import AnthropicBackend
from .factory import make_llm_backend
from .gemini import GeminiBackend
from .ollama import OllamaBackend
from .openai_compatible import OpenAICompatibleBackend

__all__ = [
    "AnthropicBackend",
    "GeminiBackend",
    "OllamaBackend",
    "OpenAICompatibleBackend",
    "make_llm_backend",
]
