import os
import logging
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout,
                             QPushButton, QLabel, QFrame,
                             QListWidget, QListWidgetItem)
from PyQt6.QtCore import pyqtSignal, Qt

from src.session_state import ActiveSession
from ui.dataset_info_panel import DatasetInfoPanel

logger = logging.getLogger(__name__)

_SESSIONS_DIRS = ["data/sessions", "data/demo_sessions"]


class OverviewPage(QWidget):
    """
    Landing screen.

    Primary workflow: Import a real run file — leads directly to analysis.
    Secondary workflow: Start demo session (explicitly labelled [Demo]).

    When an ActiveSession is present (set via set_active_session()), the panel
    shows file metadata and channels prominently, and the "Open in Replay"
    action becomes primary.

    Signals:
      import_run_requested        — user clicked Import Run File
      start_demo_requested        — user clicked Start Demo Session [Demo]
      load_session_requested(path)— user double-clicked a session file
      navigate_to(page_key)       — navigate to another page
      replace_file_requested      — user clicked Replace on the info panel
      clear_session_requested     — user clicked Clear on the info panel
    """

    import_run_requested   = pyqtSignal()
    start_demo_requested   = pyqtSignal()
    load_session_requested = pyqtSignal(str)
    navigate_to            = pyqtSignal(str)
    replace_file_requested = pyqtSignal()
    clear_session_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_active_session(self, session: ActiveSession) -> None:
        """Show the dataset info panel with metadata for the given session."""
        self._info_panel.load_session(session)
        self._info_panel.show()
        self._no_session_hint.hide()

    def clear_active_session(self) -> None:
        """Hide the dataset info panel (no session loaded)."""
        self._info_panel.clear()
        self._no_session_hint.show()

    def set_health(self, connected: bool, mode: str):
        self._health.update(connected, mode)

    def refresh(self):
        self._refresh_sessions()

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(32, 32, 32, 32)
        root.setSpacing(20)

        # ── Title ──────────────────────────────────────────────────────
        title = QLabel("RedByte GFM HIL Suite")
        title.setObjectName("OverviewTitle")
        root.addWidget(title)

        subtitle = QLabel(
            "Grid-Forming Inverter  ·  Engineering Analysis for Power Quality & Inverter Behavior"
        )
        subtitle.setObjectName("OverviewSubtitle")
        root.addWidget(subtitle)

        # ── Live connection indicator (hidden unless actively connected) ──
        self._health = _HealthRow()
        self._health.hide()   # Only shown when live telemetry is active
        root.addWidget(self._health)

        # ── Active session panel (hidden until a session is loaded) ────
        self._info_panel = DatasetInfoPanel()
        self._info_panel.replace_requested.connect(self.replace_file_requested)
        self._info_panel.clear_requested.connect(self.clear_session_requested)
        self._info_panel.open_replay_requested.connect(
            lambda: self.navigate_to.emit("replay")
        )
        self._info_panel.hide()
        root.addWidget(self._info_panel)

        # Hint shown when no session is active
        self._no_session_hint = QLabel(
            "No dataset loaded  —  import a run file (CSV, Excel, or JSON) to begin analysis"
        )
        self._no_session_hint.setObjectName("NoSessionHint")
        self._no_session_hint.setStyleSheet(
            "color:#475569; font-size:13px; padding:4px 0;"
        )
        root.addWidget(self._no_session_hint)

        # ── Action Cards ──────────────────────────────────────────────
        cards_row = QWidget()
        cards_layout = QHBoxLayout(cards_row)
        cards_layout.setContentsMargins(0, 0, 0, 0)
        cards_layout.setSpacing(16)

        # Import is always primary — it's the entry point to real work
        cards_data = [
            ("📂", "Import Run File",
             "Load a CSV, Excel, or JSON file and start analysis",
             None, True),
            ("⏵", "Open Replay",
             "Browse timeline, metrics, and spectrum of loaded sessions",
             "replay", False),
            ("✓", "Run Compliance",
             "Validate a session against IEEE 2800 checks",
             "compliance", False),
            ("⚡", "Start Demo Session",
             "[Demo] Launch diagnostics with simulated telemetry",
             "diagnostics", False),
        ]

        for icon, label, desc, nav_key, is_primary in cards_data:
            card = _ActionCard(icon, label, desc, is_primary)
            if label == "Import Run File":
                card.clicked.connect(self.import_run_requested)
            elif label == "Start Demo Session":
                card.clicked.connect(self.start_demo_requested)
            else:
                card.clicked.connect(lambda _, k=nav_key: self.navigate_to.emit(k))
            cards_layout.addWidget(card)

        root.addWidget(cards_row)

        # ── Recent Sessions ───────────────────────────────────────────
        recent_label = QLabel("Recent Sessions")
        recent_label.setObjectName("SectionLabel")
        root.addWidget(recent_label)

        self._session_list = QListWidget()
        self._session_list.setObjectName("RecentSessionList")
        self._session_list.setMaximumHeight(200)
        self._session_list.itemDoubleClicked.connect(self._on_session_double_click)
        root.addWidget(self._session_list)

        root.addStretch()

        self._refresh_sessions()

    def _refresh_sessions(self):
        self._session_list.clear()
        files = []
        for d in _SESSIONS_DIRS:
            if os.path.isdir(d):
                for f in os.listdir(d):
                    if f.endswith(".json"):
                        full = os.path.join(d, f)
                        files.append((os.path.getmtime(full), full, f))
        files.sort(reverse=True)
        for _, full_path, fname in files[:10]:
            item = QListWidgetItem(f"  {fname}")
            item.setData(Qt.ItemDataRole.UserRole, full_path)
            self._session_list.addItem(item)

        if not files:
            self._session_list.addItem("  No sessions found in data/sessions/")

    def _on_session_double_click(self, item):
        path = item.data(Qt.ItemDataRole.UserRole)
        if path:
            self.load_session_requested.emit(path)
            self.navigate_to.emit("replay")


class _ActionCard(QFrame):
    clicked = pyqtSignal()

    def __init__(self, icon: str, label: str, desc: str,
                 primary: bool = False, parent=None):
        super().__init__(parent)
        self.setObjectName("ActionCardPrimary" if primary else "ActionCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumWidth(180)
        self.setMinimumHeight(130)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(8)

        ico = QLabel(icon)
        ico.setObjectName("CardIcon")
        ico.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(ico)

        lbl = QLabel(label)
        lbl.setObjectName("CardLabel")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setWordWrap(True)
        layout.addWidget(lbl)

        d = QLabel(desc)
        d.setObjectName("CardDesc")
        d.setAlignment(Qt.AlignmentFlag.AlignCenter)
        d.setWordWrap(True)
        layout.addWidget(d)

    def mousePressEvent(self, event):
        self.clicked.emit()
        super().mousePressEvent(event)


class _HealthRow(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("HealthRow")
        self.setFixedHeight(36)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        self._dot = QLabel("●")
        self._dot.setObjectName("HealthDot")
        layout.addWidget(self._dot)

        self._lbl = QLabel("Telemetry: Not connected  ·  Mode: —")
        self._lbl.setObjectName("HealthLabel")
        layout.addWidget(self._lbl)
        layout.addStretch()

    def update(self, connected: bool, mode: str):
        if connected:
            self._dot.setStyleSheet("color: #10b981;")
            self._lbl.setText(f"Live: {mode}  (connected)")
            self.show()
        else:
            self.hide()
