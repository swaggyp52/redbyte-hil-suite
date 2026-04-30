import os
import json
import time
import logging
import webbrowser
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QStackedWidget,
                             QPushButton, QLabel, QFileDialog, QFrame,
                             QScrollArea, QComboBox)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor

from ui.validation_dashboard import ValidationDashboard

logger = logging.getLogger(__name__)

_PROFILE_DESCRIPTIONS = {
    "project_demo": "Project demo: project-specific voltage, frequency, and THD checks.",
    "ieee_2800_inspired": "IEEE 2800-inspired: inverter and grid behavior checks for recorded events.",
    "ieee_519_thd": "IEEE 519-inspired: harmonic distortion and THD reference checks.",
}


def _serializable_capsule(capsule: dict) -> dict:
    return {
        "meta": dict(capsule.get("meta", {})),
        "import_meta": dict(capsule.get("import_meta", {})),
        "events": list(capsule.get("events", [])),
        "frames": [dict(frame) for frame in capsule.get("frames", [])],
    }


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
        self._active_profile = "ieee_2800_inspired"
        self._state = "no_session"
        self._last_results: list = []
        self._last_events:  list = []
        self._last_annotations: dict = {}
        self._build(scenario_ctrl)
        self._ready.set_profile(self._active_profile)
        self._top_bar.set_profile_description(_PROFILE_DESCRIPTIONS[self._active_profile])

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
        self._top_bar.profile_changed.connect(self._on_profile_changed)
        bottom.html_clicked.connect(self._on_export_html)
        bottom.csv_clicked.connect(self._on_export_csv)
        bottom.events_clicked.connect(self._on_export_events_csv)
        bottom.bundle_clicked.connect(self._on_export_evidence_package)

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

    def set_events(self, events: list, annotations: dict | None = None) -> None:
        """
        Receive the latest detected events from the replay studio.

        Called by AppShell after event detection completes so the compliance
        page has full context for its HTML report export.
        """
        self._last_events = list(events)
        self._last_annotations = dict(annotations or {})

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
            from src.compliance_checker import evaluate_session
            results = evaluate_session(self._session_data, profile=self._active_profile)
        except Exception as exc:
            logger.error(f"Compliance check failed: {exc}")
            return

        passed = sum(1 for r in results if r.get("status") == "PASS")
        total  = sum(1 for r in results if r.get("status") in {"PASS", "FAIL"})

        self._scorecard.update_score(passed, total)
        self._scorecard.setVisible(True)
        self._check_cards.set_results(results)
        self._last_results = results
        self.dashboard.set_compliance(results)
        self.dashboard.add_entry({
            "ts":       time.time(),
            "scenario": f"{self._active_profile} checks",
            "passed":   total > 0 and passed == total,
            "details":  f"{passed}/{total} PASS/FAIL checks passed",
            "compliance": results,
        })
        self._stack.setCurrentIndex(2)
        self._state = "results"

    def _on_profile_changed(self, profile_id: str) -> None:
        self._active_profile = profile_id
        self._ready.set_profile(profile_id)
        self._top_bar.set_profile_description(_PROFILE_DESCRIPTIONS.get(profile_id, ""))

    def _on_export_html(self):
        if not self._session_data:
            return
        try:
            from src.session_exporter import generate_html_report
            compliance = self._last_results if self._last_results else None
            out_path = generate_html_report(
                self._session_data,
                self._last_events or None,
                compliance,
                output_dir="exports",
            )
            if out_path and os.path.exists(str(out_path)):
                webbrowser.open_new_tab(f"file:///{os.path.abspath(str(out_path))}")
        except Exception as exc:
            logger.error(f"HTML report failed: {exc}")

    def _on_export_csv(self):
        if not self._session_data:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Session CSV", "exports/compliance_session.csv", "CSV (*.csv)"
        )
        if path:
            try:
                from src.session_exporter import export_session_csv
                export_session_csv(self._session_data, path)
            except Exception as exc:
                logger.error(f"CSV export failed: {exc}")

    def _on_export_events_csv(self):
        if not self._last_events:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Events CSV", "exports/compliance_events.csv", "CSV (*.csv)"
        )
        if path:
            try:
                from src.session_exporter import export_events_csv
                export_events_csv(self._last_events, self._last_annotations, path)
            except Exception as exc:
                logger.error(f"Events CSV export failed: {exc}")

    def _on_export_evidence_package(self):
        if not self._session_data:
            return
        folder = QFileDialog.getExistingDirectory(
            self, "Select Evidence Export Folder", "exports"
        )
        if not folder:
            return
        try:
            from src.report_generator import generate_evidence_package
            from src.session_analysis import compute_session_metrics
            temp_path = self._session_path
            if temp_path is None:
                import tempfile
                fd, temp_path = tempfile.mkstemp(suffix=".json", prefix="evidence_session_")
                os.close(fd)
                with open(temp_path, "w", encoding="utf-8") as fh:
                    json.dump(_serializable_capsule(self._session_data), fh, indent=2)

            generate_evidence_package(
                session_path=temp_path,
                output_dir=folder,
                profile=self._active_profile,
                compliance_results=self._last_results or None,
                events=self._last_events or None,
                metrics=compute_session_metrics(self._session_data, events=self._last_events or None),
                session_data=self._session_data,
            )
        except Exception as exc:
            logger.error(f"Evidence package export failed: {exc}")


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

        title = QLabel("Standards-Inspired Validation")
        title.setObjectName("EmptyTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        desc = QLabel(
            "Load a recorded session to evaluate real measured values against\n"
            "IEEE-inspired ride-through, THD, frequency, and evidence checks."
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

        self._checks = []
        for c in [
            "Voltage regulation and phase RMS",
            "THD against IEEE 519-style 5% reference",
            "Frequency deviation, recovery, and honest N/A handling",
        ]:
            row = QLabel(f"  ·  {c}")
            row.setObjectName("CheckPreviewItem")
            row.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(row)
            self._checks.append(row)

        layout.addSpacing(8)
        btn = QPushButton("Run Engineering Checks")
        btn.setObjectName("RunTestsBtn")
        btn.clicked.connect(self.run_clicked)
        layout.addWidget(btn, alignment=Qt.AlignmentFlag.AlignCenter)

        outer.addWidget(card)

    def set_session_name(self, name: str):
        self._title.setText(f"Ready  —  {name}")

    def set_profile(self, profile_id: str):
        pretty = profile_id.replace("_", " ")
        if self._checks:
            self._checks[0].setText(f"  ·  Profile: {pretty}")
            self._checks[1].setText(
                f"  ·  {_PROFILE_DESCRIPTIONS.get(profile_id, 'Standards-inspired engineering checks')}"
            )


class _CheckResultCards(QWidget):
    """Inline pass/fail cards for each compliance check — shown after run."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("CheckResultCards")
        self.setFixedHeight(96)
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(16, 10, 16, 10)
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

        status_text = result.get("status") or ("PASS" if passed else "FAIL")
        mark = QLabel(
            "✓ PASS" if status_text == "PASS"
            else "✗ FAIL" if status_text == "FAIL"
            else "• N/A"
        )
        mark.setObjectName("CheckMark")
        if status_text == "PASS":
            mark.setStyleSheet("color: #10b981; font-weight: 700; font-size: 10pt;")
        elif status_text == "FAIL":
            mark.setStyleSheet("color: #ef4444; font-weight: 700; font-size: 10pt;")
        else:
            mark.setStyleSheet("color: #f59e0b; font-weight: 700; font-size: 10pt;")
        layout.addWidget(mark)

        lbl = QLabel(name)
        lbl.setObjectName("CheckName")
        lbl.setWordWrap(True)
        layout.addWidget(lbl)

        measured = result.get("measured")
        threshold = result.get("threshold")
        det_text = detail
        if measured is not None or threshold is not None:
            det_text = f"Measured: {measured}  ·  Threshold: {threshold}"
        if det_text:
            det = QLabel(det_text)
            det.setObjectName("CheckDetail")
            det.setWordWrap(True)
            layout.addWidget(det)

        border_color = "#10b981" if status_text == "PASS" else "#ef4444" if status_text == "FAIL" else "#f59e0b"
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
    profile_changed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("PageTopBar")
        self.setFixedHeight(52)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(8)

        self._lbl = QLabel("Compliance  ·  Standards-Inspired Validation")
        self._lbl.setObjectName("PageTitle")
        layout.addWidget(self._lbl)
        layout.addStretch()

        self._profile = QComboBox()
        self._profile.addItems(["ieee_2800_inspired", "ieee_519_thd", "project_demo"])
        self._profile.setCurrentText("ieee_2800_inspired")
        self._profile.currentTextChanged.connect(self.profile_changed)

        btn_load = QPushButton("Load Session")
        btn_load.clicked.connect(self.load_clicked)
        btn_run = QPushButton("Run Checks")
        btn_run.setObjectName("RunTestsBtn")
        btn_run.clicked.connect(self.run_clicked)

        layout.addWidget(self._profile)
        layout.addWidget(btn_load)
        layout.addWidget(btn_run)
        self._desc = QLabel("")
        self._desc.setStyleSheet("color:#94a3b8; font-size:9pt; padding-left:12px;")
        layout.addWidget(self._desc)

    def set_session(self, name: str, frames: int):
        self._lbl.setText(f"Compliance  ·  {name}  ({frames:,} frames)")

    def set_profile_description(self, text: str) -> None:
        self._desc.setText(text)


class _ExportBar(QWidget):
    html_clicked   = pyqtSignal()
    csv_clicked    = pyqtSignal()
    events_clicked = pyqtSignal()
    bundle_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ExportBar")
        self.setFixedHeight(48)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(8)
        layout.addStretch()

        btn_bundle = QPushButton("Evidence Package")
        btn_bundle.setObjectName("ExportBtn")
        btn_bundle.clicked.connect(self.bundle_clicked)
        btn_html = QPushButton("Export Report")
        btn_html.setObjectName("ExportBtn")
        btn_html.clicked.connect(self.html_clicked)
        btn_csv = QPushButton("Session CSV")
        btn_csv.clicked.connect(self.csv_clicked)
        btn_events = QPushButton("Events CSV")
        btn_events.clicked.connect(self.events_clicked)

        layout.addWidget(btn_bundle)
        layout.addWidget(btn_html)
        layout.addWidget(btn_csv)
        layout.addWidget(btn_events)
