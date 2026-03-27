# PR Plan: `cto_json` Import Path + `source_monitoring_annotation`

## Summary

- First implementation step: create `/home/arioso/projects/adjacency/docs/plans/2026-03-25-source-monitoring-annotation-cto-import-pr-plan.md` and copy this plan into it. Leave it unlinked for now; MkDocs-in-all-repos stays backlog.
- Goal: land a mesh-native CTO import path in `turnturnturn`, then use it to add the first built-in generic `adjacency` workflow: `source_monitoring_annotation`.
- Scope for this PR:
  - `turnturnturn`: request/import/adopt imported CTOs
  - `adjacency`: `lexical_v0_1`, owner/annotator workflow, `adj` CLI
  - shared sample `cto_json` fixture
- Explicitly deferred from this PR:
  - annotator UX polish / console flow design
  - output masks / exports
  - Scribe integration
  - MkDocs setup in `adjacency` and `traceprobe`
  - hook cleanup

## Planned Commit Structure

1. **TTT request/import events**
   - Add built-in purpose events `cto_request` and `cto_imported`.
   - Add `BasePurpose.request_cto(*, session_id, source_kind, source_locator, session_code=None, request_id=None)`.
   - `cto_request` is allowed only while the hub is `open`.
   - `cto_request` is persisted like any accepted purpose event, then relayed to the persistence purpose only.

2. **Canonical `cto_json` schema**
   - Add one canonical serialized CTO document family with `schema` and `version`.
   - Ordinary import reads the full document shape, not a separate input schema.
   - Imported live identity is always reminted:
     - new live `turn_id`
     - new live `created_at_ms`
     - new live `last_event_id`
     - current session’s `session_id` / `session_code`
   - Imported observations become live canonical observations and keep their original namespaces.
   - Imported historical/session/source metadata is preserved separately under a reserved TTT provenance namespace, not as live session authority.

3. **Archivist-backed import**
   - `Archivist` handles `cto_request` for `source_kind="cto_json"` only in v1.
   - Dedupe requests with the agreed hybrid policy:
     - use explicit `request_id` when present
     - otherwise derive a stable key from source kind + source locator + content hash
   - `Archivist` emits `cto_imported` with:
     - the normalized imported `cto_json`
     - source metadata
     - original requester identity / request linkage
     - target live session id/code

4. **Hub adoption path**
   - Hub accepts `cto_imported` only from the registered persistence purpose.
   - Event order is fixed:
     1. `cto_request`
     2. `cto_imported`
     3. hub adopts imported CTO into live canonical state
     4. `cto_started`
   - `cto_started.submitted_by_*` should identify the original requester, not Archivist.
   - The first imported turn for a session establishes normal session ownership just like `start_turn()`.

5. **Adjacency-owned lexical profile**
   - Add an `adjacency` profile registration module and register `lexical_v0_1`.
   - This profile belongs in `adjacency`, not `turnturnturn`.
   - `lexical_v0_1` supports one or more turns in the same lexical CTO.
   - Base content shape for v1:
     - `speakers`: roster entries with `session_speaker_id`, `display_label`, optional `external_speaker_id`
     - `turns`: ordered turn entries with `source_turn_id`, `ordinal`, `utterance`, optional `raw_source_tag`
   - Canonical speaker attribution is not in base content; it is added by the workflow.

6. **Built-in `source_monitoring_annotation` workflow**
   - Add a new built-in workflow module in `adjacency`; do not retrofit the existing Socratic `Session` path for this PR.
   - Use a single `SourceMonitoringAnnotatorPurpose` that is also the `SessionOwnerPurpose` for v1.
   - No moderator in v1.
   - On startup, this purpose requests the imported CTO.
   - On `cto_started` for `lexical_v0_1`, it reads the full CTO and runs the annotation loop over `content.turns`.
   - Annotation decisions normalize to:
     - a selected `session_speaker_id`, or
     - reserved outcomes `blank`, `unknown`, `escalate`
   - Persist annotations through TTT deltas in namespace `adjacency.source_monitoring`, keyed by `source_turn_id`.
   - When all turns are annotated, the same purpose ends the session.

7. **CLI and runtime defaults**
   - Add `adj` as the `adjacency` console script.
   - Initial command:
     - `adj start source_monitoring_annotation --cto-import <path>`
   - No `ca_annotation` alias in v1.
   - No command-line content construction in v1.
   - Default persistence for the CLI is `Archivist` with a JSONL backend.
   - CLI bootstraps:
     - adjacency profile registration
     - default Archivist
     - one `SourceMonitoringAnnotatorPurpose`
     - workflow run

8. **Fixture, docs, and propagation**
   - Add one shared canonical `cto_json` fixture: a 10-12 turn doctor-patient office visit about a red, swollen knee in a 42-year-old, with the clinical details already agreed.
   - Make that fixture the primary import/export test artifact instead of ad hoc inline CTO constructors where practical.
   - Update TTT architecture/API docs to mention the second turn-ingress path.
   - Update `adjacency` docs to describe `source_monitoring_annotation` as the first built-in generic workflow.

## Public Interfaces / Contracts

- `turnturnturn.base_purpose.BasePurpose.request_cto(...)`
- New purpose-event payloads for `cto_request` and `cto_imported`
- New `adjacency` profile registration entrypoint for `lexical_v0_1`
- New built-in workflow module for `source_monitoring_annotation`
- New CLI command: `adj start source_monitoring_annotation --cto-import <path>`

## Delegation Plan

- **Worker A: TTT import substrate**
  - Owns commits 1-4.
  - Write scope: `turnturnturn` only.
  - Files: purpose events, `BasePurpose`, `hub`, `persistence`, `archivist`, new `cto_json` helper, TTT tests.
- **Worker B: Adjacency lexical profile + workflow core**
  - Owns commits 5-6.
  - Write scope: `adjacency` workflow/profile modules and tests only.
  - Keep existing Socratic session code untouched except where a new workflow hook is strictly necessary.
- **Worker C: Adjacency CLI + doc/fixture consumers**
  - Owns commit 7 and the adjacency side of commit 8.
  - Write scope: `adjacency` CLI, `pyproject.toml`, workflow docs, CLI tests.
- **Main rollout**
  - Integrates the shared fixture, cross-repo test updates, and any traceprobe compatibility checks.
  - Keeps ownership of the final doc write-up and commit sequencing.
- Recommended mapping to available subagents if used:
  - `explore_turnturnturn` / Bacon -> Worker A
  - `adjacency_owner_coupling` / Linnaeus -> Worker B
  - `explore_adjacency` / Tesla -> Worker C
  - `ttt_startup_surface` / Carver -> review/verification pass on hub lifecycle interactions

## Test Plan

- **TTT**
  - `cto_request` allowed in `open`, rejected in `closing` and `closed`
  - idempotent repeated imports
  - imported observations remain live and namespaced as provided
  - historical/source/session metadata lands in reserved TTT provenance data
  - live CTO identity is reminted
  - `cto_started` reports the original requester
  - only the persistence purpose may emit `cto_imported`
- **Adjacency**
  - `lexical_v0_1` profile validates roster + turns
  - `source_monitoring_annotation` starts from imported `cto_json`
  - annotation loop writes per-turn deltas keyed by `source_turn_id`
  - reserved outcomes `blank`, `unknown`, `escalate` normalize correctly
  - workflow ends the session cleanly
  - CLI smoke test for `adj start source_monitoring_annotation --cto-import <path>`
- **Cross-repo**
  - existing `traceprobe` smoke/integration tests still pass unchanged

## Assumptions / Defaults

- Workflow name is `source_monitoring_annotation`.
- V1 import source is filesystem-backed `cto_json` only.
- Imported observations are trusted and become live canonical observations.
- Imported session/turn identity is historical only; live identity is reminted.
- `lexical_v0_1` is owned by `adjacency` and supports one or more turns.
- The v1 workflow uses one combined owner+annotator purpose.
- Annotator UX details remain a separate design pass.
- Backlog items to keep visible but out of this PR:
  - hook cleanup
  - MkDocs working in all repos
