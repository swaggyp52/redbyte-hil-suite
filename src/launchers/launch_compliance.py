"""
RedByte Compliance Lab - Automated test suites & validation scoring
Entry point for standards compliance and waveform validation
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
from ui.app_themes import get_compliance_style
from ui.validation_dashboard import ValidationDashboard
from ui.splash_screen import RotorSplashScreen
from scenario import ScenarioController
from launcher_base import LauncherBase


class ComplianceWindow(LauncherBase):
    """RedByte Compliance Lab main window"""

    app_name = "compliance"

    def __init__(self):
        super().__init__()
        self.setWindowTitle("🟪 RedByte Compliance Lab - Standards & Scoring")
        self.resize(1200, 800)

        self.setStyleSheet(get_compliance_style())

        if self.session.import_context('diagnostics'):
            print("✅ Loaded session from Diagnostics")

        # Initialize backend dependencies
        self.scenario_ctrl = ScenarioController()

        self.create_panels()
        self.create_toolbar()
        self._setup_status_bar()
        self._apply_panel_tooltips()
        self._finish_init()

    def create_panels(self):
        """Create compliance panels"""
        self.dashboard = ValidationDashboard(self.scenario_ctrl)
        sub = self.mdi.addSubWindow(self.dashboard)
        sub.setWindowTitle("📋 Validation Scorecard")
        sub.show()
        self._register_subwindow(sub)

    def create_toolbar(self):
        """Create toolbar"""
        toolbar = QToolBar("Compliance")
        self.addToolBar(toolbar)

        act_run = QAction("▶️ Run Tests", self)
        toolbar.addAction(act_run)

        act_export = QAction("📄 Export Report", self)
        toolbar.addAction(act_export)

        self._add_context_actions(toolbar)


def main():
    args = LauncherBase.parse_args()
    app = QApplication(sys.argv)
    splash = RotorSplashScreen()
    splash.show()
    app.processEvents()

    window = ComplianceWindow()

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
