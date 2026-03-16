"""
ConsolePage — Capstone Demo Console for the RedByte GFM HIL Suite.

A single-screen dashboard designed to show all key capabilities at once
for poster screenshots and live demonstrations.

Layout (1440×900 window):
  _ConsoleHeaderBar  (72px, full width — title + live metrics + status)
  [InverterScope | QSplitter: PhasorView / _CompactIEEEPanel | InsightsPanel]
"""
import json
import logging

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
                              QLabel, QFrame, QPushButton)
from PyQt6.QtCore import Qt, QObject, QTimer, pyqtSlot

from ui.inverter_scope import InverterScope
from ui.phasor_view import PhasorView
from ui.insights_panel import InsightsPanel

logger = logging.getLogger(__name__)

_METRICS_UPDATE_MS = 250   # header update rate — 4 Hz
_INSIGHT_FLUSH_MS  = 2000  # insight batcher flush interval


# ──────────────────────────────────────────────────────────────────────────────
# ConsolePage
# ──────────────────────────────────────────────────────────────────────────────

class ConsolePage(QWidget):
    """
    Capstone Demo Console — all key capabilities in one view.

    Identical backend wiring to DiagnosticsPage but arranged for a cleaner
    single-screenshot poster presentation.
    """

    def __init__(self, serial_mgr, insight_engine, parent=None):
        super().__init__(parent)
        self._build(serial_mgr, insight_engine)

    def _build(self, serial_mgr, insight_engine):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Header bar ───────────────────────────────────────────────────────
        self._header = _ConsoleHeaderBar()
        root.addWidget(self._header)
        serial_mgr.frame_received.connect(self._header.on_frame)
        insight_engine.insight_emitted.connect(self._header.on_insight)

        # ── Body: three columns ──────────────────────────────────────────────
        body = QWidget()
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)

        # Left: waveform scope (stretches to fill remaining width)
        self.scope = InverterScope(serial_mgr)
        body_layout.addWidget(self.scope, stretch=1)

        # Center: phasor (top) + IEEE compliance panel (bottom)
        center_split = QSplitter(Qt.Orientation.Vertical)
        center_split.setHandleWidth(2)
        center_split.setFixedWidth(320)

        self.phasor = PhasorView(serial_mgr)
        center_split.addWidget(self.phasor)

        self._ieee = _CompactIEEEPanel()
        center_split.addWidget(self._ieee)
        center_split.setSizes([540, 236])

        body_layout.addWidget(center_split)

        # Right: insights panel (fixed width, scrollable clusters)
        self.insights = InsightsPanel()
        self.insights.setFixedWidth(280)
        body_layout.addWidget(self.insights)

        # Insight batcher — buffers events, flushes every 2s to avoid UI spam
        self._batcher = _InsightBatcher(self.insights, interval_ms=_INSIGHT_FLUSH_MS)
        insight_engine.insight_emitted.connect(self._batcher.accept)

        root.addWidget(body, stretch=1)

    # ── Public slots ──────────────────────────────────────────────────────────

    def on_sim_state(self, state: str):
        """Relay simulation state to the header REC timer."""
        self._header.on_sim_state(state)

    def load_session(self, path: str):
        """Pre-load a session so the IEEE panel can run compliance tests."""
        self._ieee.load_session(path)


# ──────────────────────────────────────────────────────────────────────────────
# _ConsoleHeaderBar
# ──────────────────────────────────────────────────────────────────────────────

class _ConsoleHeaderBar(QFrame):
    """
    Full-width 72px header showing live metrics prominently.

    Layout:
      [Title block (220px)] | [FREQ] [RMS] [THD] [POWER] chips | [Status badge] [●REC]
    """

    _STATUS_READY   = ("READY",         "#64748b", "rgba(30,41,59,80)",       "rgba(71,85,105,80)")
    _STATUS_STABLE  = ("✓ STABLE",      "#10b981", "rgba(16,185,129,25)",     "rgba(16,185,129,80)")
    _STATUS_WARNING = ("⚠ WARNING",     "#f59e0b", "rgba(245,158,11,25)",     "rgba(245,158,11,80)")
    _STATUS_FAULT   = ("✕ FAULT ACTIVE","#ef4444", "rgba(239,68,68,30)",      "rgba(239,68,68,80)")

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ConsoleHeader")
        self.setFixedHeight(72)
        self.setStyleSheet(
            "QFrame#ConsoleHeader {"
            "  background: qlineargradient(x1:0,y1:0,x2:0,y2:1,"
            "    stop:0 rgba(13,20,35,235), stop:1 rgba(10,14,26,245));"
            "  border-bottom: 1px solid rgba(31,41,55,200);"
            "}"
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(14)

        # Title block
        title_block = QWidget()
        title_block.setFixedWidth(220)
        tb = QVBoxLayout(title_block)
        tb.setContentsMargins(0, 8, 0, 8)
        tb.setSpacing(1)

        lbl_title = QLabel("REDBYTE  GFM HIL")
        lbl_title.setStyleSheet(
            "color: #e8eef5; font-size: 11pt; font-weight: 700; letter-spacing: 1px;"
        )
        tb.addWidget(lbl_title)

        lbl_sub = QLabel("VSM Inverter Monitor")
        lbl_sub.setStyleSheet("color: #64748b; font-size: 8pt; letter-spacing: 0.5px;")
        tb.addWidget(lbl_sub)

        layout.addWidget(title_block)
        layout.addWidget(_vline())

        # Metric chips — updated at 4 Hz
        self._chip_freq  = _MetricChip("FREQ",  "—  Hz")
        self._chip_rms   = _MetricChip("RMS V", "—  V")
        self._chip_thd   = _MetricChip("THD",   "—  %")
        self._chip_power = _MetricChip("POWER", "—  W")
        for chip in (self._chip_freq, self._chip_rms, self._chip_thd, self._chip_power):
            layout.addWidget(chip)

        layout.addStretch()
        layout.addWidget(_vline())

        # Status badge
        self._badge = QLabel("READY")
        self._badge.setFixedWidth(136)
        self._badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._badge)
        self._apply_status("ready")

        # REC timer
        self._rec = QLabel("● REC  00:00")
        self._rec.setStyleSheet(
            "color: #ef4444; font-size: 9pt; font-weight: 700;"
            "background: rgba(239,68,68,20); border-radius: 5px; padding: 2px 8px;"
        )
        self._rec.setVisible(False)
        layout.addWidget(self._rec)

        # Internal state
        self._pending: dict = {}
        self._current_status = "ready"
        self._elapsed_s = 0

        self._metrics_timer = QTimer()
        self._metrics_timer.timeout.connect(self._apply_pending)
        self._metrics_timer.start(_METRICS_UPDATE_MS)

        self._rec_timer = QTimer()
        self._rec_timer.timeout.connect(self._tick_rec)

    # ── Slots ─────────────────────────────────────────────────────────────────

    def on_frame(self, frame: dict):
        """Buffer frame data; applied at _METRICS_UPDATE_MS rate."""
        self._pending["freq"]  = frame.get("freq")
        self._pending["v_rms"] = frame.get("v_rms")
        self._pending["thd"]   = frame.get("thd")
        self._pending["power"] = frame.get("p_mech")

        fault = frame.get("fault_type")
        if fault and self._current_status != "fault":
            self._current_status = "fault"
            self._pending["status"] = "fault"
        elif not fault and self._current_status == "fault":
            self._current_status = "stable"
            self._pending["status"] = "stable"

    @pyqtSlot(dict)
    def on_insight(self, payload: dict):
        """Elevate badge to warning/fault level based on insight severity."""
        if self._current_status in ("ready", "stable"):
            severity = payload.get("severity", "info")
            if severity == "critical":
                self._current_status = "warning"
                self._pending["status"] = "warning"
            elif severity == "warning":
                self._current_status = "warning"
                self._pending["status"] = "warning"

    def on_sim_state(self, state: str):
        """Show the REC timer when running; hide it when stopped."""
        if state == "running":
            self._elapsed_s = 0
            self._rec.setVisible(True)
            self._rec_timer.start(1000)
            if self._current_status == "ready":
                self._current_status = "stable"
                self._pending["status"] = "stable"
        elif state in ("stopped", "idle"):
            self._rec.setVisible(False)
            self._rec_timer.stop()
            self._current_status = "ready"
            self._pending["status"] = "ready"
        elif state == "paused":
            self._rec_timer.stop()

    # ── Private ───────────────────────────────────────────────────────────────

    def _tick_rec(self):
        self._elapsed_s += 1
        mins, secs = divmod(self._elapsed_s, 60)
        self._rec.setText(f"● REC  {mins:02d}:{secs:02d}")

    def _apply_pending(self):
        if not self._pending:
            return
        p, self._pending = self._pending, {}

        freq = p.get("freq")
        if freq is not None:
            color = "#94a3b8" if 59.5 <= freq <= 60.5 else "#f59e0b"
            self._chip_freq.set_value(f"{freq:.2f} Hz", color)

        v_rms = p.get("v_rms")
        if v_rms is not None:
            color = "#94a3b8" if 90.0 <= v_rms <= 135.0 else "#ef4444"
            self._chip_rms.set_value(f"{v_rms:.1f} V", color)

        thd = p.get("thd")
        if thd is not None:
            color = "#ef4444" if thd > 10 else "#f59e0b" if thd > 5 else "#94a3b8"
            self._chip_thd.set_value(f"{thd:.1f} %", color)

        power = p.get("power")
        if power is not None:
            self._chip_power.set_value(f"{power:.0f} W", "#94a3b8")

        status = p.get("status")
        if status:
            self._apply_status(status)

    def _apply_status(self, status: str):
        mapping = {
            "fault":   self._STATUS_FAULT,
            "warning": self._STATUS_WARNING,
            "stable":  self._STATUS_STABLE,
            "ready":   self._STATUS_READY,
        }
        text, fg, bg, border = mapping.get(status, self._STATUS_READY)
        self._badge.setText(text)
        self._badge.setStyleSheet(
            f"color: {fg}; background: {bg}; border: 1px solid {border};"
            "border-radius: 8px; font-weight: 700; font-size: 9pt; padding: 4px 10px;"
        )


# ──────────────────────────────────────────────────────────────────────────────
# _MetricChip
# ──────────────────────────────────────────────────────────────────────────────

class _MetricChip(QFrame):
    """Compact display: small label name on top, large monospaced value below."""

    def __init__(self, name: str, initial: str = "—", parent=None):
        super().__init__(parent)
        self.setFixedWidth(100)
        self.setStyleSheet(
            "QFrame {"
            "  background: rgba(22,28,40,180);"
            "  border: 1px solid rgba(31,41,55,120);"
            "  border-radius: 6px;"
            "}"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(1)

        lbl_name = QLabel(name)
        lbl_name.setStyleSheet(
            "color: #64748b; font-size: 7pt; letter-spacing: 0.5px;"
            "background: transparent; border: none;"
        )
        lbl_name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl_name)

        self._value = QLabel(initial)
        self._value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._value.setStyleSheet(
            "color: #94a3b8; background: transparent; border: none;"
            "font-family: 'JetBrains Mono', 'Consolas', 'Courier New', monospace;"
            "font-size: 11pt; font-weight: 700;"
        )
        layout.addWidget(self._value)

    def set_value(self, text: str, color: str = "#94a3b8"):
        self._value.setText(text)
        self._value.setStyleSheet(
            f"color: {color}; background: transparent; border: none;"
            "font-family: 'JetBrains Mono', 'Consolas', 'Courier New', monospace;"
            "font-size: 11pt; font-weight: 700;"
        )


# ──────────────────────────────────────────────────────────────────────────────
# _CompactIEEEPanel
# ──────────────────────────────────────────────────────────────────────────────

class _CompactIEEEPanel(QWidget):
    """
    Compact IEEE 2800 compliance display for the Console page.

    Shows three rule rows with colored PASS/FAIL chips plus a
    "Run Tests" button that evaluates the currently loaded session.
    """

    _RULES = [
        "Ride-through 50% sag",
        "Frequency  ±0.5 Hz",
        "Voltage recovery",
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._session_data: dict | None = None
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 8)
        root.setSpacing(6)
        self.setStyleSheet(
            "background: rgba(13,18,28,200);"
            "border-top: 1px solid rgba(31,41,55,150);"
        )

        # Title row
        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)

        lbl = QLabel("IEEE 2800 Compliance")
        lbl.setStyleSheet(
            "color: #22d3ee; font-size: 10pt; font-weight: 700;"
            "background: transparent;"
        )
        title_row.addWidget(lbl)
        title_row.addStretch()

        self._run_btn = QPushButton("Run Tests")
        self._run_btn.setFixedHeight(24)
        self._run_btn.setEnabled(False)
        self._run_btn.setStyleSheet(
            "QPushButton {"
            "  background: rgba(59,130,246,160); color: white;"
            "  border: 1px solid rgba(59,130,246,80); border-radius: 5px;"
            "  font-size: 8pt; font-weight: 600; padding: 2px 10px;"
            "}"
            "QPushButton:hover { background: rgba(59,130,246,220); }"
            "QPushButton:disabled {"
            "  background: rgba(30,41,59,120); color: #475569;"
            "  border-color: rgba(71,85,105,60);"
            "}"
        )
        self._run_btn.clicked.connect(self._on_run_tests)
        title_row.addWidget(self._run_btn)
        root.addLayout(title_row)

        # Rule rows
        self._rows: list[_RuleRow] = []
        for name in self._RULES:
            row = _RuleRow(name)
            self._rows.append(row)
            root.addWidget(row)

        root.addStretch()

        # Session info label
        self._session_lbl = QLabel("No session loaded  —  run demo then 'Run Tests'")
        self._session_lbl.setStyleSheet(
            "color: #475569; font-size: 7pt; background: transparent;"
        )
        self._session_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._session_lbl.setWordWrap(True)
        root.addWidget(self._session_lbl)

    def load_session(self, path: str):
        """Load a session JSON file to make compliance testing possible."""
        try:
            with open(path, "r", encoding="utf-8") as f:
                self._session_data = json.load(f)
            session_id = self._session_data.get("meta", {}).get("session_id", "session")
            self._session_lbl.setText(f"Session: {session_id}")
            self._run_btn.setEnabled(True)
        except Exception as exc:
            logger.warning("IEEE panel: failed to load session %s: %s", path, exc)

    def set_results(self, results: list[dict]):
        """Populate rule rows from evaluate_ieee_2800() output."""
        for i, result in enumerate(results):
            if i < len(self._rows):
                self._rows[i].set_result(
                    passed=result.get("passed", False),
                    detail=result.get("details", ""),
                )

    def _on_run_tests(self):
        if self._session_data is None:
            return
        try:
            from src.compliance_checker import evaluate_ieee_2800
            results = evaluate_ieee_2800(self._session_data)
            self.set_results(results)
            n_pass = sum(1 for r in results if r.get("passed"))
            n_total = len(results)
            color = "#10b981" if n_pass == n_total else "#f59e0b" if n_pass > 0 else "#ef4444"
            self._session_lbl.setStyleSheet(f"color: {color}; font-size: 7pt; background: transparent;")
            self._session_lbl.setText(f"Result: {n_pass}/{n_total} checks passed")
        except Exception as exc:
            logger.error("IEEE compliance check failed: %s", exc)


# ──────────────────────────────────────────────────────────────────────────────
# _RuleRow
# ──────────────────────────────────────────────────────────────────────────────

class _RuleRow(QFrame):
    """Single IEEE rule row: colored dot + rule name + detail text + PASS/FAIL chip."""

    _SS_PASS    = ("color:#10b981; background:rgba(16,185,129,25);"
                   "border:1px solid rgba(16,185,129,80); border-radius:4px;"
                   "padding:1px 6px; font-size:8pt; font-weight:700;")
    _SS_FAIL    = ("color:#ef4444; background:rgba(239,68,68,25);"
                   "border:1px solid rgba(239,68,68,80); border-radius:4px;"
                   "padding:1px 6px; font-size:8pt; font-weight:700;")
    _SS_PENDING = ("color:#64748b; background:rgba(30,41,59,80);"
                   "border:1px solid rgba(71,85,105,60); border-radius:4px;"
                   "padding:1px 6px; font-size:8pt; font-weight:700;")

    def __init__(self, name: str, parent=None):
        super().__init__(parent)
        self.setFixedHeight(44)
        self.setStyleSheet(
            "QFrame {"
            "  background: rgba(17,24,39,120);"
            "  border-radius: 6px;"
            "  border: 1px solid rgba(31,41,55,100);"
            "}"
        )
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 0, 8, 0)
        layout.setSpacing(6)

        self._dot = QLabel("●")
        self._dot.setFixedWidth(10)
        self._dot.setStyleSheet("color: #475569; font-size: 7pt; background: transparent; border: none;")
        layout.addWidget(self._dot)

        col = QVBoxLayout()
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(0)

        self._name_lbl = QLabel(name)
        self._name_lbl.setStyleSheet(
            "color: #94a3b8; font-size: 8pt; font-weight: 600; background: transparent; border: none;"
        )
        col.addWidget(self._name_lbl)

        self._detail_lbl = QLabel("—")
        self._detail_lbl.setStyleSheet(
            "color: #475569; font-size: 7pt; background: transparent; border: none;"
        )
        col.addWidget(self._detail_lbl)
        layout.addLayout(col, stretch=1)

        self._chip = QLabel("—")
        self._chip.setFixedWidth(44)
        self._chip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._chip.setStyleSheet(self._SS_PENDING)
        layout.addWidget(self._chip)

    def set_result(self, passed: bool, detail: str = ""):
        if passed:
            self._dot.setStyleSheet("color: #10b981; font-size: 7pt; background: transparent; border: none;")
            self._chip.setText("PASS")
            self._chip.setStyleSheet(self._SS_PASS)
        else:
            self._dot.setStyleSheet("color: #ef4444; font-size: 7pt; background: transparent; border: none;")
            self._chip.setText("FAIL")
            self._chip.setStyleSheet(self._SS_FAIL)
        if detail:
            self._detail_lbl.setText(detail)


# ──────────────────────────────────────────────────────────────────────────────
# _InsightBatcher  (local copy — same logic as in diagnostics_page.py)
# ──────────────────────────────────────────────────────────────────────────────

class _InsightBatcher(QObject):
    """Buffers insight events and flushes to InsightsPanel on a fixed timer."""

    def __init__(self, panel: InsightsPanel, interval_ms: int = 2000, parent=None):
        super().__init__(parent)
        self._panel = panel
        self._queue: list[dict] = []
        self._timer = QTimer()
        self._timer.timeout.connect(self._flush)
        self._timer.start(interval_ms)

    @pyqtSlot(dict)
    def accept(self, payload: dict):
        self._queue.append(payload)

    def _flush(self):
        if not self._queue:
            return
        for evt in self._queue:
            self._panel.add_insight(evt)
        self._queue.clear()


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _vline() -> QFrame:
    """Return a styled vertical divider line."""
    f = QFrame()
    f.setFrameShape(QFrame.Shape.VLine)
    f.setStyleSheet("color: rgba(31,41,55,180);")
    return f
