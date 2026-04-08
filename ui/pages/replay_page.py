import os
import json
import logging
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
                             QPushButton, QLabel, QFileDialog, QFrame,
                             QStackedWidget)
from PyQt6.QtCore import Qt, pyqtSignal

from src.session_state import ActiveSession
from ui.replay_studio import ReplayStudio
from ui.insights_panel import InsightsPanel

logger = logging.getLogger(__name__)


class ReplayPage(QWidget):
    """
    Replay surface — load a recorded session, scrub timeline, inspect metrics.

    States:
      empty   — no session loaded, shows inviting empty-state card
      loaded  — session loaded, shows summary bar + studio + insights
    """

    def __init__(self, recorder, serial_mgr, parent=None):
        super().__init__(parent)
        self._session_path = None
        self._capsule: dict | None = None
        self._build(recorder, serial_mgr)

    def _build(self, recorder, serial_mgr):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Top bar (always visible)
        self._top_bar = _ReplayTopBar()
        root.addWidget(self._top_bar)

        # Session summary bar (hidden until loaded)
        self._summary = _SessionSummaryBar()
        self._summary.setVisible(False)
        root.addWidget(self._summary)

        # Stacked: empty state OR content
        self._stack = QStackedWidget()
        root.addWidget(self._stack, stretch=1)

        # Page 0: empty state
        self._empty = _EmptyState()
        self._empty.load_clicked.connect(self._on_load)
        self._stack.addWidget(self._empty)

        # Page 1: content (studio + insights)
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        split = QSplitter(Qt.Orientation.Horizontal)
        split.setHandleWidth(2)

        self.studio = ReplayStudio(recorder, serial_mgr)
        split.addWidget(self.studio)

        self.insights = InsightsPanel()
        split.addWidget(self.insights)
        split.setSizes([820, 200])

        # Wire signals after both widgets exist
        self.studio.events_detected.connect(self._summary.set_event_count)
        self.studio.events_ready.connect(self.insights.load_event_summary)

        content_layout.addWidget(split)
        self._stack.addWidget(content)

        self._stack.setCurrentIndex(0)  # start on empty state

        # Wire top bar
        self._top_bar.load_clicked.connect(self._on_load)
        self._top_bar.export_csv_clicked.connect(self._on_export_csv)
        self._top_bar.export_events_clicked.connect(self._on_export_events_csv)
        self._top_bar.export_png_clicked.connect(self.studio._export_plot)

    # ─────────────────────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────────────────────

    def load_imported_session(self, capsule: dict, session: ActiveSession) -> None:
        """
        Load an imported dataset capsule into the replay studio.

        This is the clean external entry point for the file-import workflow.
        Populates the summary bar from the richer ActiveSession metadata
        (sample rate, source type, warnings) rather than guessing from frames.

        Args:
            capsule:  Data Capsule dict (from dataset_to_session()).
            session:  ActiveSession descriptor for the same capsule.
        """
        label = session.label
        self._capsule = capsule
        self.studio._clear_all()
        self.studio.load_session_from_dict(capsule, label=label, is_primary=True)

        # Populate insights from the capsule
        self.insights._clear_insights()
        for evt in capsule.get("insights", []):
            self.insights.add_insight(evt)

        # Update summary bar with full import metadata
        events = len(capsule.get("insights", []))
        self._summary.update_from_session(session, events)
        self._top_bar.set_loaded(label)
        self._summary.setVisible(True)
        self._stack.setCurrentIndex(1)

    def load_session(self, path: str):
        """Load a session by file path. Can be called externally."""
        if not path or not os.path.exists(path):
            return
        self._session_path = path
        self._capsule = None  # cleared until JSON loads
        try:
            with open(path) as f:
                data = json.load(f)
        except Exception as exc:
            logger.error(f"Failed to load session: {exc}")
            return
        self._capsule = data

        self.studio._clear_all()
        self.studio._load_session(path, is_primary=True)

        self.insights._clear_insights()
        for evt in data.get("insights", []):
            self.insights.add_insight(evt)

        # Build summary
        meta  = data.get("meta", {})
        frames = meta.get("frame_count", len(data.get("frames", [])))
        name   = meta.get("session_id", os.path.basename(path))
        sr     = meta.get("sample_rate_estimate", 0)
        duration = frames / sr if sr else 0.0
        events = len(data.get("insights", []))

        # Compute peak THD from frames if available
        peak_thd = None
        raw_frames = data.get("frames", [])
        if raw_frames:
            thds = [f.get("thd") for f in raw_frames if f.get("thd") is not None]
            if thds:
                peak_thd = max(thds)

        self._top_bar.set_loaded(name)
        self._summary.set_data(name, frames, duration, events, peak_thd)
        self._summary.setVisible(True)
        self._stack.setCurrentIndex(1)

    def try_autoload_last_session(self, sessions_dir: str = "data/sessions"):
        """Auto-load the most recently modified session file if available."""
        try:
            files = [
                os.path.join(sessions_dir, f)
                for f in os.listdir(sessions_dir)
                if f.endswith(".json")
            ]
            if not files:
                return
            latest = max(files, key=os.path.getmtime)
            self.load_session(latest)
        except Exception as exc:
            logger.debug(f"Auto-load skipped: {exc}")

    # ─────────────────────────────────────────────────────────────
    # Internal
    # ─────────────────────────────────────────────────────────────

    def _on_load(self):
        fname, _ = QFileDialog.getOpenFileName(
            self, "Open Session", "data/sessions", "JSON Files (*.json)"
        )
        if fname:
            self.load_session(fname)

    def _on_export_csv(self):
        capsule = self._capsule or self.studio.get_primary_capsule()
        if capsule is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Session CSV", "exports/session_export.csv", "CSV (*.csv)"
        )
        if path:
            try:
                from src.session_exporter import export_session_csv
                export_session_csv(capsule, path)
            except Exception as exc:
                logger.error(f"CSV export failed: {exc}")

    def _on_export_events_csv(self):
        events = self.studio.get_events()
        if not events:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Events CSV", "exports/events_export.csv", "CSV (*.csv)"
        )
        if path:
            try:
                from src.session_exporter import export_events_csv
                annotations = self.studio.get_annotations()
                export_events_csv(events, annotations, path)
            except Exception as exc:
                logger.error(f"Events CSV export failed: {exc}")


# ─────────────────────────────────────────────────────────────────
# Sub-widgets
# ─────────────────────────────────────────────────────────────────

class _EmptyState(QWidget):
    """Centered empty-state shown when no session is loaded."""
    load_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setAlignment(Qt.AlignmentFlag.AlignCenter)

        card = QFrame()
        card.setObjectName("EmptyStateCard")
        card.setFixedWidth(400)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(32, 36, 32, 36)
        layout.setSpacing(12)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        icon = QLabel("⏵")
        icon.setObjectName("EmptyIcon")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon)

        title = QLabel("No Session Loaded")
        title.setObjectName("EmptyTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        desc = QLabel(
            "Import a run file from the Overview to start analysis,\n"
            "or load a previously saved session below."
        )
        desc.setObjectName("EmptyDesc")
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc.setWordWrap(True)
        layout.addWidget(desc)

        layout.addSpacing(8)

        btn = QPushButton("Load Session")
        btn.setObjectName("EmptyAction")
        btn.clicked.connect(self.load_clicked)
        layout.addWidget(btn, alignment=Qt.AlignmentFlag.AlignCenter)

        outer.addWidget(card)


class _SessionSummaryBar(QFrame):
    """Compact summary row shown after a session is loaded."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("SummaryBar")
        self.setFixedHeight(40)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(24)

        self._name     = self._chip("—")
        self._frames   = self._chip("— frames")
        self._duration = self._chip("—s")
        self._events   = self._chip("—")
        self._thd      = self._chip("Peak THD —")
        self._channels = self._chip("—")

        for w in [self._name, self._frames, self._duration,
                  self._events, self._thd, self._channels]:
            layout.addWidget(w)
        layout.addStretch()

    @staticmethod
    def _chip(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("SummaryChip")
        return lbl

    def set_event_count(self, n: int) -> None:
        """Update just the event count chip (called after async detection)."""
        self._events.setText(f"{n} event{'s' if n != 1 else ''} detected")
        color = "#ef4444" if n > 0 else "#64748b"
        self._events.setStyleSheet(f"color: {color}; font-weight: {'700' if n > 0 else '400'};")

    def set_data(self, name: str, frames: int, duration: float,
                 events: int, peak_thd: float | None):
        self._name.setText(name)
        self._frames.setText(f"{frames:,} frames")
        self._duration.setText(f"{duration:.1f}s" if duration else "—s")
        self._events.setText(f"{events} event{'s' if events != 1 else ''}")
        if peak_thd is not None:
            color = "#ef4444" if peak_thd > 10 else "#f59e0b" if peak_thd > 5 else "#10b981"
            self._thd.setText(f"Peak THD {peak_thd:.1f}%")
            self._thd.setStyleSheet(f"color: {color}; font-weight: 700;")
        else:
            self._thd.setText("Peak THD —")
        self._channels.setText("—")

    def update_from_session(self, session: ActiveSession, events: int = 0) -> None:
        """Populate the summary bar from a richer ActiveSession descriptor."""
        self._name.setText(
            f"{session.source_type_display}  ·  {session.source_filename}"
        )
        self._frames.setText(f"{session.row_count_display} rows")
        self._duration.setText(session.duration_display)
        # Event count will be filled in by events_detected signal after detection runs
        self._events.setText("Scanning…")
        self._events.setStyleSheet("color: #64748b;")

        # Show sample rate instead of peak THD for imported sessions
        # (THD is computed live during replay, not stored in import_meta)
        self._thd.setText(f"Rate: {session.sample_rate_display}")
        self._thd.setStyleSheet("")

        # Warning indicator
        if session.has_warnings:
            n = len(session.warnings)
            tip = "\n".join(session.warnings)
            self._name.setToolTip(f"{n} warning(s):\n{tip}")
            self._name.setStyleSheet("color: #f59e0b; font-weight: 600;")

        # Channel names chip
        all_ch = list(session.mapped_channels) + list(session.unmapped_channels)
        if all_ch:
            ch_str = "  ".join(all_ch[:5])
            if len(all_ch) > 5:
                ch_str += f" +{len(all_ch)-5}"
            self._channels.setText(ch_str)
            self._channels.setToolTip("Channels: " + ", ".join(all_ch))
        else:
            self._channels.setText("—")


class _ReplayTopBar(QWidget):
    load_clicked       = pyqtSignal()
    export_csv_clicked = pyqtSignal()
    export_events_clicked = pyqtSignal()
    export_png_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("PageTopBar")
        self.setFixedHeight(52)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(8)

        self._lbl = QLabel("Replay Studio  —  session timeline and analysis")
        self._lbl.setObjectName("PageTitle")
        layout.addWidget(self._lbl)
        layout.addStretch()

        btn_load = QPushButton("Load Session")
        btn_load.clicked.connect(self.load_clicked)
        btn_csv = QPushButton("Export Session CSV")
        btn_csv.setObjectName("ExportBtn")
        btn_csv.clicked.connect(self.export_csv_clicked)
        btn_events = QPushButton("Export Events CSV")
        btn_events.setObjectName("ExportBtn")
        btn_events.clicked.connect(self.export_events_clicked)
        btn_png = QPushButton("Export PNG")
        btn_png.clicked.connect(self.export_png_clicked)

        for btn in [btn_load, btn_csv, btn_events, btn_png]:
            layout.addWidget(btn)

        self._export_btns = [btn_csv, btn_events, btn_png]
        self.set_unloaded()

    def set_unloaded(self) -> None:
        for b in self._export_btns:
            b.setEnabled(False)
            b.setToolTip("Load a session first")

    def set_loaded(self, name: str):
        self._lbl.setText(f"Replay  ·  {name}")
        for b in self._export_btns:
            b.setEnabled(True)
            b.setToolTip("")
