"""
Verify all 5 launcher windows instantiate without errors.
Each test creates the window class and checks that all expected
panels are created with the correct types.
"""
import sys
import os
import pytest

# Ensure src is on the path (conftest.py adds it, but be explicit)
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))


class TestLaunchCompliance:
    """Compliance Lab - simplest launcher (1 panel)"""

    def test_window_creates(self, qapp):
        from launchers.launch_compliance import ComplianceWindow
        window = ComplianceWindow()
        assert window is not None
        assert "Compliance" in window.windowTitle()
        window.close()

    def test_dashboard_panel_exists(self, qapp):
        from launchers.launch_compliance import ComplianceWindow
        from ui.validation_dashboard import ValidationDashboard
        window = ComplianceWindow()
        assert isinstance(window.dashboard, ValidationDashboard)
        window.close()


class TestLaunchSculptor:
    """Signal Sculptor - 2 panels requiring SerialManager"""

    def test_window_creates(self, qapp):
        from launchers.launch_sculptor import SculptorWindow
        window = SculptorWindow()
        assert window is not None
        assert "Sculptor" in window.windowTitle()
        window.close()

    def test_panels_exist(self, qapp):
        from launchers.launch_sculptor import SculptorWindow
        from ui.signal_sculptor import SignalSculptor
        from ui.inverter_scope import InverterScope
        window = SculptorWindow()
        assert isinstance(window.sculptor, SignalSculptor)
        assert isinstance(window.scope, InverterScope)
        window.close()


class TestLaunchReplay:
    """Replay Studio - 3 panels requiring SerialManager + Recorder"""

    def test_window_creates(self, qapp):
        from launchers.launch_replay import ReplayWindow
        window = ReplayWindow()
        assert window is not None
        assert "Replay" in window.windowTitle()
        window.close()

    def test_panels_exist(self, qapp):
        from launchers.launch_replay import ReplayWindow
        from ui.replay_studio import ReplayStudio
        from ui.phasor_view import PhasorView
        from ui.insights_panel import InsightsPanel
        window = ReplayWindow()
        assert isinstance(window.replay, ReplayStudio)
        assert isinstance(window.phasor, PhasorView)
        assert isinstance(window.insights, InsightsPanel)
        window.close()


class TestLaunchInsights:
    """Insight Studio - 1 panel, insight deserialization"""

    def test_window_creates(self, qapp):
        from launchers.launch_insights import InsightStudioWindow
        window = InsightStudioWindow()
        assert window is not None
        assert "Insight" in window.windowTitle()
        window.close()

    def test_panel_exists(self, qapp):
        from launchers.launch_insights import InsightStudioWindow
        from ui.insights_panel import InsightsPanel
        window = InsightStudioWindow()
        assert isinstance(window.insights, InsightsPanel)
        window.close()


class TestLaunchDiagnostics:
    """Diagnostics - most complex launcher (5 panels, 3 backends)"""

    def test_window_creates(self, qapp):
        from launchers.launch_diagnostics import DiagnosticsWindow
        window = DiagnosticsWindow()
        assert window is not None
        assert "Diagnostics" in window.windowTitle()
        window.close()

    def test_all_panels_exist(self, qapp):
        from launchers.launch_diagnostics import DiagnosticsWindow
        from ui.system_3d_view import System3DView
        from ui.inverter_scope import InverterScope
        from ui.phasor_view import PhasorView
        from ui.fault_injector import FaultInjector
        from ui.insights_panel import InsightsPanel
        window = DiagnosticsWindow()
        assert isinstance(window.view_3d, System3DView)
        assert isinstance(window.scope, InverterScope)
        assert isinstance(window.phasor, PhasorView)
        assert isinstance(window.injector, FaultInjector)
        assert isinstance(window.insights, InsightsPanel)
        window.close()

    def test_backends_initialized(self, qapp):
        from launchers.launch_diagnostics import DiagnosticsWindow
        from serial_reader import SerialManager
        from recorder import Recorder
        from scenario import ScenarioController
        window = DiagnosticsWindow()
        assert isinstance(window.serial_mgr, SerialManager)
        assert isinstance(window.recorder, Recorder)
        assert isinstance(window.scenario_ctrl, ScenarioController)
        window.close()


class TestLauncherBase:
    """Verify LauncherBase features are wired into all launchers"""

    def test_all_inherit_launcher_base(self, qapp):
        from launcher_base import LauncherBase
        from launchers.launch_diagnostics import DiagnosticsWindow
        from launchers.launch_replay import ReplayWindow
        from launchers.launch_compliance import ComplianceWindow
        from launchers.launch_insights import InsightStudioWindow
        from launchers.launch_sculptor import SculptorWindow

        for cls in [DiagnosticsWindow, ReplayWindow, ComplianceWindow,
                    InsightStudioWindow, SculptorWindow]:
            assert issubclass(cls, LauncherBase), f"{cls.__name__} should inherit LauncherBase"

    def test_geometry_persistence_attributes(self, qapp):
        from launchers.launch_compliance import ComplianceWindow
        window = ComplianceWindow()
        assert hasattr(window, 'saved_geometries')
        assert hasattr(window, 'user_moved_panels')
        assert isinstance(window.saved_geometries, dict)
        assert isinstance(window.user_moved_panels, set)
        window.close()

    def test_overlay_available(self, qapp):
        from launchers.launch_sculptor import SculptorWindow
        from ui.overlay import OverlayMessage
        window = SculptorWindow()
        assert hasattr(window, 'overlay')
        assert isinstance(window.overlay, OverlayMessage)
        window.close()

    def test_app_name_set(self, qapp):
        from launchers.launch_diagnostics import DiagnosticsWindow
        from launchers.launch_replay import ReplayWindow
        from launchers.launch_compliance import ComplianceWindow
        from launchers.launch_insights import InsightStudioWindow
        from launchers.launch_sculptor import SculptorWindow

        assert DiagnosticsWindow.app_name == "diagnostics"
        assert ReplayWindow.app_name == "replay"
        assert ComplianceWindow.app_name == "compliance"
        assert InsightStudioWindow.app_name == "insights"
        assert SculptorWindow.app_name == "sculptor"
