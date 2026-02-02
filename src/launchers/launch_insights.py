"""
RedByte Insight Studio - AI cognitive insight layers & event clustering
Entry point for deep insight analysis and pattern recognition
"""

import sys
from pathlib import Path

# Add parent and project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(Path(__file__).parent.parent))

from PyQt6.QtWidgets import QApplication, QToolBar
from PyQt6.QtGui import QAction

from hil_core import SessionContext, InsightEngine
from hil_core.insights import Insight
from ui.app_themes import get_insights_style
from ui.insights_panel import InsightsPanel
from ui.splash_screen import RotorSplashScreen
from launcher_base import LauncherBase


class InsightStudioWindow(LauncherBase):
    """RedByte Insight Studio main window"""

    app_name = "insights"

    def __init__(self):
        super().__init__()
        self.setWindowTitle("🟨 RedByte Insight Studio - AI Cognitive Analysis")
        self.resize(1200, 800)

        self.setStyleSheet(get_insights_style())

        self.insight_engine = InsightEngine()

        # Import from diagnostics or replay
        if self.session.import_context('diagnostics') or self.session.import_context('replay'):
            print("✅ Loaded session insights")
            for insight_dict in self.session.insights:
                insight = Insight(
                    timestamp=insight_dict.get("timestamp", 0),
                    event_type=insight_dict.get("type", "unknown"),
                    severity=insight_dict.get("severity", "info"),
                    message=insight_dict.get("message", ""),
                    metrics=insight_dict.get("metrics", {}),
                    phase=insight_dict.get("phase")
                )
                self.insight_engine.add_insight(insight)

        self.create_panels()
        self.create_toolbar()
        self._setup_status_bar()
        self._apply_panel_tooltips()
        self._finish_init()

    def create_panels(self):
        """Create insight panels"""
        self.insights = InsightsPanel()
        sub = self.mdi.addSubWindow(self.insights)
        sub.setWindowTitle("🧠 Insight Clusters")
        sub.show()
        sub.setGeometry(0, 0, 1000, 700)
        self._register_subwindow(sub)

        # Load session insights
        for insight in self.session.insights:
            self.insights.add_insight(insight)

    def create_toolbar(self):
        """Create toolbar"""
        toolbar = QToolBar("Insights")
        self.addToolBar(toolbar)

        act_analyze = QAction("🔍 Analyze", self)
        toolbar.addAction(act_analyze)

        act_export = QAction("📊 Export CSV", self)
        toolbar.addAction(act_export)

        self._add_context_actions(toolbar)

    def _on_context_loaded(self):
        """Refresh insights panel after context import."""
        if self.session.insights:
            for insight_dict in self.session.insights:
                insight = Insight(
                    timestamp=insight_dict.get("timestamp", 0),
                    event_type=insight_dict.get("type", "unknown"),
                    severity=insight_dict.get("severity", "info"),
                    message=insight_dict.get("message", ""),
                    metrics=insight_dict.get("metrics", {}),
                    phase=insight_dict.get("phase")
                )
                self.insight_engine.add_insight(insight)
                self.insights.add_insight(insight_dict)


def main():
    args = LauncherBase.parse_args()
    app = QApplication(sys.argv)
    splash = RotorSplashScreen()
    splash.show()
    app.processEvents()

    window = InsightStudioWindow()

    # Auto-load context if specified
    if args.load:
        import shutil
        dest = window.session.temp_dir / "redbyte_session_imported.json"
        shutil.copy(args.load, str(dest))
        window.session.import_context("imported")
        window._on_context_loaded()

    splash.finish(window)
    window.show()

    sys.exit(app.exec())


if __name__ == '__main__':
    main()
