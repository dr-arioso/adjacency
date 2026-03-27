"""CLI entrypoint for built-in Adjacency workflows."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from turnturnturn import (
    TTT,
    Archivist,
    JsonlArchivistBackend,
    JsonlArchivistBackendConfig,
)

from adjacency.source_monitoring import (
    ConsoleSourceMonitoringBackend,
    SourceMonitoringAnnotatorPurpose,
    assemble_source_monitoring_session,
)


def build_parser() -> argparse.ArgumentParser:
    """Build the top-level `adj` CLI parser."""
    parser = argparse.ArgumentParser(
        prog="adj",
        description="Run built-in Adjacency workflows.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    start = subparsers.add_parser("start", help="Start a built-in workflow")
    start.add_argument(
        "workflow",
        choices=["source_monitoring_annotation"],
        help="Built-in workflow to start.",
    )
    start.add_argument(
        "--cto-import",
        required=True,
        dest="cto_import",
        help="Path to a canonical cto_json document.",
    )
    start.add_argument(
        "--session-code",
        default=None,
        help="Optional caller-defined session code for lifecycle provenance.",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    """Parse CLI args and run the requested workflow."""
    parser = build_parser()
    args = parser.parse_args(argv)
    asyncio.run(_run(args))


async def _run(args: argparse.Namespace) -> None:
    """Execute a parsed CLI command."""
    if args.command != "start" or args.workflow != "source_monitoring_annotation":
        raise ValueError(f"unsupported command/workflow: {args!r}")

    jsonl_config = JsonlArchivistBackendConfig(path=Path("events.jsonl"))
    archivist = Archivist(
        backends=[(jsonl_config, JsonlArchivistBackend(jsonl_config))]
    )
    annotator = SourceMonitoringAnnotatorPurpose(
        source_locator=args.cto_import,
        backend=ConsoleSourceMonitoringBackend(),
        session_code=args.session_code,
    )
    hub = TTT.start(archivist, annotator)
    session = assemble_source_monitoring_session(annotator)
    await session.start()
    if annotator.turn_id is not None:
        cto = hub.librarian.get_cto(annotator.turn_id)
        if cto is not None:
            print(f"Annotated {len(cto.content['turns'])} turns.")


if __name__ == "__main__":
    main()
