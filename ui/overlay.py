from PyQt6.QtWidgets import QLabel, QWidget, QGraphicsOpacityEffect
from PyQt6.QtCore import QPropertyAnimation, QEasingCurve, QTimer, Qt


class OverlayMessage(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.label = QLabel(parent)
        self.label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.label.hide()

        self.opacity = QGraphicsOpacityEffect(self.label)
        self.label.setGraphicsEffect(self.opacity)
        self.anim = QPropertyAnimation(self.opacity, b"opacity")
        self.anim.setDuration(1200)
        self.anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    def show_message(self, text, color="#38bdf8", pos=(10, 10)):
        self.label.setText(text)
        self.label.setStyleSheet(
            "background: rgba(15,23,42,200);"
            "color: %s; border:1px solid rgba(148,163,184,0.3);"
            "border-radius:8px; padding:6px 10px; font-weight:600;" % color
        )
        self.label.adjustSize()
        self.label.move(pos[0], pos[1])
        self.label.show()

        self.anim.stop()
        self.opacity.setOpacity(1.0)
        self.anim.setStartValue(1.0)
        self.anim.setEndValue(0.0)
        self.anim.start()

        QTimer.singleShot(1300, self.label.hide)
