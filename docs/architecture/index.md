# Architecture

Adjacency is the workflow layer between `turnturnturn` and the domain-specific
study packages that build on top of it.

The stable public shape is intentionally small:

- `adj` as the command-line entrypoint
- session assembly helpers and workflow purpose types
- participant and backend interfaces
- the built-in `source_monitoring_annotation` workflow
- the first web UI and renderer contract for annotation workflows

For the lifecycle substrate, provenance rules, and CTO import semantics, see
the corresponding `turnturnturn` documentation. Adjacency stays focused on
workflow composition and participant orchestration.

## Current layering

1. `turnturnturn` provides the hub, CTO lifecycle, and persistence substrate.
2. `adjacency` defines reusable workflow roles, protocols, and built-in flows.
3. higher-level packages can register their own study-specific purposes on top
   of the same substrate without changing the adjacency core.
