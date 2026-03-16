import os
import json
import logging
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
                             QPushButton, QLabel, QFrame, QListWidget, QListWidgetItem)
from PyQt6.QtCore import pyqtSignal, Qt

logger = logging.getLogger(__name__)

_SESSIONS_DIRS = ["data/sessions", "data/demo_sessions"]


class OverviewPage(QWidget):
    """
    Landing screen — makes the demo path immediately obvious.

    Signals:
      start_demo_requested  — user clicked Start Demo Session
      load_session_requested(path) — user picked a session file
      navigate_to(page_key) — navigate to another page
    """

    start_demo_requested = pyqtSignal()
    load_session_requested = pyqtSignal(str)
    navigate_to = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(32, 32, 32, 32)
        root.setSpacing(24)

        # ── Title ──
        title = QLabel("RedByte GFM HIL Suite")
        title.setObjectName("OverviewTitle")
        root.addWidget(title)

        subtitle = QLabel("Grid-Forming Inverter  ·  Hardware-in-the-Loop Diagnostics & Validation")
        subtitle.setObjectName("OverviewSubtitle")
        root.addWidget(subtitle)

        # ── System Health ──
        self._health = _HealthRow()
        root.addWidget(self._health)

        # ── Action Cards ──
        cards_row = QWidget()
        cards_layout = QHBoxLayout(cards_row)
        cards_layout.setContentsMargins(0, 0, 0, 0)
        cards_layout.setSpacing(16)

        cards = [
            ("⚡", "Start Demo Session",
             "Launch live diagnostics with mock telemetry",
             "diagnostics", True),
            ("📂", "Load Session",
             "Open a saved session for replay or compliance",
             "replay", False),
            ("⏵", "Open Replay",
             "Browse timeline, metrics, and spectrum",
             "replay", False),
            ("✓", "Run Compliance",
             "Validate a session against IEEE 2800 checks",
             "compliance", False),
        ]

        for icon, label, desc, nav_key, is_primary in cards:
            card = _ActionCard(icon, label, desc, is_primary)
            if label == "Start Demo Session":
                card.clicked.connect(self.start_demo_requested)
            elif label == "Load Session":
                card.clicked.connect(lambda _, k="replay": self.navigate_to.emit(k))
            else:
                card.clicked.connect(lambda _, k=nav_key: self.navigate_to.emit(k))
            cards_layout.addWidget(card)

        root.addWidget(cards_row)

        # ── Recent Sessions ──
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
        """Populate recent sessions list from known session directories."""
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

    def set_health(self, connected: bool, mode: str):
        self._health.update(connected, mode)

    def refresh(self):
        self._refresh_sessions()


class _ActionCard(QFrame):
    clicked = pyqtSignal()

    def __init__(self, icon: str, label: str, desc: str, primary: bool = False, parent=None):
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
            self._lbl.setText(f"Telemetry: Connected  ·  Mode: {mode}")
        else:
            self._dot.setStyleSheet("color: #64748b;")
            self._lbl.setText(f"Telemetry: Not connected  ·  Mode: {mode}")
