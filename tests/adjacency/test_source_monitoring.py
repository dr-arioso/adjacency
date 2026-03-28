"""Tests for the built-in source monitoring annotation workflow."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from turnturnturn import TTT
from turnturnturn.archivist import (
    Archivist,
    JsonlArchivistBackend,
    JsonlArchivistBackendConfig,
)
from turnturnturn.errors import HubClosedError
from turnturnturn.profile import ProfileRegistry

from adjacency.profiles import LEXICAL_PROFILE_ID
from adjacency.profiles import register as register_profiles
from adjacency.source_monitoring import (
    ScriptedSourceMonitoringRenderer,
    SourceMonitoringAnnotatorPurpose,
    SourceMonitoringIntent,
    SourceMonitoringWorkflowController,
    assemble_source_monitoring_session,
)

FIXTURE_PATH = Path(__file__).with_name("doctor_patient_knee_cto.json")


def test_lexical_profile_validates_roster_and_turns():
    register_profiles()
    profile = ProfileRegistry.get(LEXICAL_PROFILE_ID, 1)
    content = {
        "speakers": [
            {"session_speaker_id": "doctor", "display_label": "Doctor"},
            {"session_speaker_id": "patient", "display_label": "Patient"},
        ],
        "turns": [
            {
                "source_turn_id": "turn_01",
                "ordinal": 1,
                "utterance": "What brings you in today?",
            }
        ],
    }

    profile.validate(content)


def test_lexical_profile_rejects_missing_turns():
    register_profiles()
    profile = ProfileRegistry.get(LEXICAL_PROFILE_ID, 1)

    with pytest.raises(ValueError):
        profile.validate(
            {
                "speakers": [
                    {"session_speaker_id": "doctor", "display_label": "Doctor"}
                ],
                "turns": [],
            }
        )


@pytest.mark.asyncio
async def test_source_monitoring_annotation_imports_and_writes_deltas(tmp_path):
    jsonl_path = tmp_path / "events.jsonl"
    jsonl_config = JsonlArchivistBackendConfig(path=jsonl_path)
    archivist = Archivist(
        backends=[(jsonl_config, JsonlArchivistBackend(jsonl_config))]
    )
    renderer = ScriptedSourceMonitoringRenderer(
        [
            "doctor",
            "patient",
            "doctor",
            "patient",
            "doctor",
            "patient",
            "doctor",
            "patient",
            "doctor",
            "patient",
            "doctor",
            "patient",
        ]
    )
    annotator = SourceMonitoringAnnotatorPurpose(
        source_locator=str(FIXTURE_PATH),
        renderer=renderer,
        session_code="SMA-01",
    )
    hub = TTT.start(archivist, annotator)
    session = assemble_source_monitoring_session(annotator)

    await session.start()

    assert annotator.turn_id is not None
    cto = hub.librarian.get_cto(annotator.turn_id)
    assert cto is not None
    annotations = cto.observations["adjacency.source_monitoring"]
    assert len(annotations) == 12
    assert annotations[0]["key"] == "turn_01"
    assert annotations[0]["value"]["selection"] == "doctor"
    assert annotations[0]["value"]["request_review"] is False
    assert annotations[-1]["key"] == "turn_12"
    assert annotations[-1]["value"]["selection"] == "patient"

    records = [json.loads(line) for line in jsonl_path.read_text().splitlines()]
    event_types = [record["event_type"] for record in records]
    assert "request_cto" in event_types
    assert "cto_imported" in event_types
    assert "cto_started" in event_types
    assert "delta_merged" in event_types
    assert "adjacency.workflow_completed" in event_types
    assert "request_session_end" in event_types
    assert "session_completed" in event_types
    assert event_types.index("adjacency.workflow_completed") < event_types.index(
        "request_session_end"
    )

    with pytest.raises(HubClosedError):
        await hub.start_purpose(annotator)


def test_source_monitoring_normalizes_reserved_outcomes():
    renderer = ScriptedSourceMonitoringRenderer(["unknown"])
    purpose = SourceMonitoringAnnotatorPurpose(
        source_locator=str(FIXTURE_PATH),
        renderer=renderer,
    )
    speakers = [
        {"session_speaker_id": "doctor", "display_label": "Doctor"},
        {"session_speaker_id": "patient", "display_label": "Patient"},
    ]

    assert purpose._normalize_selection("unknown", speakers) == "unknown"
    assert purpose._normalize_selection("doctor", speakers) == "doctor"
    assert purpose._normalize_selection("", speakers) == "blank"

    with pytest.raises(ValueError):
        purpose._normalize_selection("nurse", speakers)


def test_controller_blank_bypass_emits_no_submission():
    controller = _make_controller()

    transition = controller.handle_intent(SourceMonitoringIntent(kind="leave_blank"))

    assert transition.submission is None
    assert transition.completed is False
    snapshot = controller.snapshot()
    assert snapshot.transcript.active_index == 1
    assert snapshot.transcript.items[0].status == "blank"


def test_controller_submit_then_review_toggle_resubmits_if_dirty():
    controller = _make_controller()

    transition = controller.handle_intent(
        SourceMonitoringIntent(kind="select_speaker", selection="doctor")
    )
    assert transition.submission is None

    transition = controller.handle_intent(
        SourceMonitoringIntent(kind="submit_annotation")
    )
    assert transition.submission is not None
    assert transition.submission.state.selection == "doctor"
    assert transition.submission.state.request_review is False

    controller.handle_intent(SourceMonitoringIntent(kind="navigate_up"))
    controller.handle_intent(SourceMonitoringIntent(kind="toggle_request_review"))
    transition = controller.handle_intent(SourceMonitoringIntent(kind="navigate_down"))
    assert transition.submission is not None
    assert transition.submission.state.selection == "doctor"
    assert transition.submission.state.request_review is True


def test_controller_toggle_back_to_persisted_state_emits_no_resubmit():
    controller = _make_controller()
    controller.handle_intent(
        SourceMonitoringIntent(kind="select_speaker", selection="doctor")
    )
    controller.handle_intent(SourceMonitoringIntent(kind="submit_annotation"))
    controller.handle_intent(SourceMonitoringIntent(kind="navigate_up"))
    controller.handle_intent(SourceMonitoringIntent(kind="toggle_request_review"))
    controller.handle_intent(SourceMonitoringIntent(kind="toggle_request_review"))

    transition = controller.handle_intent(SourceMonitoringIntent(kind="navigate_down"))

    assert transition.submission is None


def test_controller_complete_focuses_first_blank_item():
    controller = _make_controller(turn_count=3)
    controller.handle_intent(
        SourceMonitoringIntent(kind="select_speaker", selection="doctor")
    )
    controller.handle_intent(SourceMonitoringIntent(kind="submit_annotation"))
    controller.handle_intent(SourceMonitoringIntent(kind="leave_blank"))
    controller.handle_intent(
        SourceMonitoringIntent(kind="select_speaker", selection="doctor")
    )
    controller.handle_intent(SourceMonitoringIntent(kind="submit_annotation"))

    transition = controller.handle_intent(
        SourceMonitoringIntent(kind="complete_workflow")
    )

    assert transition.completed is False
    assert controller.snapshot().transcript.active_index == 1


def test_controller_complete_after_unknown_emits_terminal_transition():
    controller = _make_controller(turn_count=2)
    controller.handle_intent(SourceMonitoringIntent(kind="select_unknown"))
    controller.handle_intent(SourceMonitoringIntent(kind="submit_annotation"))
    controller.handle_intent(SourceMonitoringIntent(kind="select_unknown"))

    transition = controller.handle_intent(
        SourceMonitoringIntent(kind="complete_workflow")
    )

    assert transition.submission is not None
    assert transition.submission.state.selection == "unknown"
    assert transition.completed is True


def _make_controller(turn_count: int = 2) -> SourceMonitoringWorkflowController:
    speakers = [
        {"session_speaker_id": "doctor", "display_label": "Doctor"},
        {"session_speaker_id": "patient", "display_label": "Patient"},
    ]
    turns = [
        {
            "source_turn_id": f"turn_{index + 1:02d}",
            "ordinal": index + 1,
            "utterance": f"Utterance {index + 1}",
            "raw_source_tag": f"speaker_{index % 2}",
        }
        for index in range(turn_count)
    ]
    return SourceMonitoringWorkflowController(
        speakers=speakers,
        turns=turns,
        session_code="SMA-TEST",
        source_label="fixture.json",
    )
