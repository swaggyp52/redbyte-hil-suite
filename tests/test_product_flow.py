"""
Product flow smoke tests — product takeover pass.

Covers the three new wiring changes:
  1. SessionBar.set_analysis_mode() — badge + button state
  2. CompliancePage.load_from_capsule() — state transitions
  3. Sidebar nav label renamed Console → Monitor
"""
import sys
import os
import time

import pytest

# Ensure src on path (conftest already does this but be explicit for clarity)
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QObject, pyqtSignal


def _get_app():
    app = QApplication.instance()
    if not app:
        app = QApplication([])
    return app


# ─────────────────────────────────────────────────────────────────
# SessionBar — analysis mode
# ─────────────────────────────────────────────────────────────────

class TestSessionBarAnalysisMode:
    def test_analysis_mode_on_sets_badge(self, qapp):
        from ui.session_bar import SessionBar
        bar = SessionBar()
        bar.set_analysis_mode(True)
        assert bar.lbl_mode.text() == "ANALYSIS"

    def test_analysis_mode_on_disables_controls(self, qapp):
        from ui.session_bar import SessionBar
        bar = SessionBar()
        bar.set_analysis_mode(True)
        assert not bar.btn_run.isEnabled()
        assert not bar.btn_pause.isEnabled()
        assert not bar.btn_stop.isEnabled()

    def test_analysis_mode_off_restores_ready(self, qapp):
        from ui.session_bar import SessionBar
        bar = SessionBar()
        bar.set_analysis_mode(True)
        bar.set_analysis_mode(False)
        assert bar.lbl_mode.text() == "READY"

    def test_analysis_mode_off_re_enables_run(self, qapp):
        from ui.session_bar import SessionBar
        bar = SessionBar()
        bar.set_analysis_mode(True)
        bar.set_analysis_mode(False)
        # Run should be re-enabled; pause/stop remain disabled (no sim active)
        assert bar.btn_run.isEnabled()
        assert not bar.btn_pause.isEnabled()
        assert not bar.btn_stop.isEnabled()

    def test_update_sim_state_overrides_analysis_mode(self, qapp):
        """When sim starts, state change signal updates buttons even after analysis mode."""
        from ui.session_bar import SessionBar
        bar = SessionBar()
        bar.set_analysis_mode(True)
        bar.update_sim_state("running")
        # Should follow sim state, not stay in analysis lock
        assert not bar.btn_run.isEnabled()
        assert bar.btn_pause.isEnabled()
        assert bar.btn_stop.isEnabled()


# ─────────────────────────────────────────────────────────────────
# CompliancePage — load_from_capsule
# ─────────────────────────────────────────────────────────────────

def _minimal_capsule(n_frames: int = 10) -> dict:
    base_ts = time.time()
    frames = [
        {
            "ts":   base_ts + i * 0.02,
            "v_an": 120.0,
            "freq": 60.0,
        }
        for i in range(n_frames)
    ]
    return {
        "meta": {
            "session_id": "test_capsule",
            "frame_count": n_frames,
            "sample_rate_estimate": 50,
        },
        "frames": frames,
        "insights": [],
    }


class FakeScenarioCtrl(QObject):
    """Minimal stand-in so CompliancePage can construct without a real ScenarioController."""
    pass


class TestComplianceLoadFromCapsule:
    def _make_page(self, qapp):
        from ui.pages.compliance_page import CompliancePage
        ctrl = FakeScenarioCtrl()
        page = CompliancePage(ctrl)
        return page

    def test_initial_state_is_no_session(self, qapp):
        page = self._make_page(qapp)
        assert page._state == "no_session"

    def test_load_from_capsule_no_session_transitions_to_loaded(self, qapp):
        page = self._make_page(qapp)
        capsule = _minimal_capsule()
        page.load_from_capsule(capsule)
        assert page._state == "loaded"

    def test_load_from_capsule_stores_data(self, qapp):
        page = self._make_page(qapp)
        capsule = _minimal_capsule()
        page.load_from_capsule(capsule)
        assert page._session_data is capsule

    def test_load_from_capsule_sets_no_path(self, qapp):
        """In-memory load must not set a file path."""
        page = self._make_page(qapp)
        page.load_from_capsule(_minimal_capsule())
        assert page._session_path is None

    def test_load_from_capsule_with_session_uses_display_name(self, qapp):
        from src.session_state import ActiveSession
        from ui.pages.compliance_page import CompliancePage

        capsule = _minimal_capsule()
        session = ActiveSession.from_capsule(capsule, label="RigolDS0.csv")

        ctrl = FakeScenarioCtrl()
        page = CompliancePage(ctrl)
        page.load_from_capsule(capsule, session)

        assert page._state == "loaded"
        # Top bar label should reference the source filename
        assert "RigolDS0.csv" in page._top_bar._lbl.text()

    def test_load_from_capsule_switches_stack_to_loaded_index(self, qapp):
        page = self._make_page(qapp)
        page.load_from_capsule(_minimal_capsule())
        # Index 1 = _ReadyToRun page
        assert page._stack.currentIndex() == 1

    def test_load_from_capsule_hides_scorecard(self, qapp):
        page = self._make_page(qapp)
        page.load_from_capsule(_minimal_capsule())
        assert not page._scorecard.isVisible()


# ─────────────────────────────────────────────────────────────────
# Sidebar — Console → Monitor rename
# ─────────────────────────────────────────────────────────────────

class TestSidebarLabels:
    def test_monitor_label_present(self, qapp):
        from ui.sidebar import Sidebar
        sb = Sidebar()
        # "console" key should show "Monitor" text, not "Console"
        btn = sb._buttons.get("console")
        assert btn is not None
        assert "Monitor" in btn.text()

    def test_console_label_absent(self, qapp):
        from ui.sidebar import Sidebar
        sb = Sidebar()
        btn = sb._buttons.get("console")
        assert "Console" not in btn.text()

    def test_all_expected_nav_keys_present(self, qapp):
        from ui.sidebar import Sidebar
        sb = Sidebar()
        for key in ("overview", "diagnostics", "replay", "compliance", "console", "tools"):
            assert key in sb._buttons, f"Missing nav key: {key}"
