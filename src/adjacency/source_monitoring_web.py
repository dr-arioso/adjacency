"""NiceGUI surface for the source monitoring workflow."""

from __future__ import annotations

import asyncio
import queue
import socket
import threading
from dataclasses import dataclass
from typing import Any, Literal

from adjacency.interaction_renderer import InteractionRenderer
from adjacency.source_monitoring import (
    SourceMonitoringIntent,
    SourceMonitoringRenderRequest,
)


def _find_free_port(host: str) -> int:
    """Reserve an ephemeral local TCP port for the NiceGUI server."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((host, 0))
        return int(sock.getsockname()[1])


@dataclass
class _UiRefs:
    """Mutable references to the top-level NiceGUI widgets that refresh in place."""

    header: Any
    progress: Any
    footer: Any
    complete_button: Any
    active_card: Any
    history_panel: Any
    instructions: Any


class NiceGuiSourceMonitoringRenderer(
    InteractionRenderer[SourceMonitoringRenderRequest, SourceMonitoringIntent]
):
    """NiceGUI implementation of the source-monitoring renderer contract."""

    def __init__(
        self,
        *,
        host: str = "127.0.0.1",
        port: int | None = None,
        route: str = "/",
        refresh_seconds: float = 0.1,
    ) -> None:
        """Create a long-lived NiceGUI renderer for one workflow session."""
        self.host = host
        self.port = port or _find_free_port(host)
        self.route = route
        self.refresh_seconds = refresh_seconds
        self.url = f"http://{self.host}:{self.port}{self.route}"
        self._snapshot: SourceMonitoringRenderRequest | None = None
        self._snapshot_lock = threading.Lock()
        self._intent_queue: queue.Queue[SourceMonitoringIntent] = queue.Queue()
        self._server_started = False
        self._server_lock = threading.Lock()

    async def publish(self, request: SourceMonitoringRenderRequest) -> None:
        """Store the latest workflow snapshot and lazily start the web server."""
        self._ensure_server_started()
        with self._snapshot_lock:
            self._snapshot = request

    async def next_intent(self) -> SourceMonitoringIntent:
        """Wait for the next user intent emitted from the web surface."""
        self._ensure_server_started()
        return await asyncio.to_thread(self._intent_queue.get)

    def _ensure_server_started(self) -> None:
        """Start the NiceGUI server exactly once for this renderer instance."""
        with self._server_lock:
            if self._server_started:
                return
            thread = threading.Thread(
                target=self._run_server,
                name="adjacency-source-monitoring-web",
                daemon=True,
            )
            thread.start()
            self._server_started = True

    def _run_server(self) -> None:
        """Run the NiceGUI app on its dedicated background thread."""
        try:
            from nicegui import ui
        except ModuleNotFoundError as exc:  # pragma: no cover - runtime guard
            raise RuntimeError(
                "NiceGUI is required for the default source-monitoring web surface. "
                "Install adjacency with the NiceGUI dependency or choose the "
                "console renderer explicitly."
            ) from exc

        @ui.page(self.route)
        def source_monitoring_page() -> None:
            refs = self._build_page(ui)
            loading_state = {"shown": False}
            last_rendered: dict[str, SourceMonitoringRenderRequest | None] = {
                "snapshot": None
            }

            def refresh() -> None:
                snapshot = self._snapshot_copy()
                if snapshot is None:
                    if loading_state["shown"]:
                        return
                    refs.header.text = "Waiting for imported CTO content..."
                    refs.progress.text = ""
                    refs.footer.text = "Loading source monitoring session..."
                    refs.complete_button.disable()
                    refs.instructions.clear()
                    with refs.instructions:
                        ui.spinner(size="lg")
                    refs.history_panel.clear()
                    refs.active_card.clear()
                    with refs.active_card:
                        ui.spinner(size="lg")
                    loading_state["shown"] = True
                    last_rendered["snapshot"] = None
                    return
                if snapshot == last_rendered["snapshot"]:
                    return
                self._refresh_page(ui, refs, snapshot)
                last_rendered["snapshot"] = snapshot
                loading_state["shown"] = False

            ui.timer(self.refresh_seconds, refresh)
            ui.keyboard(on_key=self._handle_key)

        ui.run(
            host=self.host,
            port=self.port,
            reload=False,
            show=False,
            title="Adjacency Source Monitoring",
        )

    def _snapshot_copy(self) -> SourceMonitoringRenderRequest | None:
        """Read the latest published snapshot under a lock."""
        with self._snapshot_lock:
            return self._snapshot

    def _build_page(self, ui: Any) -> _UiRefs:
        """Construct the static single-page layout and retain refreshable refs."""
        with ui.column().classes("w-full gap-4 p-4"):
            with ui.row().classes("w-full items-start justify-between"):
                with ui.column():
                    header = ui.label("Waiting for imported CTO content...").classes(
                        "text-2xl font-semibold"
                    )
                    progress = ui.label("")
                footer = ui.label("")
            with ui.row().classes("w-full gap-4 items-start"):
                with ui.column().classes("w-2/3 gap-2"):
                    active_card = ui.card().classes("w-full min-h-64")
                    with ui.row().classes("w-full justify-between"):
                        ui.button(
                            "Previous", on_click=lambda: self._enqueue("navigate_up")
                        )
                        complete_button = ui.button(
                            "Complete",
                            on_click=lambda: self._enqueue("complete_workflow"),
                        )
                        ui.button(
                            "Next", on_click=lambda: self._enqueue("navigate_down")
                        )
                    history_panel = ui.column().classes("w-full gap-2")
                with ui.card().classes("w-1/3") as instructions:
                    ui.label("Instructions").classes("text-lg font-medium")
        return _UiRefs(
            header=header,
            progress=progress,
            footer=footer,
            complete_button=complete_button,
            active_card=active_card,
            history_panel=history_panel,
            instructions=instructions,
        )

    def _refresh_page(
        self, ui: Any, refs: _UiRefs, snapshot: SourceMonitoringRenderRequest
    ) -> None:
        """Render the latest workflow snapshot into the existing widget tree."""
        refs.header.text = (
            f"{snapshot.session.workflow_name} · "
            f"{snapshot.session.session_code or 'no session code'}"
        )
        refs.progress.text = snapshot.session.progress_label
        refs.footer.text = snapshot.footer.message
        if snapshot.footer.can_complete:
            refs.complete_button.enable()
        else:
            refs.complete_button.disable()

        refs.instructions.clear()
        with refs.instructions:
            ui.label(snapshot.instructions.title).classes("text-lg font-medium")
            for line in snapshot.instructions.body:
                ui.label(line)
            ui.separator()
            ui.label("Speaker shortcuts").classes("font-medium")
            for entry in snapshot.instructions.speaker_shortcuts:
                ui.label(f"[{entry.shortcut}] {entry.display_label}")
            ui.separator()
            ui.label("Controls").classes("font-medium")
            for key, value in snapshot.affordances.shortcut_hints.items():
                ui.label(
                    f"{snapshot.affordances.control_labels.get(key, key)} [{value}]"
                )

        refs.active_card.clear()
        active_item = snapshot.transcript.items[snapshot.transcript.active_index]
        with refs.active_card:
            ui.label(f"Turn {active_item.ordinal}").classes("text-lg font-medium")
            if active_item.raw_source_tag:
                ui.label(f"Raw source: {active_item.raw_source_tag}")
            ui.markdown(active_item.utterance)
            with ui.row().classes("gap-2"):
                for entry in snapshot.instructions.speaker_shortcuts:
                    button = ui.button(
                        f"{entry.display_label} [{entry.shortcut}]",
                        on_click=lambda speaker_id=entry.session_speaker_id: self._enqueue(
                            "select_speaker", selection=speaker_id
                        ),
                    )
                    if not active_item.selection_editable:
                        button.disable()
                unknown_button = ui.button(
                    f"{snapshot.affordances.control_labels['unknown']} [u]",
                    on_click=lambda: self._enqueue("select_unknown"),
                )
                if not active_item.selection_editable:
                    unknown_button.disable()
            with ui.row().classes("gap-2"):
                blank_button = ui.button(
                    f"{snapshot.affordances.control_labels['leave_blank']} [Space]",
                    on_click=lambda: self._enqueue("leave_blank"),
                )
                if not active_item.selection_editable:
                    blank_button.disable()
                review_checkbox = ui.checkbox(
                    f"{snapshot.affordances.control_labels['request_review']} [r]",
                    value=active_item.request_review,
                    on_change=lambda event, current=active_item.request_review: self._handle_review_change(
                        event, current
                    ),
                )
                if not active_item.request_review_editable:
                    review_checkbox.disable()
                ui.button(
                    f"{snapshot.affordances.control_labels['submit']} [Ctrl+Enter]",
                    on_click=lambda: self._enqueue("submit_annotation"),
                )
            ui.label(f"Current selection: {active_item.current_selection or '<blank>'}")

        refs.history_panel.clear()
        with refs.history_panel:
            ui.label("Transcript").classes("text-lg font-medium")
            for index, item in enumerate(snapshot.transcript.items):
                css = "opacity-40" if item.status != "active" else "opacity-100 ring-2"
                with ui.card().classes(f"w-full {css}"):
                    ui.label(f"Turn {item.ordinal} · {item.status}")
                    ui.label(item.utterance)
                    if item.current_selection is not None:
                        ui.label(f"Selection: {item.current_selection}")
                    if item.request_review:
                        ui.label("Request review enabled")
                    if index == snapshot.transcript.active_index:
                        ui.label("Active").classes("font-medium")

    def _handle_key(self, event: Any) -> None:
        """Translate keyboard shortcuts into source-monitoring intents."""
        snapshot = self._snapshot_copy()
        if snapshot is None or not getattr(event.action, "keydown", False):
            return
        active = snapshot.transcript.items[snapshot.transcript.active_index]
        keyboard_key = getattr(event, "key", None)
        key_name = getattr(keyboard_key, "name", keyboard_key)
        key = str(key_name).lower()
        modifiers = {
            str(getattr(modifier, "name", modifier)).lower()
            for modifier in getattr(event, "modifiers", [])
        }
        if key == "r":
            self._enqueue("toggle_request_review")
            return
        if key == "u":
            self._enqueue("select_unknown")
            return
        if key == "arrowup":
            self._enqueue("navigate_up")
            return
        if key == "arrowdown":
            self._enqueue("navigate_down")
            return
        if key == " ":
            self._enqueue("leave_blank")
            return
        if key == "enter" and ("control" in modifiers or "ctrl" in modifiers):
            self._enqueue("submit_annotation")
            return
        for entry in snapshot.instructions.speaker_shortcuts:
            if key == entry.shortcut.lower():
                self._enqueue(
                    "select_speaker",
                    source_turn_id=active.source_turn_id,
                    selection=entry.session_speaker_id,
                )
                return

    def _enqueue(
        self,
        kind: Literal[
            "select_speaker",
            "select_unknown",
            "leave_blank",
            "toggle_request_review",
            "submit_annotation",
            "navigate_up",
            "navigate_down",
            "complete_workflow",
        ],
        *,
        source_turn_id: str | None = None,
        selection: str | None = None,
    ) -> None:
        """Push one normalized intent into the renderer intent queue."""
        if kind == "select_unknown":
            self._intent_queue.put(SourceMonitoringIntent(kind="select_unknown"))
            return
        self._intent_queue.put(
            SourceMonitoringIntent(
                kind=kind, source_turn_id=source_turn_id, selection=selection
            )
        )

    def _handle_review_change(self, event: Any, current_value: bool) -> None:
        """Translate checkbox changes into the toggle-based controller intent."""
        desired_value = bool(getattr(event, "value", current_value))
        if desired_value == current_value:
            return
        self._enqueue("toggle_request_review")
