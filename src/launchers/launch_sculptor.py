"""
RedByte Signal Sculptor - Live waveform editing & filter tuning
Entry point for signal manipulation and custom waveform design
"""

import sys
from pathlib import Path

# Add parent and project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(Path(__file__).parent.parent))

from PyQt6.QtWidgets import QApplication, QToolBar
from PyQt6.QtGui import QAction

from hil_core import SessionContext
from ui.app_themes import get_sculptor_style
from ui.signal_sculptor import SignalSculptor
from ui.inverter_scope import InverterScope
from ui.splash_screen import RotorSplashScreen
from serial_reader import SerialManager
from launcher_base import LauncherBase


class SculptorWindow(LauncherBase):
    """RedByte Signal Sculptor main window"""

    app_name = "sculptor"

    def __init__(self):
        super().__init__()
        self.setWindowTitle("🟧 RedByte Signal Sculptor - Waveform Editing")
        self.resize(1200, 800)

        self.setStyleSheet(get_sculptor_style())

        # Initialize backend dependencies
        self.serial_mgr = SerialManager()

        self.create_panels()
        self.create_toolbar()
        self._setup_status_bar(self.serial_mgr)
        self._apply_panel_tooltips()
        self._finish_init()

    def create_panels(self):
        """Create sculptor panels"""
        # Signal Sculptor (editor)
        self.sculptor = SignalSculptor(self.serial_mgr)
        sub_sculptor = self.mdi.addSubWindow(self.sculptor)
        sub_sculptor.setWindowTitle("🎛️ Signal Editor")
        sub_sculptor.show()
        self._register_subwindow(sub_sculptor)

        # Mini Scope (preview)
        self.scope = InverterScope(self.serial_mgr)
        sub_scope = self.mdi.addSubWindow(self.scope)
        sub_scope.setWindowTitle("📊 Preview")
        sub_scope.show()
        self._register_subwindow(sub_scope)

        # Layout
        sub_sculptor.setGeometry(0, 0, 800, 600)
        sub_scope.setGeometry(800, 0, 400, 600)

    def create_toolbar(self):
        """Create toolbar"""
        toolbar = QToolBar("Sculptor")
        self.addToolBar(toolbar)

        act_apply = QAction("✔️ Apply Filter", self)
        toolbar.addAction(act_apply)

        act_export = QAction("💾 Export Waveform", self)
        toolbar.addAction(act_export)

        self._add_context_actions(toolbar)


def main():
    args = LauncherBase.parse_args()
    app = QApplication(sys.argv)
    splash = RotorSplashScreen()
    splash.show()
    app.processEvents()

    window = SculptorWindow()

    # Start in mock mode if requested
    if args.mock:
        window.serial_mgr.start_mock_mode()
        window.notify("Mock mode active", "#f59e0b")

    # Auto-load context if specified
    if args.load:
        import shutil
        dest = window.session.temp_dir / "redbyte_session_imported.json"
        shutil.copy(args.load, str(dest))
        window.session.import_context("imported")

    splash.finish(window)
    window.show()

    sys.exit(app.exec())


if __name__ == '__main__':
    main()
