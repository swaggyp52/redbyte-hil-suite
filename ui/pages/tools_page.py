"""
Tools page — demo-preparation utilities for the VSM Evidence Workbench.

Provides a self-contained set of helpers for running pre-presentation checks,
opening output folders, resetting session state, and inspecting version info.
Not part of the primary analysis workflow.
"""

import subprocess
import sys
import threading
from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog, QFrame, QHBoxLayout, QLabel,
    QPushButton, QScrollArea, QTextEdit, QVBoxLayout, QWidget,
)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

_DEMO_CHECKLIST = [
    "1. Run smoke test — all 31 checks should PASS",
    "2. Open the app via run.bat",
    "3. Import RigolDS0.csv — apply 3-phase mapping",
    "4. Navigate to Replay → Metrics tab",
    "5. Navigate to Compliance tab",
    "6. Import DS1 as second session and compare",
    "7. Export evidence package",
    "8. Import InverterPower.xlsx — confirm generic mode",
    "9. Close app and confirm exports in artifacts/evidence_exports/",
]


class ToolsPage(QWidget):
    """Demo preparation utilities."""

    reset_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(32, 32, 32, 32)
        root.setSpacing(20)

        header = QLabel("Tools  —  Demo Preparation")
        header.setObjectName("PageHeader")
        root.addWidget(header)

        subtitle = QLabel(
            "Pre-presentation checks, output folder access, and session reset."
        )
        subtitle.setObjectName("OverviewSubtitle")
        root.addWidget(subtitle)

        # ── Action row ──────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)

        self._btn_smoke = QPushButton("▶  Run Smoke Test")
        self._btn_smoke.setObjectName("SimBtnRun")
        self._btn_smoke.clicked.connect(self._run_smoke_test)
        btn_row.addWidget(self._btn_smoke)

        btn_exports = QPushButton("📁  Open Evidence Exports")
        btn_exports.clicked.connect(self._open_exports)
        btn_row.addWidget(btn_exports)

        btn_screenshots = QPushButton("🖼  Open Screenshots")
        btn_screenshots.clicked.connect(self._open_screenshots)
        btn_row.addWidget(btn_screenshots)

        btn_reset = QPushButton("↺  Reset Session")
        btn_reset.clicked.connect(self.reset_requested)
        btn_row.addWidget(btn_reset)

        btn_version = QPushButton("ℹ  Version Info")
        btn_version.clicked.connect(self._show_version)
        btn_row.addWidget(btn_version)

        btn_row.addStretch()
        root.addLayout(btn_row)

        # ── Separator ───────────────────────────────────────────────
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setObjectName("SidebarSep")
        root.addWidget(sep)

        # ── Demo checklist ──────────────────────────────────────────
        checklist_lbl = QLabel("Demo Checklist")
        checklist_lbl.setObjectName("SectionLabel")
        root.addWidget(checklist_lbl)

        for step in _DEMO_CHECKLIST:
            lbl = QLabel(step)
            lbl.setObjectName("ChecklistItem")
            lbl.setStyleSheet("color: #94a3b8; font-size: 13px; padding: 2px 0;")
            root.addWidget(lbl)

        root.addStretch()

    # ── Smoke test runner ────────────────────────────────────────────

    def _run_smoke_test(self):
        script = _PROJECT_ROOT / "scripts" / "final_demo_smoke.py"
        dlg = _OutputDialog(f"Smoke Test — {script.name}", self)
        dlg.show()

        def _worker():
            try:
                proc = subprocess.run(
                    [sys.executable, str(script)],
                    capture_output=True,
                    text=True,
                    cwd=str(_PROJECT_ROOT),
                    timeout=120,
                )
                output = proc.stdout
                if proc.stderr:
                    output += "\n--- stderr ---\n" + proc.stderr
                if proc.returncode != 0:
                    output += f"\n[Exit code {proc.returncode}]"
            except Exception as exc:
                output = f"Failed to run smoke test:\n{exc}"
            dlg._output_ready.emit(output)

        threading.Thread(target=_worker, daemon=True).start()

    # ── Folder openers ───────────────────────────────────────────────

    def _open_exports(self):
        import os
        folder = _PROJECT_ROOT / "artifacts" / "evidence_exports"
        folder.mkdir(parents=True, exist_ok=True)
        try:
            os.startfile(str(folder))
        except Exception:
            pass

    def _open_screenshots(self):
        import os
        folder = _PROJECT_ROOT / "artifacts" / "final_screenshots"
        folder.mkdir(parents=True, exist_ok=True)
        try:
            os.startfile(str(folder))
        except Exception:
            pass

    # ── Version info ─────────────────────────────────────────────────

    def _show_version(self):
        from PyQt6.QtWidgets import QMessageBox
        try:
            result = subprocess.run(
                ["git", "log", "-1", "--oneline"],
                capture_output=True, text=True,
                cwd=str(_PROJECT_ROOT), timeout=5,
            )
            git_line = result.stdout.strip() or "(no git history)"
        except Exception:
            git_line = "(git not available)"

        py_ver = sys.version.split()[0]
        QMessageBox.information(
            self, "Version Info",
            f"Python: {py_ver}\n"
            f"Last commit: {git_line}\n"
            f"Project root: {_PROJECT_ROOT}",
        )


class _OutputDialog(QDialog):
    """Non-blocking output window for long-running subprocess output."""

    _output_ready = pyqtSignal(str)

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(700, 480)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        self._text = QTextEdit()
        self._text.setReadOnly(True)
        self._text.setObjectName("OutputLog")
        self._text.setStyleSheet(
            "font-family: 'JetBrains Mono', Consolas, monospace; font-size: 12px;"
        )
        self._text.setPlainText("Running…")
        layout.addWidget(self._text)

        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close, alignment=Qt.AlignmentFlag.AlignRight)

        self._output_ready.connect(self._on_output)

    def _on_output(self, text: str):
        self._text.setPlainText(text)
        # Scroll to bottom
        sb = self._text.verticalScrollBar()
        sb.setValue(sb.maximum())
