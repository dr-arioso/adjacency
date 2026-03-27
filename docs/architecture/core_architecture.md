# Core Architecture

Adjacency is designed as a thin orchestration layer with a few stable
concepts:

- a `Session` that wires already-constructed purposes together
- a `Protocol` that captures the session shape and role expectations
- `Participant` implementations that do not know about the hub
- `Purpose` implementations that do know about the hub and can emit events
- backend adapters that isolate provider-specific LLM SDKs

The package is intentionally explicit. There is no hidden session builder or
registry magic in the public API surface. Callers assemble the pieces they
need, then hand them to the workflow entrypoint.

## Built-in workflow

The first built-in generic workflow is `source_monitoring_annotation`.
It is intended to show that Adjacency can run a reusable, turn-oriented
workflow over a canonical CTO without TraceProbe-specific assumptions.

## Stable public surfaces

This repository intentionally documents only the stable surfaces that are
expected to remain useful across workflows:

- `adjacency.cli`
- `adjacency.protocol`
- `adjacency.session`
- `adjacency.session_factory`
- `adjacency.participants.*`
- `adjacency.purposes.*`
- `adjacency.backends.*`
- `adjacency.source_monitoring`
