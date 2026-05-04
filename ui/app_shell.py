"""
AppShell - unified application shell for the VSM Evidence Workbench.

Replaces the MDI-based MainWindow with a left-sidebar + stacked-page layout.
All backend managers live here; pages receive references to them.
"""
import logging
import os
import time
from PyQt6.QtWidgets import (QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
                             QMessageBox, QStackedWidget)
from PyQt6.QtCore import Qt, QTimer

from src.serial_reader import SerialManager
from src.recorder import Recorder
from src.insight_engine import InsightEngine
from src.simulation_controller import SimulationController
from src.scenario import ScenarioController
from src.session_state import ActiveSession

from ui.sidebar import Sidebar
from ui.session_bar import SessionBar
from ui.overlay import OverlayMessage
from ui.pages.overview_page import OverviewPage
from ui.pages.diagnostics_page import DiagnosticsPage
from ui.pages.replay_page import ReplayPage
from ui.pages.compliance_page import CompliancePage
from ui.pages.tools_page import ToolsPage
from ui.pages.console_page import ConsolePage

logger = logging.getLogger(__name__)

_PAGE_KEYS = ["overview", "diagnostics", "replay", "compliance", "tools", "console"]
_PAGE_INDICES = {k: i for i, k in enumerate(_PAGE_KEYS)}


class AppShell(QMainWindow):
    """
    Single-window unified shell.

    Structure:
      SessionBar (top, fixed height)
      ├─ Sidebar (left, fixed width)
      └─ QStackedWidget (center, stretches to fill)
    """

    def __init__(self, demo_mode: bool = False, mock_mode: bool = False,
                 enable_3d: bool = True, windowed: bool = False,
                 live_port: str = "", parent=None):
        super().__init__(parent)
        self.setWindowTitle("VSM Evidence Workbench")
        self.resize(1440, 900)

        self._demo_mode = demo_mode
        self._mock_mode = mock_mode
        self._enable_3d = enable_3d
        self._windowed = windowed
        # Serial port for live hardware mode (empty = not configured)
        self._live_port = live_port

        # The currently active analysis session (imported file or loaded capsule)
        self._current_session: ActiveSession | None = None

        self._init_backends()
        self._build_ui()
        self._wire_signals()

        # Accept file drops anywhere on the window
        self.setAcceptDrops(True)

        if demo_mode:
            QTimer.singleShot(200, self._start_demo)

    # ──────────────────────────────────────────────────────────────
    # Backend initialisation
    # ──────────────────────────────────────────────────────────────

    def _init_backends(self):
        os.makedirs("data/sessions", exist_ok=True)
        os.makedirs("exports", exist_ok=True)

        self.serial_mgr = SerialManager()
        self.recorder = Recorder(data_dir="data/sessions")
        self.insight_engine = InsightEngine()
        self.sim_ctrl = SimulationController()
        self.scenario_ctrl = ScenarioController()

        # Auto-save frames to recorder when recording
        self.serial_mgr.frame_received.connect(self._on_frame)

    def _on_frame(self, frame: dict):
        if self.recorder.is_recording:
            self.recorder.log_frame(frame)
        self.insight_engine.update(frame)

    # ──────────────────────────────────────────────────────────────
    # UI construction
    # ──────────────────────────────────────────────────────────────

    def _build_ui(self):
        # Root widget
        root = QWidget()
        self.setCentralWidget(root)
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # Session bar at top
        self.session_bar = SessionBar()
        root_layout.addWidget(self.session_bar)

        # Horizontal split: sidebar + content
        body = QWidget()
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)

        self.sidebar = Sidebar()
        body_layout.addWidget(self.sidebar)

        # Thin separator line
        sep = QWidget()
        sep.setFixedWidth(1)
        sep.setObjectName("ShellSeparator")
        body_layout.addWidget(sep)

        self.stack = QStackedWidget()
        body_layout.addWidget(self.stack, stretch=1)

        root_layout.addWidget(body, stretch=1)

        # Toast overlay — parented to root widget so it floats above everything
        self._toast = OverlayMessage(root)

        # Build pages in order matching _PAGE_KEYS
        self._overview = OverviewPage()
        self._diagnostics = DiagnosticsPage(
            self.serial_mgr, self.scenario_ctrl, self.insight_engine,
            enable_3d=self._enable_3d
        )
        self._replay = ReplayPage(self.recorder, self.serial_mgr)
        self._compliance = CompliancePage(self.scenario_ctrl)
        self._tools = ToolsPage()
        self._console = ConsolePage(self.serial_mgr, self.insight_engine)

        for page in [self._overview, self._diagnostics, self._replay,
                     self._compliance, self._tools, self._console]:
            self.stack.addWidget(page)

        # Default page
        self.sidebar.select("overview")
        self.stack.setCurrentIndex(0)

    def _wire_signals(self):
        # Sidebar navigation
        self.sidebar.page_changed.connect(self._navigate)

        # Session bar simulation controls
        self.session_bar.run_clicked.connect(self._on_run)
        self.session_bar.pause_clicked.connect(self._on_pause)
        self.session_bar.stop_clicked.connect(self._on_stop)

        # SimulationController state → session bar + console REC timer
        self.sim_ctrl.state_changed.connect(self.session_bar.update_sim_state)
        self.sim_ctrl.state_changed.connect(self._console.on_sim_state)

        # Overview actions
        self._overview.import_run_requested.connect(self._open_import_dialog)
        self._overview.replace_file_requested.connect(self._open_import_dialog)
        self._overview.clear_session_requested.connect(self._clear_active_session)
        self._overview.start_demo_requested.connect(self._start_demo)
        self._overview.load_session_requested.connect(self._load_session_into_replay)
        self._overview.navigate_to.connect(self._navigate)

        # Connection status → overview health indicator
        self.serial_mgr.connection_status.connect(self._on_connection_status)

        # Tools page
        self._tools.reset_requested.connect(self._clear_active_session)

        # Replay empty-state navigation
        self._replay.navigate_to.connect(self._navigate)

        # Forward detected events to compliance page for full report context
        self._replay.studio.events_detected.connect(self._on_events_detected)

    # ──────────────────────────────────────────────────────────────
    # File import workflow
    # ──────────────────────────────────────────────────────────────

    _SUPPORTED_EXTS = frozenset({".csv", ".xls", ".xlsx", ".json"})

    def _open_import_dialog(self, preload_path: str = "") -> None:
        """Open the Import Run File dialog and wire the result into ReplayStudio.

        If *preload_path* is provided (e.g. from drag-and-drop), ingestion
        starts automatically so the dialog opens with the file already loading.
        """
        from ui.import_dialog import ImportDialog
        dlg = ImportDialog(self)
        dlg.session_imported.connect(self._on_session_imported)
        if preload_path:
            dlg.load_file(preload_path)
        dlg.exec()

    # ──────────────────────────────────────────────────────────────
    # Drag-and-drop
    # ──────────────────────────────────────────────────────────────

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            # Accept all file drags so unsupported drops receive a clear
            # in-app explanation instead of being ignored by Qt.
            event.acceptProposedAction()
            return
        event.ignore()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if not path:
                continue
            ext = os.path.splitext(path)[1].lower()
            if ext in self._SUPPORTED_EXTS:
                self._open_import_dialog(preload_path=path)
                return
            # Unsupported file — explain clearly instead of failing silently
            ext_display = ext if ext else "(no extension)"
            QMessageBox.warning(
                self,
                "Unsupported File Type",
                f"<b>{os.path.basename(path)}</b> ({ext_display}) cannot be analyzed.\n\n"
                "Supported data files:\n"
                "  • <b>CSV</b>  — oscilloscope captures (Rigol DS0/DS1), "
                "simulation logs, or recorded measurement exports\n"
                "  • <b>XLSX / XLS</b>  — simulation output (Excel)\n"
                "  • <b>JSON</b>  — saved Data Capsule sessions\n\n"
                "Firmware, docs, and scripts don't contain waveform data "
                "and are not imported here.",
            )
            return
        event.ignore()

    def _on_session_imported(self, capsule: dict):
        """Receive an imported session capsule and make it the active session."""
        label = capsule.get("meta", {}).get("session_id", "import")
        try:
            session = ActiveSession.from_capsule(capsule, label=label)

            self._set_active_session(session)
            self._navigate("overview")
            t0 = time.perf_counter()
            logger.info("app_shell.load.start: %s", label)
            self._replay.load_imported_session(capsule, session)
            self._compliance.load_from_capsule(capsule, session)
            self.session_bar.set_analysis_mode(True)
            logger.info("app_shell.load.end: %s (%.3fs)", label, time.perf_counter() - t0)

            source = session.source_type_display
            self.session_bar.set_source(f"Offline Analysis Mode - {source}")
            self._show_toast(f"Imported: {label}", "#10b981")
            logger.info("Imported session '%s' loaded (%s).", label, source)
        except Exception as exc:
            logger.exception("Failed to load imported session '%s'", label)
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(
                self, "Load Error",
                f"Failed to load session '{label}':\n{exc}\n\nCheck the log for details."
            )

    # ──────────────────────────────────────────────────────────────
    # Active session management
    # ──────────────────────────────────────────────────────────────

    def _set_active_session(self, session: ActiveSession) -> None:
        """Store the active session and broadcast to all interested pages."""
        self._current_session = session
        self._overview.set_active_session(session)
        self.session_bar.set_source(session.source_type_display)
        self._diagnostics.phasor.reset()

    def _clear_active_session(self) -> None:
        """Clear the active session and reset related UI state."""
        self._current_session = None
        self._overview.clear_active_session()
        self.session_bar.set_source("—")
        self.session_bar.set_analysis_mode(False)
        logger.info("Active session cleared.")

    # ──────────────────────────────────────────────────────────────
    # Navigation
    # ──────────────────────────────────────────────────────────────

    def _navigate(self, key: str):
        idx = _PAGE_INDICES.get(key, 0)
        self.stack.setCurrentIndex(idx)
        self.sidebar.select(key)

        # When entering Replay, prefer the in-memory active session created by import.
        if key == "replay":
            if self._current_session is not None:
                primary_capsule = self._replay.studio.get_primary_capsule()
                active_sid = self._current_session.capsule.get("meta", {}).get("session_id", "<unknown>")
                replay_sid = (
                    primary_capsule.get("meta", {}).get("session_id", "<none>")
                    if primary_capsule is not None
                    else "<none>"
                )
                needs_reload = primary_capsule is not self._current_session.capsule
                if needs_reload:
                    logger.debug(
                        "Replay navigation: loading active session into replay (active=%s replay=%s)",
                        active_sid,
                        replay_sid,
                    )
                    self._replay.load_imported_session(
                        self._current_session.capsule,
                        self._current_session,
                    )
                else:
                    logger.debug("Replay navigation: active session already loaded (%s)", active_sid)
            elif not self._replay.studio.sessions:
                self._replay.try_autoload_last_session()

        # Refresh overview when returning to it
        if key == "overview":
            self._overview.refresh()

    # ──────────────────────────────────────────────────────────────
    # Simulation controls
    # ──────────────────────────────────────────────────────────────

    def _on_run(self):
        if self.sim_ctrl.start():
            use_mock = self._mock_mode or self._demo_mode
            if use_mock:
                mode_label = "DEMO"
                source_label = "MOCK"
                self.serial_mgr.start_mock_mode()
            elif self._live_port:
                mode_label = "LIVE"
                source_label = self._live_port
                self.serial_mgr.connect_serial(self._live_port)
            else:
                # No explicit port — warn and fall back to demo
                logger.warning(
                    "_on_run: no live_port configured; falling back to DEMO mode. "
                    "Pass --port <COMx> to use real hardware."
                )
                mode_label = "DEMO"
                source_label = "MOCK (no port)"
                self.serial_mgr.start_mock_mode()

            self.session_bar.set_mode(mode_label)
            self.session_bar.set_source(f"Input: {source_label}")
            self.recorder.start()
            self.session_bar.set_recording(True)
            self._show_toast(f"Recording started — {mode_label}", "#10b981")
            logger.info("Simulation started (%s)", mode_label)

    def _on_pause(self):
        self.sim_ctrl.pause()
        self.serial_mgr.stop()
        self.session_bar.set_recording(False)

    def _on_stop(self):
        self.sim_ctrl.stop()
        self.serial_mgr.stop()
        self.session_bar.set_recording(False)

        # Capture in-memory capsule BEFORE recorder.stop() clears its buffer.
        live_capsule = self.recorder.to_capsule()

        saved = self.recorder.stop()
        if saved:
            name = os.path.basename(saved)
            logger.info("Session saved: %s", saved)
            self.session_bar.set_source(f"Saved: {name}")

        # Auto-bridge: load the recorded session into the unified analysis
        # pipeline (same flow as an imported file) if there are enough frames.
        frames = live_capsule.get("frames", [])
        if len(frames) >= 10:
            session = ActiveSession.from_capsule(live_capsule)
            self._set_active_session(session)
            self._replay.load_imported_session(live_capsule, session)
            self._compliance.load_from_capsule(live_capsule, session)
            self.session_bar.set_analysis_mode(True)
            self.session_bar.set_source("Analysis: Recorded session")
            self._show_toast(
                f"Session recorded ({len(frames)} frames) — loaded for analysis",
                "#10b981",
            )
            logger.info("Live session (%d frames) auto-loaded for analysis.", len(frames))
        else:
            if saved:
                self._show_toast(f"Session saved  —  {os.path.basename(saved)}", "#10b981")

        self._overview.refresh()

    def _show_toast(self, text: str, color: str = "#10b981"):
        """Show a transient toast notification anchored bottom-right of the session bar."""
        bar = self.session_bar
        x = bar.width() - 380
        y = bar.height() + 8
        self._toast.show_message(text, color=color, pos=(max(x, 8), y))

    # ──────────────────────────────────────────────────────────────
    # Demo mode
    # ──────────────────────────────────────────────────────────────

    def _start_demo(self):
        """Navigate to the Console and start mock telemetry."""
        self._mock_mode = True
        self.session_bar.set_mode("DEMO")
        self.session_bar.set_source("MOCK")
        self._navigate("console")
        if not self.sim_ctrl.is_running():
            self._on_run()
        if not self._windowed:
            self.showFullScreen()

    # ──────────────────────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────────────────────

    def _load_session_into_replay(self, path: str):
        self._replay.load_session(path)
        self._compliance.load_session(path)
        self._console.load_session(path)

    def _on_events_detected(self, _n: int) -> None:
        """
        After event detection runs, forward events to the compliance page so
        it has full context when generating the engineering report.
        """
        events      = self._replay.studio.get_events()
        annotations = self._replay.studio.get_annotations()
        self._compliance.set_events(events, annotations)

    def _on_connection_status(self, connected: bool, source: str):
        self._overview.set_health(connected, "MOCK" if "MOCK" in source else source)

    def closeEvent(self, event):
        self.serial_mgr.stop()
        self.recorder.stop()
        super().closeEvent(event)
