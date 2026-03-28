"""Smoke tests for the ``adj`` command-line surface."""

from __future__ import annotations

from argparse import Namespace
from pathlib import Path

import pytest

from adjacency import cli


def test_build_parser_accepts_source_monitoring_annotation_import() -> None:
    parser = cli.build_parser()
    args = parser.parse_args(
        [
            "start",
            "source_monitoring_annotation",
            "--cto-import",
            "tests/adjacency/doctor_patient_knee_cto.json",
            "--session-code",
            "SMA-01",
        ]
    )

    assert args == Namespace(
        command="start",
        workflow="source_monitoring_annotation",
        cto_import="tests/adjacency/doctor_patient_knee_cto.json",
        session_code="SMA-01",
    )


def test_main_bootstraps_source_monitoring_workflow(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    calls: dict[str, object] = {}

    class DummyBackendConfig:
        def __init__(self, path: Path) -> None:
            calls["backend_config_path"] = path

    class DummyBackend:
        def __init__(self, config: DummyBackendConfig) -> None:
            calls["backend_config"] = config

    class DummyArchivist:
        def __init__(
            self, backends: list[tuple[DummyBackendConfig, DummyBackend]]
        ) -> None:
            calls["archivist_backends"] = backends

    class DummyHub:
        class DummyLibrarian:
            def get_cto(self, turn_id: object) -> object | None:
                calls["librarian_turn_id"] = turn_id
                return None

        def __init__(self) -> None:
            self.librarian = self.DummyLibrarian()

    class DummyAnnotator:
        def __init__(
            self,
            *,
            source_locator: str,
            renderer: object,
            session_code: str | None = None,
        ) -> None:
            calls["annotator_source_locator"] = source_locator
            calls["annotator_renderer"] = renderer
            calls["annotator_session_code"] = session_code
            self.turn_id = None

    class DummySession:
        async def start(self) -> None:
            calls["session_started"] = True

    def fake_start(archivist: object, annotator: object) -> DummyHub:
        calls["ttt_start"] = (archivist, annotator)
        return DummyHub()

    def fake_assemble_session(annotator: object) -> DummySession:
        calls["assembled_session_with"] = annotator
        return DummySession()

    monkeypatch.setattr(cli, "JsonlArchivistBackendConfig", DummyBackendConfig)
    monkeypatch.setattr(cli, "JsonlArchivistBackend", DummyBackend)
    monkeypatch.setattr(cli, "Archivist", DummyArchivist)
    monkeypatch.setattr(
        cli, "TTT", type("DummyTTT", (), {"start": staticmethod(fake_start)})
    )
    dummy_renderer = type("DummyRenderer", (), {"url": "http://127.0.0.1:8123/"})()
    monkeypatch.setattr(cli, "build_source_monitoring_renderer", lambda: dummy_renderer)
    monkeypatch.setattr(cli, "SourceMonitoringAnnotatorPurpose", DummyAnnotator)
    monkeypatch.setattr(
        cli, "assemble_source_monitoring_session", fake_assemble_session
    )

    cto_path = tmp_path / "doctor_patient_knee_cto.json"
    cto_path.write_text("{}")

    cli.main(
        [
            "start",
            "source_monitoring_annotation",
            "--cto-import",
            str(cto_path),
            "--session-code",
            "SMA-01",
        ]
    )

    assert calls["backend_config_path"] == Path("events.jsonl")
    assert calls["annotator_source_locator"] == str(cto_path)
    assert calls["annotator_session_code"] == "SMA-01"
    assert calls["annotator_renderer"] is dummy_renderer
    assert calls["session_started"] is True
    captured = capsys.readouterr()
    assert "Source monitoring UI: http://127.0.0.1:8123/" in captured.out
