import os
import json
import time
import logging
import webbrowser
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QStackedWidget,
                             QPushButton, QLabel, QFileDialog, QFrame,
                             QScrollArea)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor

from ui.validation_dashboard import ValidationDashboard

logger = logging.getLogger(__name__)


class CompliancePage(QWidget):
    """
    Compliance surface — load a session, run IEEE tests, see scored results.

    States:
      no_session  — prompt to load
      loaded      — session ready, prompt to run
      results     — results visible with check cards + export
    """

    def __init__(self, scenario_ctrl, parent=None):
        super().__init__(parent)
        self._session_path = None
        self._session_data = None
        self._state = "no_session"
        self._build(scenario_ctrl)

    def _build(self, scenario_ctrl):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Top bar — always visible
        self._top_bar = _ComplianceTopBar()
        root.addWidget(self._top_bar)

        # Scorecard strip — hidden until results ready
        self._scorecard = _ScorecardStrip()
        self._scorecard.setVisible(False)
        root.addWidget(self._scorecard)

        # Stacked: no_session | loaded | results
        self._stack = QStackedWidget()
        root.addWidget(self._stack, stretch=1)

        # Page 0: no session prompt
        self._no_session = _NoSessionPrompt()
        self._no_session.load_clicked.connect(self._on_load)
        self._stack.addWidget(self._no_session)

        # Page 1: session loaded, ready to run
        self._ready = _ReadyToRun()
        self._ready.run_clicked.connect(self._on_run_tests)
        self._stack.addWidget(self._ready)

        # Page 2: results view
        results_widget = QWidget()
        results_layout = QVBoxLayout(results_widget)
        results_layout.setContentsMargins(0, 0, 0, 0)
        results_layout.setSpacing(0)

        self._check_cards = _CheckResultCards()
        results_layout.addWidget(self._check_cards)

        self.dashboard = ValidationDashboard(scenario_ctrl)
        results_layout.addWidget(self.dashboard, stretch=1)

        self._stack.addWidget(results_widget)

        self._stack.setCurrentIndex(0)

        # Bottom export bar — always visible
        bottom = _ExportBar()
        root.addWidget(bottom)

        # Wire
        self._top_bar.load_clicked.connect(self._on_load)
        self._top_bar.run_clicked.connect(self._on_run_tests)
        bottom.html_clicked.connect(self._on_export_html)
        bottom.csv_clicked.connect(self._on_export_csv)

    # ─────────────────────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────────────────────

    def load_session(self, path: str):
        """Load a session — can be called externally."""
        if not path or not os.path.exists(path):
            return
        try:
            with open(path) as f:
                self._session_data = json.load(f)
            self._session_path = path
            name = self._session_data.get("meta", {}).get("session_id", os.path.basename(path))
            frames = self._session_data.get("meta", {}).get("frame_count",
                         len(self._session_data.get("frames", [])))
            self._top_bar.set_session(name, frames)
            self._ready.set_session_name(name)
            self._scorecard.setVisible(False)
            self._stack.setCurrentIndex(1)
            self._state = "loaded"
        except Exception as exc:
            logger.error(f"Failed to load compliance session: {exc}")

    def load_from_capsule(self, capsule: dict, session=None) -> None:
        """
        Load an in-memory Data Capsule dict for compliance checking.

        Called by AppShell after a file import so the compliance page is
        pre-loaded without requiring a separate file-open step.

        Args:
            capsule: Data Capsule dict (from dataset_to_session()).
            session: Optional ActiveSession for richer metadata display.
        """
        self._session_data = capsule
        self._session_path = None  # no file path — data is in memory

        if session is not None:
            name = f"{session.source_type_display}  ·  {session.source_filename}"
            frames_str = session.row_count_display
        else:
            meta = capsule.get("meta", {})
            name = meta.get("session_id", "imported")
            frames_str = str(meta.get("frame_count", len(capsule.get("frames", []))))

        self._top_bar.set_session(name, int(frames_str.replace(",", "")) if frames_str.isdigit() else 0)
        self._ready.set_session_name(name)
        self._scorecard.setVisible(False)
        self._stack.setCurrentIndex(1)
        self._state = "loaded"
        logger.info("Compliance page pre-loaded from imported capsule: %s", name)

    # ─────────────────────────────────────────────────────────────
    # Internal
    # ─────────────────────────────────────────────────────────────

    def _on_load(self):
        fname, _ = QFileDialog.getOpenFileName(
            self, "Open Session for Compliance", "data/sessions", "JSON Files (*.json)"
        )
        if fname:
            self.load_session(fname)

    def _on_run_tests(self):
        if not self._session_data:
            return
        try:
            from src.compliance_checker import evaluate_ieee_2800
            results = evaluate_ieee_2800(self._session_data)
        except Exception as exc:
            logger.error(f"Compliance check failed: {exc}")
            return

        passed = sum(1 for r in results if r.get("passed"))
        total  = len(results)

        self._scorecard.update_score(passed, total)
        self._scorecard.setVisible(True)
        self._check_cards.set_results(results)
        self.dashboard.set_compliance(results)
        self.dashboard.add_entry({
            "ts":       time.time(),
            "scenario": "IEEE 2800 Compliance",
            "passed":   passed == total,
            "details":  f"{passed}/{total} checks passed",
            "compliance": results,
        })
        self._stack.setCurrentIndex(2)
        self._state = "results"

    def _on_export_html(self):
        if not self._session_path:
            return
        try:
            from src.report_generator import generate_report
            out_path = generate_report(self._session_path, output_dir="exports")
            if out_path and os.path.exists(str(out_path)):
                webbrowser.open_new_tab(f"file:///{os.path.abspath(str(out_path))}")
        except Exception as exc:
            logger.error(f"HTML report failed: {exc}")

    def _on_export_csv(self):
        if not self._session_path:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export CSV", "exports/compliance.csv", "CSV (*.csv)"
        )
        if path:
            try:
                from src.csv_exporter import CSVExporter
                CSVExporter().export_session(self._session_path, path, format_type="detailed")
            except Exception as exc:
                logger.error(f"CSV export failed: {exc}")


# ─────────────────────────────────────────────────────────────────
# Sub-widgets
# ─────────────────────────────────────────────────────────────────

class _NoSessionPrompt(QWidget):
    load_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setAlignment(Qt.AlignmentFlag.AlignCenter)

        card = QFrame()
        card.setObjectName("EmptyStateCard")
        card.setFixedWidth(400)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(32, 36, 32, 36)
        layout.setSpacing(12)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        icon = QLabel("✓")
        icon.setObjectName("EmptyIcon")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon)

        title = QLabel("Compliance Lab")
        title.setObjectName("EmptyTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        desc = QLabel(
            "Load a recorded session to evaluate it against\n"
            "IEEE 2800-inspired grid-forming inverter compliance checks."
        )
        desc.setObjectName("EmptyDesc")
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc.setWordWrap(True)
        layout.addWidget(desc)

        layout.addSpacing(8)
        btn = QPushButton("Load Session")
        btn.setObjectName("EmptyAction")
        btn.clicked.connect(self.load_clicked)
        layout.addWidget(btn, alignment=Qt.AlignmentFlag.AlignCenter)

        outer.addWidget(card)


class _ReadyToRun(QWidget):
    run_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setAlignment(Qt.AlignmentFlag.AlignCenter)

        card = QFrame()
        card.setObjectName("ReadyCard")
        card.setFixedWidth(440)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(12)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        icon = QLabel("📋")
        icon.setObjectName("EmptyIcon")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon)

        self._title = QLabel("Session Loaded")
        self._title.setObjectName("EmptyTitle")
        self._title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._title)

        checks_label = QLabel("Will evaluate:")
        checks_label.setObjectName("ReadySubhead")
        checks_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(checks_label)

        checks = [
            "Ride-through 50% voltage sag ≥ 200ms",
            "Frequency within ±0.5 Hz under load",
            "Voltage recovery after sag clearance",
        ]
        for c in checks:
            row = QLabel(f"  ·  {c}")
            row.setObjectName("CheckPreviewItem")
            row.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(row)

        layout.addSpacing(8)
        btn = QPushButton("Run IEEE Tests")
        btn.setObjectName("RunTestsBtn")
        btn.clicked.connect(self.run_clicked)
        layout.addWidget(btn, alignment=Qt.AlignmentFlag.AlignCenter)

        outer.addWidget(card)

    def set_session_name(self, name: str):
        self._title.setText(f"Ready  —  {name}")


class _CheckResultCards(QWidget):
    """Inline pass/fail cards for each compliance check — shown after run."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("CheckResultCards")
        self.setFixedHeight(88)
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(16, 8, 16, 8)
        self._layout.setSpacing(12)

    def set_results(self, results: list[dict]):
        # Clear existing cards
        while self._layout.count():
            item = self._layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for r in results:
            card = self._make_card(r)
            self._layout.addWidget(card)
        self._layout.addStretch()

    def _make_card(self, result: dict) -> QFrame:
        passed = result.get("passed", False)
        name   = result.get("name", "Check")
        detail = result.get("details", "")

        card = QFrame()
        card.setObjectName("CheckCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(4)

        mark = QLabel("✓ PASS" if passed else "✗ FAIL")
        mark.setObjectName("CheckMark")
        if passed:
            mark.setStyleSheet("color: #10b981; font-weight: 700; font-size: 10pt;")
        else:
            mark.setStyleSheet("color: #ef4444; font-weight: 700; font-size: 10pt;")
        layout.addWidget(mark)

        lbl = QLabel(name)
        lbl.setObjectName("CheckName")
        lbl.setWordWrap(True)
        layout.addWidget(lbl)

        if detail:
            det = QLabel(detail)
            det.setObjectName("CheckDetail")
            det.setWordWrap(True)
            layout.addWidget(det)

        border_color = "#10b981" if passed else "#ef4444"
        card.setStyleSheet(
            f"#CheckCard {{ border: 1px solid {border_color}; border-radius: 8px;"
            f" background: rgba(15,17,21,200); }}"
        )
        return card


class _ScorecardStrip(QFrame):
    """Prominent pass/fail summary bar — shown after tests run."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ScorecardStrip")
        self.setFixedHeight(52)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(24, 0, 24, 0)
        layout.setSpacing(16)

        self._icon = QLabel("—")
        self._icon.setObjectName("ScorecardIcon")
        layout.addWidget(self._icon)

        self._lbl = QLabel("Run tests to see results")
        self._lbl.setObjectName("ScorecardLabel")
        layout.addWidget(self._lbl)
        layout.addStretch()

        self._pct = QLabel("")
        self._pct.setObjectName("ScorecardPct")
        layout.addWidget(self._pct)

    def update_score(self, passed: int, total: int):
        pct = int(100 * passed / total) if total else 0
        if passed == total:
            color, icon = "#10b981", "✓"
            msg = f"All {total} checks passed"
        elif passed == 0:
            color, icon = "#ef4444", "✗"
            msg = f"0 of {total} checks passed"
        else:
            color, icon = "#f59e0b", "⚠"
            msg = f"{passed} of {total} checks passed"

        self._icon.setText(icon)
        self._icon.setStyleSheet(f"color: {color}; font-size: 16pt; font-weight: 700;")
        self._lbl.setText(msg)
        self._lbl.setStyleSheet(f"color: {color}; font-weight: 700; font-size: 11pt;")
        self._pct.setText(f"{pct}%")
        self._pct.setStyleSheet(
            f"color: {color}; font-size: 14pt; font-weight: 700; opacity: 0.7;"
        )
        self.setStyleSheet(
            f"#ScorecardStrip {{ border-bottom: 2px solid {color};"
            f" background: rgba(15,17,21,200); }}"
        )


class _ComplianceTopBar(QWidget):
    load_clicked = pyqtSignal()
    run_clicked  = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("PageTopBar")
        self.setFixedHeight(52)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(8)

        self._lbl = QLabel("Compliance Lab  —  IEEE 2800 validation")
        self._lbl.setObjectName("PageTitle")
        layout.addWidget(self._lbl)
        layout.addStretch()

        btn_load = QPushButton("Load Session")
        btn_load.clicked.connect(self.load_clicked)
        btn_run = QPushButton("Run IEEE Tests")
        btn_run.setObjectName("RunTestsBtn")
        btn_run.clicked.connect(self.run_clicked)

        layout.addWidget(btn_load)
        layout.addWidget(btn_run)

    def set_session(self, name: str, frames: int):
        self._lbl.setText(f"Compliance  ·  {name}  ({frames:,} frames)")


class _ExportBar(QWidget):
    html_clicked = pyqtSignal()
    csv_clicked  = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ExportBar")
        self.setFixedHeight(48)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(8)
        layout.addStretch()

        btn_html = QPushButton("Export HTML Report")
        btn_html.setObjectName("ExportBtn")
        btn_html.clicked.connect(self.html_clicked)
        btn_csv = QPushButton("Export CSV")
        btn_csv.clicked.connect(self.csv_clicked)

        layout.addWidget(btn_html)
        layout.addWidget(btn_csv)
