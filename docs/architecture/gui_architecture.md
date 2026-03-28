# GUI Architecture

This document describes the current GUI direction for `adjacency`.

It is not a finished product spec. It is a working architecture note covering:

- GUI goals
- the current implementation state
- the near-term plan
- the reusable `FocusedSequenceViewport` component direction

## Goals

The GUI layer in `adjacency` should support structured human workflows without
forcing workflow logic into the UI implementation.

The current goals are:

- keep workflow state authoritative in `adjacency` workflow code
- keep presentation concerns inside an interaction surface / renderer layer
- support multiple human-facing surfaces over the same workflow contract
- make the main sequence-navigation component reusable across workflows
- avoid locking the architecture to the first rough source-monitoring UI

The longer-term aim is not "a source-monitoring GUI." It is a small family of
reusable interaction surfaces for structured human work.

## Current State

Today, `adjacency` has:

- a thin `InteractionRenderer` seam
- a source-monitoring workflow controller that owns authoritative state
- a NiceGUI-based first web surface
- console and scripted fallbacks using the same workflow/controller contract

This is already a healthy seam:

- `turnturnturn` does not need GUI changes
- workflow state and provenance remain mesh-native
- GUI behavior can evolve inside `adjacency`

The current NiceGUI surface is intentionally a proving prototype. It is useful
because it exercises:

- the renderer contract
- the workflow/controller boundary
- keyboard and mouse interaction
- incremental provenance writes

It is not yet the intended reusable visual design.

## Current Plan

Near-term GUI work should focus on:

1. tightening the interaction feel of the existing web surface
2. extracting the reusable sequence-navigation shell from the current
   source-monitoring layout
3. letting workflows provide content and controls to that shell

What should remain code-owned:

- progression rules
- completion rules
- normalization and validation
- provenance timing
- authoritative per-item state

What can become more declarative over time:

- control visibility
- labels and copy
- keyboard hints
- layout variants
- which standard workflow actions are shown

We should resist over-generalizing the renderer contract too early. The seam
should become more reusable because the component boundary is good, not because
we prematurely invent a universal workflow schema.

## FocusedSequenceViewport

The key reusable GUI component should be `FocusedSequenceViewport`.

That name is intentionally broader than "transcript scroller" because the same
interaction shape can work for:

- transcript annotation
- conversational analysis
- coder calibration
- form completion
- surveys
- future image or illustration-centric workflows

### Component Idea

`FocusedSequenceViewport` renders a linear sequence around one active window.

It should support:

- dimmed prior context above the active window
- a focused active window in the center
- dimmed upcoming context below
- navigation across viewed items
- workflow-level action controls
- a compact status / instruction band

The active unit is intentionally pluggable. It may be:

- one turn
- a turn pair
- a span
- a survey item
- a record
- a future non-text artifact

So the reusable abstraction is not "utterance annotation." It is "structured
work over a focused sequence unit."

### Standard Workflow Actions

The current likely shared action set is:

- `Submit`
- `Leave Blank`
- `Save for later`
- `Complete`

These should probably live at the component-shell level, with each workflow
deciding:

- which actions are visible
- which are enabled
- what each action means semantically

This keeps workflows from re-inventing the shell while preserving workflow
authority over state transitions.

### Slots / Regions

The current direction is a component with a few stable regions:

- header region
  - session/workflow/progress/source context
- status/instruction band
  - immediate status, errors, and short instructions
- action bar
  - shared workflow actions such as submit and complete
- viewport body
  - prior context
  - active window
  - upcoming context
- sidecar controls region
  - compact checkboxes, flags, or short secondary controls

The workflow should supply the active item content and the workflow-specific
controls. The viewport shell should supply the sequence framing and navigation
behavior.

## Why NiceGUI For Now

NiceGUI is a good current choice because it gives us:

- Python-first iteration
- local or remote web sessions
- keyboard event handling
- enough layout and custom styling flexibility to prove the component boundary

It is probably not the final answer if `adjacency` grows into a highly polished,
animation-heavy frontend product. That is acceptable.

The near-term architectural goal is:

- prove the renderer seam
- prove the reusable viewport concept
- avoid embedding workflow logic in the GUI

If we later outgrow NiceGUI or Quasar constraints, a clean component and
renderer boundary will make that migration much safer.

## Web Target And Console Fallback

`FocusedSequenceViewport` should have two explicit targets:

### Web Target

The web target is the richer surface.

It should support:

- a visually dominant active window
- dimmed prior and upcoming context
- compact sidecar controls
- persistent status and instruction bands
- keyboard and mouse interaction
- the more distinctive GUI layout language we want for `adjacency`

This is the primary design target for workflows such as:

- source monitoring annotation
- CA annotation
- coder calibration
- sequence-oriented form completion

### Console Fallback Target

The console target should be compatible, but not visually equivalent.

It should preserve the same semantics while accepting a simpler presentation,
for example:

- compact header and status lines
- the active item rendered centrally in terminal output
- a short slice of prior and upcoming context
- action hints and keyboard commands
- the same submission, blank-bypass, and completion rules

The goal is not to reproduce the full web design in a terminal. The goal is to
preserve workflow behavior and user affordances as faithfully as practical.

If terminal interaction later becomes important enough to justify a richer
implementation, `Textual` is the more likely path than stretching raw `rich`
too far. Until then, the console path should remain a compatible fallback.

### Minimum Shared Semantics

Across web and console surfaces, the following should remain stable:

- one authoritative workflow/controller state machine
- one focused active sequence unit at a time
- the same standard workflow actions
  - `Submit`
  - `Leave Blank`
  - `Save for later`
  - `Complete`
- the same completion gating rules
- the same provenance timing and latest-write-wins semantics
- the same distinction between workflow-owned state and surface-local state

So the shared contract is behavioral, not visual.

## Relationship To Source Monitoring

`source_monitoring_annotation` is the first consumer of this GUI direction, not
the definition of it.

That workflow is useful because it pressures:

- focused sequence navigation
- per-item submission and resubmission
- blank bypass behavior
- completion gating
- compact secondary flags like `Request review`

But the GUI architecture should not be named or shaped around source monitoring
alone.

## Open Questions

The important questions still open are:

- how much of the shell layout should be configurable vs fixed
- whether `Submit` should stay button-only or also use keyboard submit
- how the component should handle active units that contain more than one
  sequence record, such as turn pairs
- how much custom CSS/animation to invest in while still on NiceGUI
- when to elevate `FocusedSequenceViewport` from design direction to an actual
  reusable component in code

## Practical Direction

The practical next move is:

1. treat the current source-monitoring NiceGUI surface as a prototype
2. refine the visual shell toward the `FocusedSequenceViewport` shape
3. keep extracting reusable GUI structure in `adjacency`
4. let additional workflows reuse that structure only once the seam feels
   stable

That keeps us from locking the architecture to an underdeveloped first UI while
still making concrete progress.
