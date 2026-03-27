# Adjacency

Adjacency is a reusable workflow layer on top of `turnturnturn`. It defines the
stable protocol, participant, purpose, backend, and session assembly surfaces
that study workflows can build on.

The first built-in generic workflow is `source_monitoring_annotation`, which
imports a canonical CTO and walks its turns with a human backend by default.

## Quick start

```bash
adj start source_monitoring_annotation --cto-import tests/adjacency/doctor_patient_knee_cto.json
```

That command uses the built-in workflow, the default Archivist-backed
persistence path, and the console annotator backend.

## Documentation map

- [Architecture](architecture/index.md)
- [API Reference](api/index.md)
- [Developer Guide](dev-guide.md)

## Repository boundaries

Adjacency stays focused on workflow composition. It should not grow knowledge
of TraceProbe-specific semantics unless a capability is genuinely reusable
across study workflows.
