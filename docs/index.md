# Study Stack

Three repos, one dependency direction:

```
turnturnturn  ←  adjacency  ←  traceprobe
```

**turnturnturn** — event hub and CTO lifecycle. No domain knowledge; pure infrastructure.

**adjacency** — structured elicitation framework. Defines the session model, participant abstraction, protocol format, and `assemble_session()` factory. Build study tools on top of this.

**traceprobe** — LLM trace mutation study tool and reference implementation of how to build on adjacency. Purpose-specific, but intended to be slim enough to read as an example.

---

## Dev setup

From `~/projects/`:

```bash
./dev-setup.sh
```

Installs all three as editable packages and configures pre-commit hooks in each repo. Requires Python 3.12+ and a virtualenv active.

Multi-root workspace: `~/projects/study-stack.code-workspace`

---

## Seam contract

`grep -r "traceprobe" ~/projects/adjacency/src/` must return nothing. Adjacency has no knowledge of TraceProbe. If a capability is needed in both, it belongs in adjacency (or turnturnturn).

---

## Known future work

### MkDocs not yet configured

turnturnturn has a complete MkDocs setup (material theme, mkdocstrings, API nav). adjacency and traceprobe do not yet have `mkdocs.yml` or mkdocs dependencies. Both need:

- `mkdocs.yml` mirroring turnturnturn's configuration
- mkdocs + mkdocs-material + mkdocstrings[python] + griffe + interrogate added to `pyproject.toml` dev deps
- `docs/api/` pages wired into the nav

### Docstring gaps

**adjacency** (~95% coverage) — small gaps:
- `ParticipantPurpose.__init__()` — missing docstring
- `AnthropicBackend.complete()`, `LLMParticipant.assess()`, `LadderState.record_verdict()` — missing Args/Returns
- `assemble_session()` — missing Returns section

**traceprobe** (~70% coverage) — significant gaps in pre-existing code:
- `backends.py` — `BackendError` and all concrete model classes missing most docstrings
- `roles.py` — `ModelSubject`, `HumanInterviewer`, `ModelReviewer` missing multiple docstrings
- `purposes/moderator.py` — `SocraticModerator` methods missing docstrings
- `loader.py`, `cli.py`, `runner.py`, `profiles.py`, `participants/heuristic.py`, `assemble.py` — scattered gaps

**turnturnturn** (~98%) — `_EventPolicy` dataclass missing docstring (private, low priority)

### Open design questions

**AdjacencyLibrarian placement** — currently lives in adjacency because it needs to be reachable without traceprobe, but it carries TraceProbe-shaped assumptions (exhibit ID → scoring config). Revisit when the content model matures.

**TraceProbe diet** — TraceProbe is intended to be a clean, slim reference implementation. `roles.py` and `backends.py` carry legacy complexity that predates the adjacency split. Both are candidates for simplification.
