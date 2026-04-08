import logging
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
                             QPushButton, QLabel, QFrame)
from PyQt6.QtCore import Qt, QObject, QTimer, pyqtSlot

from ui.inverter_scope import InverterScope
from ui.phasor_view import PhasorView
from ui.fault_injector import FaultInjector
from ui.insights_panel import InsightsPanel
from ui.live_status_panel import LiveStatusPanel

logger = logging.getLogger(__name__)

# How often (ms) to flush batched insights to the panel — prevents UI spam
_INSIGHT_FLUSH_MS = 2000
# How often (ms) to update the health card metrics
_METRICS_UPDATE_MS = 500


class DiagnosticsPage(QWidget):
    """
    Hero surface — live monitoring.

    Layout:
      [SystemHealthCard — status badge, current issue, key metrics]
      [InverterScope (55%) | PhasorView / FaultInjector (30%) | InsightsPanel (15%)]
    """

    def __init__(self, serial_mgr, scenario_ctrl, insight_engine,
                 enable_3d: bool = True, parent=None):
        super().__init__(parent)
        self._serial_mgr = serial_mgr
        self._enable_3d = enable_3d
        self._3d_widget = None
        self._build(serial_mgr, scenario_ctrl, insight_engine)

    def _build(self, serial_mgr, scenario_ctrl, insight_engine):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Live source status — shows adapter, fps, active channels, warnings
        self.live_status = LiveStatusPanel()
        root.addWidget(self.live_status)
        serial_mgr.connection_status.connect(self.live_status.set_connected)
        serial_mgr.live_stats_updated.connect(self.live_status.update_stats)

        # System health card — replaces the raw status strip
        self._health = _SystemHealthCard()
        root.addWidget(self._health)

        # Wire health card to live data (throttled internally)
        serial_mgr.frame_received.connect(self._health.on_frame)
        insight_engine.insight_emitted.connect(self._health.on_insight)

        # Insight batcher — buffers events, flushes to panel every 2s
        self.insights = InsightsPanel()
        self._batcher = _InsightBatcher(self.insights, interval_ms=_INSIGHT_FLUSH_MS)
        insight_engine.insight_emitted.connect(self._batcher.accept)

        # Optional 3D toggle
        if self._enable_3d:
            btn_bar = QWidget()
            btn_bar.setObjectName("DiagBtnBar")
            bbl = QHBoxLayout(btn_bar)
            bbl.setContentsMargins(8, 3, 8, 3)
            bbl.setSpacing(6)
            self._btn_3d = QPushButton("Show 3D View")
            self._btn_3d.setObjectName("ToggleBtn")
            self._btn_3d.setCheckable(True)
            self._btn_3d.toggled.connect(self._toggle_3d)
            bbl.addWidget(self._btn_3d)
            bbl.addStretch()
            root.addWidget(btn_bar)

        # Main splitter
        main_split = QSplitter(Qt.Orientation.Horizontal)
        main_split.setHandleWidth(2)

        self.scope = InverterScope(serial_mgr)
        main_split.addWidget(self.scope)

        right_split = QSplitter(Qt.Orientation.Vertical)
        right_split.setHandleWidth(2)
        self.phasor = PhasorView(serial_mgr)
        self.fault_injector = FaultInjector(scenario_ctrl, serial_mgr)
        right_split.addWidget(self.phasor)
        right_split.addWidget(self.fault_injector)
        right_split.setSizes([300, 220])
        main_split.addWidget(right_split)

        main_split.addWidget(self.insights)
        main_split.setSizes([600, 360, 200])

        root.addWidget(main_split, stretch=1)

    def _toggle_3d(self, checked: bool):
        if not self._enable_3d:
            return
        if self._3d_widget is None and checked:
            try:
                from ui.system_3d_view import System3DView
                self._3d_widget = System3DView(self._serial_mgr)
                self._3d_widget.setWindowTitle("3D System View")
                self._3d_widget.resize(520, 420)
            except Exception as exc:
                logger.warning(f"3D view unavailable: {exc}")
                self._btn_3d.setChecked(False)
                return
        if self._3d_widget:
            self._3d_widget.setVisible(checked)
            if checked:
                self._3d_widget.show()


class _InsightBatcher(QObject):
    """
    Buffers incoming insight events and flushes them to the InsightsPanel
    on a fixed-interval timer instead of immediately.  Eliminates UI spam.
    """

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


class _SystemHealthCard(QFrame):
    """
    Replaces the raw status strip with a meaningful status card.

    Shows:
      [STATUS BADGE]  Current Issue  |  RMS  THD  Freq  |  ● LIVE
    """

    _STATUS_STABLE  = ("STABLE",       "#10b981", "rgba(16,185,129,25)")
    _STATUS_WARNING = ("WARNING",       "#f59e0b", "rgba(245,158,11,25)")
    _STATUS_FAULT   = ("FAULT ACTIVE",  "#ef4444", "rgba(239,68,68,30)")

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("HealthCard")
        self.setFixedHeight(56)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(0)

        # Status badge
        self._badge = QLabel("STABLE")
        self._badge.setObjectName("HealthBadgeStable")
        self._badge.setFixedWidth(110)
        self._badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._badge)

        # Divider
        d1 = self._divider()
        layout.addWidget(d1)
        layout.addSpacing(12)

        # Current issue
        self._issue = QLabel("System nominal  —  no active faults")
        self._issue.setObjectName("HealthIssue")
        layout.addWidget(self._issue)

        layout.addStretch()

        # Metrics
        self._rms  = self._metric("RMS —")
        self._thd  = self._metric("THD —")
        self._freq = self._metric("Freq —")
        for m in [self._rms, self._thd, self._freq]:
            layout.addSpacing(20)
            layout.addWidget(m)

        layout.addSpacing(16)
        d2 = self._divider()
        layout.addWidget(d2)
        layout.addSpacing(12)

        # Live indicator
        self._live = QLabel("● LIVE")
        self._live.setObjectName("StatusLive")
        layout.addWidget(self._live)

        # Rate-limit metrics updates
        self._pending: dict = {}
        self._metrics_timer = QTimer()
        self._metrics_timer.timeout.connect(self._apply_pending)
        self._metrics_timer.start(_METRICS_UPDATE_MS)

        self._current_status = "stable"

    @staticmethod
    def _metric(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("HealthMetric")
        return lbl

    @staticmethod
    def _divider() -> QFrame:
        f = QFrame()
        f.setFrameShape(QFrame.Shape.VLine)
        f.setObjectName("HealthDivider")
        return f

    def on_frame(self, frame: dict):
        """Buffer frame data — applied at _METRICS_UPDATE_MS rate."""
        self._pending["rms"]  = frame.get("v_rms")
        self._pending["thd"]  = frame.get("thd")
        self._pending["freq"] = frame.get("freq")
        fault = frame.get("fault_type")
        if fault and self._current_status != "fault":
            self._current_status = "fault"
            self._pending["status"] = "fault"
            self._pending["issue"] = f"Fault active: {fault}"
        elif not fault and self._current_status == "fault":
            self._current_status = "stable"
            self._pending["status"] = "stable"
            self._pending["issue"] = "System nominal  —  no active faults"

    @pyqtSlot(dict)
    def on_insight(self, payload: dict):
        """Update status badge when an insight fires."""
        severity = payload.get("severity", "info")
        kind = payload.get("type", "")
        desc = payload.get("description", "")

        if severity == "critical" and self._current_status != "fault":
            self._current_status = "warning"
            self._pending["status"] = "warning"
            self._pending["issue"] = f"{kind}: {desc}"
        elif severity == "warning" and self._current_status == "stable":
            self._current_status = "warning"
            self._pending["status"] = "warning"
            self._pending["issue"] = f"{kind}: {desc}"

    def _apply_pending(self):
        if not self._pending:
            return
        p = self._pending
        self._pending = {}

        rms = p.get("rms")
        thd = p.get("thd")
        freq = p.get("freq")
        if rms is not None:
            self._rms.setText(f"RMS {rms:.1f}V")
        if thd is not None:
            color = "#ef4444" if thd > 10 else "#f59e0b" if thd > 5 else "#94a3b8"
            self._thd.setText(f"THD {thd:.1f}%")
            self._thd.setStyleSheet(f"color: {color}; font-weight: 600;")
        if freq is not None:
            ok = 59.0 <= freq <= 61.0
            color = "#94a3b8" if ok else "#f59e0b"
            self._freq.setText(f"{freq:.2f} Hz")
            self._freq.setStyleSheet(f"color: {color}; font-weight: 600;")

        status = p.get("status")
        issue = p.get("issue")
        if status:
            self._apply_status(status)
        if issue:
            self._issue.setText(issue)

    def _apply_status(self, status: str):
        if status == "fault":
            label, fg, bg = self._STATUS_FAULT
        elif status == "warning":
            label, fg, bg = self._STATUS_WARNING
        else:
            label, fg, bg = self._STATUS_STABLE
        self._badge.setText(label)
        self._badge.setStyleSheet(
            f"color: {fg}; background: {bg}; border: 1px solid {fg};"
            f"border-radius: 8px; font-weight: 700; font-size: 9pt; padding: 2px 8px;"
        )
