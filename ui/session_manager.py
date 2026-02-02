from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QPushButton, QLabel, 
                             QFileDialog, QHBoxLayout, QGroupBox)
from PyQt6.QtCore import pyqtSignal
import os

class SessionApp(QWidget):
    """
    Controls for Recording and Replaying sessions.
    """
    record_toggled = pyqtSignal(bool) # True = Start, False = Stop
    replay_requested = pyqtSignal(str) # Filepath

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Session Manager")
        self.layout = QVBoxLayout(self)

        header = QLabel("Session Manager — Record & Replay")
        header.setStyleSheet("font-size: 12pt; font-weight: 700; color: #facc15;")
        self.layout.addWidget(header)

        # Recorder Section
        grp_record = QGroupBox("Data Recorder")
        rec_layout = QVBoxLayout()
        self.btn_record = QPushButton("Start Recording")
        self.btn_record.setCheckable(True)
        self.btn_record.clicked.connect(self._on_record_clicked)
        self.lbl_rec_status = QLabel("Ready")
        rec_layout.addWidget(self.btn_record)
        rec_layout.addWidget(self.lbl_rec_status)
        grp_record.setLayout(rec_layout)
        self.layout.addWidget(grp_record)

        # Replay Section
        grp_replay = QGroupBox("Replay Engine")
        rep_layout = QVBoxLayout()
        self.btn_load = QPushButton("Load Session File...")
        self.btn_load.clicked.connect(self._load_file)
        self.btn_replay = QPushButton("Start Replay")
        self.btn_replay.clicked.connect(self._start_replay)
        self.btn_replay.setEnabled(False)
        self.lbl_file = QLabel("No file loaded")
        rep_layout.addWidget(self.btn_load)
        rep_layout.addWidget(self.lbl_file)
        rep_layout.addWidget(self.btn_replay)
        grp_replay.setLayout(rep_layout)
        self.layout.addWidget(grp_replay)
        
        self.current_replay_file = None

    def _on_record_clicked(self):
        is_recording = self.btn_record.isChecked()
        if is_recording:
            self.btn_record.setText("Stop Recording")
            self.lbl_rec_status.setText("Recording...")
            self.btn_record.setStyleSheet("background-color: #ffcccc")
        else:
            self.btn_record.setText("Start Recording")
            self.lbl_rec_status.setText("Stopped")
            self.btn_record.setStyleSheet("")
        
        self.record_toggled.emit(is_recording)

    def _load_file(self):
        fname, _ = QFileDialog.getOpenFileName(self, "Open Session", os.getcwd(), "JSON Files (*.json)")
        if fname:
            self.current_replay_file = fname
            self.lbl_file.setText(os.path.basename(fname))
            self.btn_replay.setEnabled(True)

    def _start_replay(self):
        if self.current_replay_file:
            self.replay_requested.emit(self.current_replay_file)
