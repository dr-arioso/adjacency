# `source_monitoring_annotation`

`source_monitoring_annotation` is the first built-in generic workflow in
Adjacency.

It demonstrates the intended runtime pattern:

1. a caller launches `adj start source_monitoring_annotation --cto-import ...`
2. the workflow requests a canonical CTO import from `turnturnturn`
3. the imported CTO becomes live in the session mesh
4. the annotator walks the turns in order and writes namespaced deltas
5. the workflow ends the session after all turns are annotated

The v1 implementation uses a human backend at the console by default. The
workflow core stays separate from that interaction style so later frontends
can reuse the same session and annotation semantics.

The important architectural property is that the workflow is turn-oriented,
not TraceProbe-oriented. It operates on a lexical CTO and a roster of speakers,
which keeps the implementation reusable for other future workflows.
