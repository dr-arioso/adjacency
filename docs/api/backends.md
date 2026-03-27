# Backends

Backend adapters isolate LLM provider SDK details from the rest of the codebase.
The stable API surface is the abstract backend contract plus the factory helper
that chooses an implementation from a provider-qualified spec string.

::: adjacency.backends.base

::: adjacency.backends.factory
