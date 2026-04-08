"""
Event Lane widget for RedByte GFM HIL Suite.

Shows detected events from an ImportedDataset as a color-coded list
with a summary bar, engineering statistics cards, and inline user annotations.
Emits ``event_selected(ts_start)`` when the user clicks a row so the caller
can seek the replay scrubber.

Usage::

    lane = EventLane()
    lane.load_events(events)          # list[DetectedEvent]
    lane.event_selected.connect(scrubber.setValue)
"""

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QBrush, QColor
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QSizePolicy,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.event_detector import DetectedEvent

# Severity colour palette (background, text)
_SEV_COLORS: dict[str, tuple[str, str]] = {
    "critical": ("#7f1d1d", "#fca5a5"),
    "warning":  ("#78350f", "#fcd34d"),
    "info":     ("#1e3a5f", "#93c5fd"),
}
_SEV_BADGE_BG: dict[str, str] = {
    "critical": "#ef4444",
    "warning":  "#f59e0b",
    "info":     "#3b82f6",
}

# Friendly display names for event kinds
_KIND_LABELS: dict[str, str] = {
    "voltage_sag":      "Voltage Sag",
    "voltage_swell":    "Voltage Swell",
    "freq_excursion":   "Freq Excursion",
    "flatline":         "Flatline",
    "step_change":      "Step Change",
    "clipping":         "Clipping",
    "duplicate_channel": "Duplicate Ch.",
    "thd_spike":        "THD Spike",
}

# Stats card labels and their metric extraction keys
_STAT_CARD_DEFS: list[tuple[str, str]] = [
    ("Worst Sag",    "sag_depth_pct"),
    ("Worst Swell",  "swell_depth_pct"),
    ("Max Freq Dev", "freq_dev_hz"),
    ("Max THD",      "thd_pct"),
    ("Max Flatline", "flatline_s"),
    ("Confidence",   "confidence"),
]


def _compute_stats(events: list[DetectedEvent]) -> dict[str, str]:
    """Derive summary statistics from the event list for the stats cards."""
    sag_depths: list[float] = []
    swell_depths: list[float] = []
    freq_devs: list[float] = []
    thd_pcts: list[float] = []
    flatline_durs: list[float] = []
    confidences: list[float] = [e.confidence for e in events]

    for e in events:
        if e.kind == "voltage_sag":
            sag_depths.append(e.metrics.get("depth_pct", 0.0))
        elif e.kind == "voltage_swell":
            swell_depths.append(e.metrics.get("depth_pct", 0.0))
        elif e.kind == "freq_excursion":
            freq_devs.append(e.metrics.get("deviation_hz", 0.0))
        elif e.kind == "thd_spike":
            thd_pcts.append(e.metrics.get("thd_pct", 0.0))
        elif e.kind == "flatline":
            flatline_durs.append(e.metrics.get("duration_s", 0.0))

    def _fmt_pct(vals: list[float]) -> str:
        return f"{max(vals):.1f}%" if vals else "--"

    def _fmt_hz(vals: list[float]) -> str:
        return f"{max(vals):.3f} Hz" if vals else "--"

    def _fmt_s(vals: list[float]) -> str:
        return f"{max(vals):.3f} s" if vals else "--"

    def _fmt_conf(vals: list[float]) -> str:
        if not vals:
            return "--"
        lo, hi = min(vals), max(vals)
        if lo == hi:
            return f"{lo:.0%}"
        return f"{lo:.0%}–{hi:.0%}"

    return {
        "sag_depth_pct":  _fmt_pct(sag_depths),
        "swell_depth_pct": _fmt_pct(swell_depths),
        "freq_dev_hz":    _fmt_hz(freq_devs),
        "thd_pct":        _fmt_pct(thd_pcts),
        "flatline_s":     _fmt_s(flatline_durs),
        "confidence":     _fmt_conf(confidences),
    }


class EventLane(QWidget):
    """
    Lists detected events from a session with severity badges,
    engineering summary cards, and inline user annotations.

    Signals
    -------
    event_selected : float
        Emitted with ``ts_start`` when the user clicks a row.
    """

    event_selected = pyqtSignal(float)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._events: list[DetectedEvent] = []
        # annotations keyed by ts_start (float rounded to µs)
        self._annotations: dict[str, str] = {}
        self._build()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_events(self, events: list[DetectedEvent]) -> None:
        """Replace the current event list with *events* and refresh the view."""
        self._events = list(events)
        # Populate kind combo with unique event types
        self._kind_combo.blockSignals(True)
        self._kind_combo.clear()
        self._kind_combo.addItem("All Types")
        kinds = sorted({e.kind for e in events})
        for k in kinds:
            self._kind_combo.addItem(_KIND_LABELS.get(k, k))
        self._kind_combo.blockSignals(False)
        self._refresh()

    def clear(self) -> None:
        """Clear all events and reset the summary bar."""
        self._events = []
        self._refresh()

    def get_events(self) -> list:
        """Return the current list of DetectedEvent objects (read-only copy)."""
        return list(self._events)

    def get_annotations(self) -> dict:
        """Return the current annotations dict keyed by ts_start string."""
        return dict(self._annotations)

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        # ── Summary bar ──────────────────────────────────────────────
        self._summary_bar = QHBoxLayout()
        self._summary_bar.setSpacing(8)

        self._lbl_total = QLabel("No events detected")
        self._lbl_total.setStyleSheet("color: #94a3b8; font-size: 11px;")

        self._badge_critical = self._make_badge("critical")
        self._badge_warning  = self._make_badge("warning")
        self._badge_info     = self._make_badge("info")

        for w in [self._lbl_total,
                  self._badge_critical, self._badge_warning, self._badge_info]:
            self._summary_bar.addWidget(w)
        self._summary_bar.addStretch()
        root.addLayout(self._summary_bar)

        # ── Filter bar ────────────────────────────────────────────────
        filter_row = QHBoxLayout()
        filter_row.setSpacing(8)

        filter_label = QLabel("Filter:")
        filter_label.setStyleSheet("color: #64748b; font-size: 10px;")
        filter_row.addWidget(filter_label)

        self._sev_combo = QComboBox()
        self._sev_combo.addItems(["All Severities", "Critical", "Warning", "Info"])
        self._sev_combo.setFixedWidth(130)
        self._sev_combo.currentIndexChanged.connect(lambda _: self._refresh())
        filter_row.addWidget(self._sev_combo)

        self._kind_combo = QComboBox()
        self._kind_combo.addItem("All Types")
        self._kind_combo.setFixedWidth(150)
        self._kind_combo.currentIndexChanged.connect(lambda _: self._refresh())
        filter_row.addWidget(self._kind_combo)

        self._chk_hide_info = QCheckBox("Hide info-level")
        self._chk_hide_info.setStyleSheet("color: #94a3b8; font-size: 10px;")
        self._chk_hide_info.toggled.connect(lambda _: self._refresh())
        filter_row.addWidget(self._chk_hide_info)

        filter_row.addStretch()

        self._lbl_showing = QLabel("")
        self._lbl_showing.setStyleSheet("color: #475569; font-size: 10px;")
        filter_row.addWidget(self._lbl_showing)

        root.addLayout(filter_row)

        # ── Engineering stats cards ───────────────────────────────────
        self._stats_frame = QFrame()
        self._stats_frame.setStyleSheet(
            "QFrame { background: #0d1117; border: 1px solid #1e293b; border-radius: 4px; }"
        )
        stats_grid = QGridLayout(self._stats_frame)
        stats_grid.setContentsMargins(8, 6, 8, 6)
        stats_grid.setHorizontalSpacing(16)
        stats_grid.setVerticalSpacing(4)

        # Build label pairs: (title_label, value_label) for each stat card
        self._stat_labels: dict[str, QLabel] = {}
        for idx, (caption, key) in enumerate(_STAT_CARD_DEFS):
            row, col = divmod(idx, 3)
            col *= 2  # pairs occupy 2 grid columns each

            title_lbl = QLabel(caption)
            title_lbl.setStyleSheet("color: #64748b; font-size: 9px;")

            val_lbl = QLabel("--")
            val_lbl.setStyleSheet(
                "color: #e2e8f0; font-size: 11px; font-weight: 600;"
            )
            self._stat_labels[key] = val_lbl

            stats_grid.addWidget(title_lbl, row * 2,     col)
            stats_grid.addWidget(val_lbl,   row * 2 + 1, col)

        self._stats_frame.setVisible(False)
        root.addWidget(self._stats_frame)

        # ── Separator ────────────────────────────────────────────────
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #1e293b;")
        root.addWidget(sep)

        # ── Event table ──────────────────────────────────────────────
        self._tree = QTreeWidget()
        self._tree.setColumnCount(6)
        self._tree.setHeaderLabels(
            ["Time (s)", "Duration", "Kind", "Channel", "Description", "Note"]
        )
        self._tree.setRootIsDecorated(False)
        self._tree.setAlternatingRowColors(True)
        self._tree.setSortingEnabled(True)
        self._tree.setStyleSheet("""
            QTreeWidget {
                background: #0b0f14;
                alternate-background-color: #111827;
                color: #e2e8f0;
                border: 1px solid #1e293b;
                font-size: 10px;
            }
            QHeaderView::section {
                background: #1e293b;
                color: #94a3b8;
                font-size: 10px;
                border: none;
                padding: 4px;
            }
            QTreeWidget::item:selected {
                background: #1e3a5f;
            }
        """)
        self._tree.header().setDefaultSectionSize(100)
        self._tree.header().resizeSection(4, 260)  # Description wider
        self._tree.header().resizeSection(5, 140)  # Note column
        self._tree.itemClicked.connect(self._on_item_clicked)
        self._tree.itemDoubleClicked.connect(self._on_item_double_clicked)
        self._tree.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        root.addWidget(self._tree, stretch=1)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _make_badge(severity: str) -> QLabel:
        badge = QLabel("0")
        bg = _SEV_BADGE_BG.get(severity, "#64748b")
        badge.setStyleSheet(
            f"background: {bg}; color: #fff; border-radius: 8px; "
            f"padding: 1px 7px; font-size: 10px; font-weight: 700;"
        )
        badge.setFixedHeight(18)
        return badge

    @staticmethod
    def _annotation_key(ts_start: float) -> str:
        return f"{ts_start:.6f}"

    def _refresh(self) -> None:
        self._tree.clear()

        # ── Apply filters ────────────────────────────────────────────
        sev_filter = self._sev_combo.currentText().lower()
        kind_filter_text = self._kind_combo.currentText()
        hide_info = self._chk_hide_info.isChecked()

        # Reverse-lookup kind key from label
        kind_key_filter = None
        if kind_filter_text != "All Types":
            for k, v in _KIND_LABELS.items():
                if v == kind_filter_text:
                    kind_key_filter = k
                    break
            if kind_key_filter is None:
                kind_key_filter = kind_filter_text  # raw kind name

        filtered: list[DetectedEvent] = []
        for e in self._events:
            if hide_info and e.severity == "info":
                continue
            if sev_filter not in ("all severities",) and e.severity != sev_filter and sev_filter != "all severities":
                continue
            if kind_key_filter and e.kind != kind_key_filter:
                continue
            filtered.append(e)

        # ── Unfiltered totals for badges ─────────────────────────────
        n_critical = sum(1 for e in self._events if e.severity == "critical")
        n_warning  = sum(1 for e in self._events if e.severity == "warning")
        n_info     = sum(1 for e in self._events if e.severity == "info")
        n_total    = len(self._events)

        if n_total == 0:
            self._lbl_total.setText("No events detected")
        else:
            self._lbl_total.setText(f"{n_total} event{'s' if n_total != 1 else ''} detected")

        self._badge_critical.setText(str(n_critical))
        self._badge_warning.setText(str(n_warning))
        self._badge_info.setText(str(n_info))

        # Stats cards
        if n_total > 0:
            stats = _compute_stats(filtered if filtered else self._events)
            for key, val_lbl in self._stat_labels.items():
                val_lbl.setText(stats.get(key, "--"))
            self._stats_frame.setVisible(True)
        else:
            self._stats_frame.setVisible(False)

        bg_crit, fg_crit = _SEV_COLORS["critical"]
        bg_warn, fg_warn = _SEV_COLORS["warning"]
        bg_info, fg_info = _SEV_COLORS["info"]

        # Show filter status
        if len(filtered) != n_total:
            self._lbl_showing.setText(f"Showing {len(filtered)} of {n_total}")
        else:
            self._lbl_showing.setText("")

        for event in filtered:
            dur  = event.ts_end - event.ts_start
            kind = _KIND_LABELS.get(event.kind, event.kind)
            note = self._annotations.get(self._annotation_key(event.ts_start), "")

            item = QTreeWidgetItem([
                f"{event.ts_start:.4f}",
                f"{dur:.3f}s",
                kind,
                event.channel,
                event.description,
                note,
            ])
            item.setData(0, Qt.ItemDataRole.UserRole, event.ts_start)
            item.setToolTip(5, "Double-click to add/edit annotation")

            # Severity colouring
            sev = event.severity
            if sev == "critical":
                bg_hex, fg_hex = bg_crit, fg_crit
            elif sev == "warning":
                bg_hex, fg_hex = bg_warn, fg_warn
            else:
                bg_hex, fg_hex = bg_info, fg_info

            bg_col = QColor(bg_hex)
            fg_col = QColor(fg_hex)
            for col in range(5):  # columns 0–4 get severity colour; Note stays neutral
                item.setBackground(col, QBrush(bg_col))
                item.setForeground(col, QBrush(fg_col))

            self._tree.addTopLevelItem(item)

        self._tree.resizeColumnToContents(0)
        self._tree.resizeColumnToContents(1)
        self._tree.resizeColumnToContents(2)
        self._tree.resizeColumnToContents(3)

    def _on_item_clicked(self, item: QTreeWidgetItem, _column: int) -> None:
        ts = item.data(0, Qt.ItemDataRole.UserRole)
        if ts is not None:
            self.event_selected.emit(float(ts))

    def _on_item_double_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        """Open an inline text prompt to annotate the event row."""
        ts = item.data(0, Qt.ItemDataRole.UserRole)
        if ts is None:
            return
        key = self._annotation_key(float(ts))
        current = self._annotations.get(key, "")
        text, ok = QInputDialog.getText(
            self,
            "Annotate Event",
            f"Note for event at t={float(ts):.4f}s:",
            text=current,
        )
        if ok:
            if text.strip():
                self._annotations[key] = text.strip()
            else:
                self._annotations.pop(key, None)
            # Update just the Note column of the item rather than full refresh
            item.setText(5, self._annotations.get(key, ""))
