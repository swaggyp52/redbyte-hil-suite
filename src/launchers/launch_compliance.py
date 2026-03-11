"""
RedByte Compliance Lab - Automated test suites & validation scoring
Entry point for standards compliance and waveform validation
"""

import sys
import json
import webbrowser
from pathlib import Path

# Add parent and project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(Path(__file__).parent.parent))

from PyQt6.QtWidgets import (
    QApplication, QToolBar, QFileDialog, QMessageBox, QWidget,
    QVBoxLayout, QLabel, QHBoxLayout, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QColor, QBrush

from ui.app_themes import get_compliance_style
from ui.validation_dashboard import ValidationDashboard
from ui.splash_screen import RotorSplashScreen
from scenario import ScenarioController
from launcher_base import LauncherBase
from compliance_checker import evaluate_ieee_2800
from report_generator import generate_report


class ComplianceRunnerPanel(QWidget):
    """Self-contained widget: load session → run checks → show results → export."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._session_path: str | None = None
        self._compliance_results: list[dict] = []

        layout = QVBoxLayout(self)

        # Header
        hdr = QLabel("Compliance Lab — IEEE-Inspired Checks")
        hdr.setStyleSheet("font-size: 12pt; font-weight: 700; color: #a78bfa;")
        layout.addWidget(hdr)

        # Toolbar row
        btn_row = QHBoxLayout()

        self.btn_load = QPushButton("📂 Load Session…")
        self.btn_load.clicked.connect(self._load_session)
        btn_row.addWidget(self.btn_load)

        self.lbl_file = QLabel("No session loaded")
        self.lbl_file.setStyleSheet("color: #64748b; font-size: 9pt;")
        btn_row.addWidget(self.lbl_file)

        btn_row.addStretch()

        self.btn_run = QPushButton("▶  Run Tests")
        self.btn_run.setEnabled(False)
        self.btn_run.clicked.connect(self._run_checks)
        btn_row.addWidget(self.btn_run)

        self.btn_export = QPushButton("📄 Export Report")
        self.btn_export.setEnabled(False)
        self.btn_export.clicked.connect(self._export_report)
        btn_row.addWidget(self.btn_export)

        layout.addLayout(btn_row)

        # Results table
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Check", "Result", "Details"])
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet("""
            QTableWidget {
                background: rgba(15, 17, 21, 200);
                border: 1px solid rgba(31, 41, 55, 120);
                color: #e2e8f0;
                font-size: 9pt;
            }
            QHeaderView::section {
                background: rgba(30, 41, 59, 200);
                color: #94a3b8;
                font-weight: bold;
                border: none;
                padding: 6px;
            }
        """)
        layout.addWidget(self.table)

        # Summary
        self.lbl_summary = QLabel("")
        self.lbl_summary.setStyleSheet("font-size: 10pt; font-weight: 600; color: #94a3b8;")
        layout.addWidget(self.lbl_summary)

    # ------------------------------------------------------------------

    def load_from_path(self, path: str):
        """Load a session JSON directly (called programmatically)."""
        if not Path(path).exists():
            QMessageBox.critical(self, "File Error", f"Session file not found:\n{path}")
            return
        self._session_path = path
        self.lbl_file.setText(Path(path).name)
        self.btn_run.setEnabled(True)
        self.lbl_summary.setText(f"Session loaded: {Path(path).name}")

    def _load_session(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Session JSON", str(project_root / "data"),
            "JSON Files (*.json)"
        )
        if path:
            self.load_from_path(path)

    def _run_checks(self):
        if not self._session_path:
            return

        try:
            with open(self._session_path) as f:
                data = json.load(f)
        except Exception as e:
            QMessageBox.critical(self, "Load Error", str(e))
            return

        try:
            results = evaluate_ieee_2800(data)
        except Exception as e:
            QMessageBox.critical(self, "Check Error", str(e))
            return

        self._compliance_results = results
        self._populate_table(results)
        self.btn_export.setEnabled(True)

    def _populate_table(self, results: list[dict]):
        self.table.setRowCount(len(results))
        passes = 0
        for row, r in enumerate(results):
            passed = r.get("passed", False)
            if passed:
                passes += 1

            name_item = QTableWidgetItem(r.get("name", ""))
            result_item = QTableWidgetItem("PASS" if passed else "FAIL")
            detail_item = QTableWidgetItem(r.get("details", ""))

            color = QColor("#10b981") if passed else QColor("#ef4444")
            result_item.setForeground(QBrush(color))
            result_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            self.table.setItem(row, 0, name_item)
            self.table.setItem(row, 1, result_item)
            self.table.setItem(row, 2, detail_item)

        total = len(results)
        pct = int(100 * passes / total) if total else 0
        status_color = "#10b981" if passes == total else "#f59e0b" if passes > 0 else "#ef4444"
        self.lbl_summary.setStyleSheet(
            f"font-size: 10pt; font-weight: 600; color: {status_color};"
        )
        self.lbl_summary.setText(
            f"Results: {passes}/{total} checks PASSED ({pct}%)"
        )

    def _export_report(self):
        if not self._session_path:
            return
        try:
            report_path = generate_report(self._session_path)
            QMessageBox.information(
                self, "Report Saved",
                f"Report written to:\n{report_path}"
            )
            webbrowser.open_new_tab(Path(report_path).resolve().as_uri())
        except Exception as e:
            QMessageBox.critical(self, "Report Error", str(e))


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
        # Main compliance runner (file load + run + results + export)
        self.runner = ComplianceRunnerPanel()
        sub_runner = self.mdi.addSubWindow(self.runner)
        sub_runner.setWindowTitle("🔬 Compliance Suite")
        sub_runner.show()
        sub_runner.resize(900, 500)
        self._register_subwindow(sub_runner)

        # Validation Dashboard (scenario results)
        self.dashboard = ValidationDashboard(self.scenario_ctrl)
        sub_dash = self.mdi.addSubWindow(self.dashboard)
        sub_dash.setWindowTitle("📋 Validation Scorecard")
        sub_dash.show()
        self._register_subwindow(sub_dash)

    def create_toolbar(self):
        """Create toolbar"""
        toolbar = QToolBar("Compliance")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        act_load = QAction("📂 Load Session", self)
        act_load.triggered.connect(self._toolbar_load)
        toolbar.addAction(act_load)

        act_run = QAction("▶️ Run Tests", self)
        act_run.triggered.connect(lambda: self.runner._run_checks())
        toolbar.addAction(act_run)

        act_export = QAction("📄 Export Report", self)
        act_export.triggered.connect(lambda: self.runner._export_report())
        toolbar.addAction(act_export)

        self._add_context_actions(toolbar)

    def _toolbar_load(self):
        self.runner._load_session()


def main():
    args = LauncherBase.parse_args()
    app = QApplication(sys.argv)
    splash = RotorSplashScreen()
    splash.show()
    app.processEvents()

    window = ComplianceWindow()

    # Auto-load context if --load specified
    if args.load and Path(args.load).exists():
        window.runner.load_from_path(args.load)

    splash.finish(window)
    window.show()

    sys.exit(app.exec())


if __name__ == '__main__':
    main()
