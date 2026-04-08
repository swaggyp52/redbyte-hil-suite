from PyQt6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QLabel, QFrame
from PyQt6.QtCore import pyqtSignal, Qt

_NAV_ITEMS = [
    ("overview",    "⊞",  "Overview"),
    ("diagnostics", "⚡", "Diagnostics"),
    ("replay",      "⏵",  "Replay"),
    ("compliance",  "✓",  "Compliance"),
    ("console",     "📐", "Monitor"),
]

_TOOL_ITEMS = [
    ("tools", "⚙", "Tools"),
]


class Sidebar(QWidget):
    """Left navigation sidebar. Emits page_changed(key) on nav click."""

    page_changed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._buttons = {}
        self._active = None
        self._build()

    def _build(self):
        self.setFixedWidth(160)
        self.setObjectName("Sidebar")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 16, 8, 12)
        layout.setSpacing(2)

        logo = QLabel("REDBYTE")
        logo.setObjectName("SidebarLogo")
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(logo)

        sub = QLabel("GFM HIL Suite")
        sub.setObjectName("SidebarSub")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(sub)

        layout.addSpacing(20)

        for key, icon, label in _NAV_ITEMS:
            btn = self._make_nav_btn(key, icon, label)
            self._buttons[key] = btn
            layout.addWidget(btn)

        layout.addStretch()

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setObjectName("SidebarSep")
        layout.addWidget(sep)

        layout.addSpacing(4)

        for key, icon, label in _TOOL_ITEMS:
            btn = self._make_nav_btn(key, icon, label)
            self._buttons[key] = btn
            layout.addWidget(btn)

    def _make_nav_btn(self, key, icon, label):
        btn = QPushButton(f"  {icon}  {label}")
        btn.setObjectName("NavBtn")
        btn.setCheckable(True)
        btn.clicked.connect(lambda _, k=key: self._select(k))
        return btn

    def _select(self, key):
        if self._active == key:
            return
        if self._active and self._active in self._buttons:
            self._buttons[self._active].setChecked(False)
        self._active = key
        self._buttons[key].setChecked(True)
        self.page_changed.emit(key)

    def select(self, key):
        """Programmatically select a page without re-emitting if already active."""
        self._select(key)
