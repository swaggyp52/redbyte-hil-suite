from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from ui.signal_sculptor import SignalSculptor


class ToolsPage(QWidget):
    """
    Secondary tools — Signal Sculptor for parametric waveform generation.
    Not part of the primary demo path.
    """

    def __init__(self, serial_mgr, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        header = QLabel("Tools  —  Signal Sculptor")
        header.setObjectName("PageHeader")
        layout.addWidget(header)

        self.sculptor = SignalSculptor(serial_mgr)
        layout.addWidget(self.sculptor)
        layout.addStretch()
