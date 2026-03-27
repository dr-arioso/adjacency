# Adjacency

Adjacency is a Python framework for building structured annotation, review, and
elicitation workflows with humans and language models. It sits between
`turnturnturn` and domain applications like `traceprobe`, providing reusable
protocols, participant backends, and session orchestration. Provenance is
first-class: the canonical record is the event stream.

## Quick start

```bash
adj start source_monitoring_annotation --cto-import tests/adjacency/doctor_patient_knee_cto.json
```

That runs the first built-in generic workflow with the default
Archivist-backed persistence path and the console annotator backend.

## Docs

- [Documentation root](docs/index.md)
- [Architecture](docs/architecture/index.md)
- [API reference](docs/api/index.md)
- [Developer guide](docs/dev-guide.md)

## Scope

Adjacency owns reusable workflow logic. It should not absorb domain-specific
semantics unless they are genuinely reusable across multiple study workflows.
