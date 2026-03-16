from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel, QPushButton
from PyQt6.QtCore import pyqtSignal, QTimer


class SessionBar(QWidget):
    """Top bar showing app title, session context, and simulation controls."""

    run_clicked = pyqtSignal()
    pause_clicked = pyqtSignal()
    stop_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("SessionBar")
        self.setFixedHeight(52)
        self._build()

    def _build(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(12)

        title = QLabel("REDBYTE")
        title.setObjectName("SessionBarTitle")
        layout.addWidget(title)

        div = QLabel("·")
        div.setObjectName("SessionBarDiv")
        layout.addWidget(div)

        self.lbl_mode = QLabel("READY")
        self.lbl_mode.setObjectName("ModeBadge")
        layout.addWidget(self.lbl_mode)

        self.lbl_source = QLabel("—")
        self.lbl_source.setObjectName("SessionBarSource")
        layout.addWidget(self.lbl_source)

        self.lbl_state = QLabel("")
        self.lbl_state.setObjectName("SimState")
        layout.addWidget(self.lbl_state)

        layout.addSpacing(8)
        self._rec_dot = QLabel("● REC")
        self._rec_dot.setObjectName("RecordDot")
        self._rec_dot.setVisible(False)
        layout.addWidget(self._rec_dot)

        self._rec_timer = QTimer()
        self._rec_timer.timeout.connect(self._blink_rec)
        self._rec_visible = True

        layout.addStretch()

        self.btn_run = QPushButton("▶  Run")
        self.btn_run.setObjectName("SimBtnRun")
        self.btn_run.clicked.connect(self.run_clicked)

        self.btn_pause = QPushButton("⏸  Pause")
        self.btn_pause.setObjectName("SimBtn")
        self.btn_pause.clicked.connect(self.pause_clicked)
        self.btn_pause.setEnabled(False)

        self.btn_stop = QPushButton("⏹  Stop")
        self.btn_stop.setObjectName("SimBtn")
        self.btn_stop.clicked.connect(self.stop_clicked)
        self.btn_stop.setEnabled(False)

        for btn in [self.btn_run, self.btn_pause, self.btn_stop]:
            layout.addWidget(btn)

    def set_recording(self, active: bool):
        if active:
            self._rec_visible = True
            self._rec_dot.setVisible(True)
            self._rec_timer.start(600)
        else:
            self._rec_timer.stop()
            self._rec_dot.setVisible(False)

    def _blink_rec(self):
        self._rec_visible = not self._rec_visible
        self._rec_dot.setVisible(self._rec_visible)

    def set_mode(self, mode: str):
        self.lbl_mode.setText(mode.upper())

    def set_source(self, source: str):
        self.lbl_source.setText(source)

    def update_sim_state(self, state: str):
        """Update button enabled states and state label from SimulationController state."""
        labels = {
            "idle": "Idle",
            "running": "● Running",
            "paused": "⏸ Paused",
            "stopped": "■ Stopped",
        }
        self.lbl_state.setText(labels.get(state, state))

        running = state == "running"
        paused = state == "paused"
        stopped_or_idle = state in ("idle", "stopped")

        self.btn_run.setEnabled(not running)
        self.btn_pause.setEnabled(running)
        self.btn_stop.setEnabled(running or paused)
