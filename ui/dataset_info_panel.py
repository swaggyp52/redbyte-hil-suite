"""
DatasetInfoPanel — compact metadata display for an ActiveSession.

Used on the Overview page (when a session is active) and on the Replay page
header area so the user always knows what dataset is loaded.

Layout:
  ┌─────────────────────────────────────────────────────────────────┐
  │ [source type badge]  filename                        [Replace] [Clear] │
  │─────────────────────────────────────────────────────────────────│
  │  Duration: X.XXX s     Samples: X,XXX     Rate: X Hz           │
  │  Channels: X mapped  /  X unmapped                              │
  │  [!] warnings count  (click to expand warning list)            │
  └─────────────────────────────────────────────────────────────────┘
"""

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout,
    QWidget,
)

from src.session_state import ActiveSession


# Colour map for source-type badges
_SOURCE_COLORS: dict[str, str] = {
    "rigol_csv":         "#0ea5e9",   # sky blue
    "simulation_excel":  "#10b981",   # emerald
    "data_capsule_json": "#8b5cf6",   # violet
    "live":              "#f59e0b",   # amber
}
_DEFAULT_SOURCE_COLOR = "#64748b"    # slate


class DatasetInfoPanel(QFrame):
    """
    Compact single-session metadata display.

    Signals:
        replace_requested:  The user clicked "Replace File".
        clear_requested:    The user clicked "Clear Session".
    """

    replace_requested    = pyqtSignal()
    clear_requested      = pyqtSignal()
    open_replay_requested = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("DatasetInfoPanel")
        self.setFrameShape(QFrame.Shape.NoFrame)
        self._build()
        self._warnings: list[str] = []
        self._warnings_expanded = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_session(self, session: ActiveSession) -> None:
        """Populate the panel from an ActiveSession."""
        # Source badge
        color = _SOURCE_COLORS.get(session.source_type, _DEFAULT_SOURCE_COLOR)
        self._badge.setText(session.source_type_display)
        self._badge.setStyleSheet(
            f"background:{color}; color:#fff; border-radius:3px; "
            f"padding:1px 6px; font-size:11px; font-weight:600;"
        )

        # Filename
        self._filename.setText(session.source_filename)
        self._filename.setToolTip(session.source_path)

        # Metadata chips
        self._set_chip(self._dur_val, "Duration", session.duration_display)
        self._set_chip(self._samples_val, "Samples", session.row_count_display)
        self._set_chip(self._rate_val, "Sample rate", session.sample_rate_display)

        # Channel summary
        n_mapped   = len(session.mapped_channels)
        n_unmapped = len(session.unmapped_channels)
        ch_parts = [f"<b>{n_mapped}</b> mapped"]
        if n_unmapped:
            ch_parts.append(f"<b>{n_unmapped}</b> unmapped")

        # Dead channel highlight from session warnings
        dead_warnings = [w for w in session.warnings if "dead or constant" in w]
        if dead_warnings:
            dead_names = []
            for w in dead_warnings:
                parts = w.split("'")
                if len(parts) >= 2:
                    dead_names.append(parts[1])
            ch_parts.append(
                f"<span style='color:#f59e0b;'>&#x26A0; {len(dead_names)} dead: "
                + ", ".join(dead_names) + "</span>"
            )

        self._ch_label.setText("  /  ".join(ch_parts))

        if n_unmapped:
            tip = "Unmapped channels use original source names:\n" + "\n".join(
                f"  {ch}" for ch in session.unmapped_channels
            )
            self._ch_label.setToolTip(tip)
        else:
            self._ch_label.setToolTip("")

        # Warnings
        self._warnings = session.warnings
        self._refresh_warnings()

        self.show()

    def clear(self) -> None:
        """Hide the panel (no active session)."""
        self._warnings = []
        self.hide()

    # ------------------------------------------------------------------
    # Internal construction
    # ------------------------------------------------------------------

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 8, 12, 8)
        root.setSpacing(4)

        # ── Row 1: badge + filename + action buttons ───────────────────
        row1 = QHBoxLayout()
        row1.setSpacing(8)

        self._badge = QLabel()
        self._badge.setFixedHeight(20)
        self._badge.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
        )

        self._filename = QLabel()
        self._filename.setStyleSheet("font-weight:600; font-size:13px;")
        self._filename.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )

        btn_open = QPushButton("Open in Replay →")
        btn_open.setObjectName("PrimaryBtn")
        btn_open.setFixedHeight(24)
        btn_open.setFixedWidth(120)
        btn_open.clicked.connect(self.open_replay_requested)

        btn_replace = QPushButton("Replace")
        btn_replace.setObjectName("SecondaryBtn")
        btn_replace.setFixedHeight(24)
        btn_replace.setFixedWidth(72)
        btn_replace.clicked.connect(self.replace_requested)

        btn_clear = QPushButton("Clear")
        btn_clear.setObjectName("SecondaryBtn")
        btn_clear.setFixedHeight(24)
        btn_clear.setFixedWidth(52)
        btn_clear.clicked.connect(self.clear_requested)

        row1.addWidget(self._badge)
        row1.addWidget(self._filename, stretch=1)
        row1.addWidget(btn_open)
        row1.addWidget(btn_replace)
        row1.addWidget(btn_clear)

        # ── Row 2: metadata chips ──────────────────────────────────────
        row2 = QHBoxLayout()
        row2.setSpacing(20)

        self._dur_val     = self._chip("Duration",   "—")
        self._samples_val = self._chip("Samples",    "—")
        self._rate_val    = self._chip("Sample rate","—")

        for chip_row, chip_widget in [
            (row2, self._dur_val),
            (row2, self._samples_val),
            (row2, self._rate_val),
        ]:
            chip_row.addWidget(chip_widget)
        row2.addStretch()

        # ── Row 3: channel summary ─────────────────────────────────────
        row3 = QHBoxLayout()
        row3.setSpacing(8)

        ch_icon = QLabel("⊞")
        ch_icon.setStyleSheet("color:#94a3b8; font-size:12px;")
        self._ch_label = QLabel()
        self._ch_label.setStyleSheet("font-size:12px; color:#94a3b8;")

        row3.addWidget(ch_icon)
        row3.addWidget(self._ch_label)
        row3.addStretch()

        # ── Row 4: warnings (hidden when empty) ───────────────────────
        self._warn_row = QHBoxLayout()
        self._warn_row.setSpacing(6)

        self._warn_icon = QLabel()
        self._warn_icon.setStyleSheet("font-size:12px;")

        self._warn_label = QLabel()
        self._warn_label.setStyleSheet("font-size:12px; color:#f59e0b; cursor:pointer;")
        self._warn_label.mousePressEvent = self._toggle_warnings

        self._warn_row.addWidget(self._warn_icon)
        self._warn_row.addWidget(self._warn_label)
        self._warn_row.addStretch()

        self._warn_detail = QLabel()
        self._warn_detail.setObjectName("WarnDetail")
        self._warn_detail.setWordWrap(True)
        self._warn_detail.setStyleSheet(
            "font-size:11px; color:#94a3b8; padding-left:18px;"
        )
        self._warn_detail.hide()

        # ── Assemble ──────────────────────────────────────────────────
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color:#334155;")

        root.addLayout(row1)
        root.addWidget(sep)
        root.addLayout(row2)
        root.addLayout(row3)
        root.addLayout(self._warn_row)
        root.addWidget(self._warn_detail)

        self.setStyleSheet("""
            DatasetInfoPanel {
                background: #1e293b;
                border: 1px solid #334155;
                border-radius: 6px;
            }
            QPushButton#PrimaryBtn {
                background: #0ea5e9;
                color: #fff;
                border: none;
                border-radius: 4px;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton#PrimaryBtn:hover {
                background: #38bdf8;
            }
            QPushButton#SecondaryBtn {
                background: #334155;
                color: #cbd5e1;
                border: none;
                border-radius: 4px;
                font-size: 12px;
            }
            QPushButton#SecondaryBtn:hover {
                background: #475569;
            }
        """)

    def _chip(self, label: str, value: str) -> QLabel:
        """Return a small read-only label widget showing 'Label: value'."""
        w = QLabel(f"<span style='color:#64748b;'>{label}:</span> {value}")
        w.setStyleSheet("font-size:12px;")
        return w

    def _refresh_warnings(self) -> None:
        n = len(self._warnings)
        if n == 0:
            self._warn_icon.hide()
            self._warn_label.hide()
            self._warn_detail.hide()
            return

        self._warn_icon.setText("⚠")
        self._warn_icon.setStyleSheet("color:#f59e0b; font-size:13px;")
        self._warn_icon.show()
        self._warn_label.setText(
            f"{n} warning{'s' if n > 1 else ''} — click to expand"
            if not self._warnings_expanded
            else f"{n} warning{'s' if n > 1 else ''} — click to collapse"
        )
        self._warn_label.show()

        if self._warnings_expanded:
            self._warn_detail.setText(
                "\n".join(f"• {w}" for w in self._warnings)
            )
            self._warn_detail.show()
        else:
            self._warn_detail.hide()

    def _toggle_warnings(self, _event=None) -> None:
        self._warnings_expanded = not self._warnings_expanded
        self._refresh_warnings()

    # Override _chip inline update — store refs to update values later
    def _set_chip(self, chip_widget: QLabel, label: str, value: str) -> None:
        chip_widget.setText(
            f"<span style='color:#64748b;'>{label}:</span> {value}"
        )
