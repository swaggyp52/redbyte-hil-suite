from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel
from PyQt6.QtCore import QTimer, pyqtSignal
import collections
import time

from src.signal_processing import compute_rms, compute_thd


class StatusBarWidget(QWidget):
    metrics_updated = pyqtSignal(float, float)
    """Compact status bar widget showing mode, RMS, and THD."""
    def __init__(self, serial_mgr, parent=None):
        super().__init__(parent)
        self.serial_mgr = serial_mgr
        self.mode = "LIVE"
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(6, 2, 6, 2)

        self.lbl_mode = QLabel("Mode: LIVE")
        self.lbl_rms = QLabel("RMS: --")
        self.lbl_thd = QLabel("THD: --")

        badge_style = "background:#0f172a; border:1px solid #1f2a3a; border-radius:8px; padding:4px 8px;"
        self.lbl_mode.setStyleSheet(badge_style + " color:#93c5fd; font-weight:600;")
        self.lbl_rms.setStyleSheet(badge_style + " color:#e2e8f0;")
        self.lbl_thd.setStyleSheet(badge_style + " color:#fca5a5;")

        self.lbl_rms.setToolTip("RMS: Root-mean-square voltage. Typical target ~120V RMS.")
        self.lbl_thd.setToolTip("THD: Total harmonic distortion. Ideal <5%.")

        self.layout.addWidget(self.lbl_mode)
        self.layout.addWidget(self.lbl_rms)
        self.layout.addWidget(self.lbl_thd)

        self._buf_v = collections.deque(maxlen=200)
        self._buf_ts = collections.deque(maxlen=200)
        self._last_rms = None
        self._last_thd = None

        self.serial_mgr.frame_received.connect(self._on_frame)

        self.timer = QTimer()
        self.timer.timeout.connect(self._update_metrics)
        self.timer.start(250)

    def set_mode(self, mode: str):
        self.mode = mode
        self.lbl_mode.setText(f"Mode: {mode}")

    def _on_frame(self, frame):
        self._buf_v.append(frame.get("v_an", 0.0))
        self._buf_ts.append(frame.get("ts", time.time()))

    def _update_metrics(self):
        if not self._buf_v:
            return
        rms = compute_rms(list(self._buf_v))
        thd = compute_thd(list(self._buf_v), time_data=list(self._buf_ts))
        self.lbl_rms.setText(f"RMS: {rms:.1f} V")
        self.lbl_thd.setText(f"THD: {thd:.1f}%")
        self.metrics_updated.emit(rms, thd)

        if self._last_rms is not None and abs(rms - self._last_rms) > 4.0:
            self.lbl_rms.setStyleSheet(self.lbl_rms.styleSheet() + " background:#1f2937;")
        if self._last_thd is not None and abs(thd - self._last_thd) > 2.0:
            self.lbl_thd.setStyleSheet(self.lbl_thd.styleSheet() + " background:#3f1d1d;")

        self._last_rms = rms
        self._last_thd = thd
