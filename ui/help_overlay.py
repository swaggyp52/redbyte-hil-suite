from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton
from PyQt6.QtCore import Qt


class HelpOverlay(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.setStyleSheet("background: rgba(15, 23, 42, 230); border: 1px solid #1f2633; border-radius: 12px;")

        layout = QVBoxLayout(self)
        title = QLabel("Quick Tips")
        title.setStyleSheet("font-size: 12pt; font-weight: 700; color: #93c5fd;")
        layout.addWidget(title)

        tips = QLabel(
            "• Use Presentation Mode to hide controls.\n"
            "• Run Quick Demo to inject faults and auto-generate reports.\n"
            "• Capture Scene anytime to export visuals."
        )
        tips.setStyleSheet("color: #e2e8f0;")
        layout.addWidget(tips)

        btn = QPushButton("Got it")
        btn.clicked.connect(self.hide)
        layout.addWidget(btn)
