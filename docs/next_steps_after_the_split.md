# Next Steps After the Split

## Purpose

This document describes the immediate next steps after the Adjacency / TraceProbe split lands cleanly.

The goal is not to pursue maximal architecture all at once. The goal is to quickly prove that the new seam unlocks a more usable Adjacency workflow model.

In particular, the next phase should demonstrate that:

- Adjacency can support a simple non-TraceProbe workflow with minimal code
- TTT remains the provenance/persistence substrate underneath that workflow
- a lexical CTO profile can support a broadly legible turn-based interaction object
- future Scribe-based packaging/import can feed the same workflow without changing the workflow itself

---

## Immediate priority

The first proof after the split should be a **simple moderated annotation loop** over a short conversational CTO.

This should be treated as a reusable Adjacency workflow pattern, not as a one-off app script.

---

## First test workflow

### Candidate workflow

A short doctor-patient interaction of roughly 10-12 turns.

### Annotation task

For each turn, a human annotator identifies the speaker/source.

Initial candidate labels:

- `doctor`
- `patient`

Optional additional field:

- `confidence`

### Why this is the right first test

This workflow is:

- simple
- realistic
- turn-oriented
- easy to evaluate by eye
- outside TraceProbe's domain semantics
- a strong test of the lexical CTO idea

It also matches a real pain point, since AI-transcribed audio often performs poorly on speaker attribution.

---

## Architectural interpretation

From an Adjacency / TTT standpoint, this should be implemented as a **moderated annotation loop**.

### TTT should do

- carry the CTO/work unit
- route events
- persist annotation Deltas
- preserve provenance
- allow later purposes to observe or build on those Deltas

### Adjacency should do

- traverse turns in order
- have the moderator present the current turn
- capture a structured annotation response
- emit a Delta targeting the current turn
- advance until complete

This is exactly the kind of workflow Adjacency should eventually make available with very little YAML/configuration.

---

## Near-term execution order

The annotation loop is not only a workflow proof. It is also the first meaningful runtime UI pressure test for the post-split architecture.

### Step 1: hand-build a minimal CTO in the domain layer

Do not block on import tooling.

Create a very small lexical-style CTO specimen by hand for the doctor-patient interaction.

Near-term purpose:

- validate the lexical turn shape
- validate turn traversal
- validate annotation Delta persistence
- validate output masks

This is the fastest way to test the post-split architecture.

### Step 2: run the moderated annotation loop against that CTO

Implement the smallest useful moderated annotation session that:

- iterates over turns
- prompts for speaker attribution
- records per-turn annotations
- persists those annotations through TTT

This should prove that Adjacency now supports a generic, non-TraceProbe workflow.

### Step 3: build the minimal runtime UI for that loop

This phase should include a very small runtime UI, not a full authoring environment.

The immediate goal is to test live usability of the workflow, including:

- current-turn display
- a small context window where helpful
- moderator prompt display
- candidate label selection
- optional confidence entry
- submit / next flow
- a minimal summary or progress view

A preexisting NiceGUI mockup already exists, so the practical near-term move is likely to repurpose that mockup rather than design a new UI from scratch.

This should be treated as a runtime session UI pressure test, not as a finished product.

### Step 4: export/use the annotated result

Once the loop works, confirm that the result is useful outside the runtime.

Initial outputs should probably include:

- JSON
- ANSI / terminal-friendly rendering
- optionally Markdown

This confirms that annotations are not merely captured, but also usable.

### Step 5: feed the same workflow through Scribe

Once the hand-built CTO path works, the next step is to hand a plain transcript to Scribe and let Scribe package it into the same lexical CTO shape.

Then run the exact same moderated annotation loop unchanged.

This validates the portable ingress path and proves that Scribe is part of the ecosystem value, not just a later convenience.

---

## Declarative target

The doctor-patient annotation workflow should not remain a Python-only assembly exercise.

The medium-term target is that this workflow can be described declaratively with minimal configuration, roughly specifying:

- use the lexical profile
- use a moderated annotation loop
- iterate over turns
- collect `speaker_attribution`
- allowed labels: `doctor`, `patient`
- optional `confidence`
- use a standard output mask

The current hand-built and programmatic path is the proof-of-concept substrate, not the final authoring experience.

---

## What success looks like

A successful first post-split milestone would show that:

- a short lexical CTO can be created and consumed without TraceProbe-specific semantics
- Adjacency can run a moderated annotation loop over turns
- annotations land in namespaced canonical annotation space via TTT
- the result can be exported in at least one useful portable form
- Scribe can later package a plain transcript into the same workflow without changing the workflow logic

---

## Why this milestone matters

This is a small but strategically important proof.

If it works, it demonstrates that:

- the split produced real generality, not just cleaner imports
- turn-oriented lexical CTOs are a viable common carrier
- Adjacency can support non-TraceProbe interaction workflows
- TTT remains boring and substrate-like underneath
- Scribe has a clear near-term role in the ecosystem

---

## UI target for this phase

The first UI target should be a **runtime session UI**, not a study-builder or full authoring surface.

That means the UI for this phase exists to validate:

- whether turn traversal feels natural
- whether the moderator-driven annotation flow is legible
- whether the lexical CTO shape supports live interaction cleanly
- whether the exported masks align with what the runtime presents

A richer authoring/configuration UI remains a later phase, after the declarative layer is more stable.

## Suggested immediate deliverables

1. A tiny hand-authored doctor-patient lexical CTO specimen
2. A minimal moderated annotation loop in Adjacency
3. A minimal NiceGUI-based runtime UI for that loop
4. One annotation track for speaker attribution
5. JSON and ANSI output masks for the annotated result
6. A follow-on path for transcript -> Scribe -> lexical CTO

---

## Non-goal for this phase

Do not attempt to solve all of the following immediately:

- rich multimodal support
- collaborative adjudication
- large ontology design
- full lexical annotation vocabulary
- advanced UI authoring
- full transcript ingestion generality

The goal of this phase is to prove the new architecture with the smallest realistic workflow.

---

## North star for this phase

**Hand-build one small lexical CTO, run one simple moderated annotation loop over it, exercise that workflow through a minimal runtime UI, persist the result through TTT, then prove that Scribe can feed the same workflow from a plain transcript.**

