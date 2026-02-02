"""
RedByte Diagnostics - Live signal capture + fault injection
Entry point for diagnostic operations and real-time monitoring
"""

import sys
from pathlib import Path

# Add parent and project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(Path(__file__).parent.parent))

from PyQt6.QtWidgets import QApplication, QToolBar, QMenu
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QAction, QIcon

# Import core modules
from hil_core import SessionContext, SignalEngine, FaultEngine, InsightEngine
from ui.app_themes import get_diagnostics_style, APP_ACCENTS
from ui.inverter_scope import InverterScope
from ui.phasor_view import PhasorView
from ui.fault_injector import FaultInjector
from ui.system_3d_view import System3DView
from ui.insights_panel import InsightsPanel
from ui.splash_screen import RotorSplashScreen

# Import backend dependencies
from serial_reader import SerialManager
from recorder import Recorder
from scenario import ScenarioController
from launcher_base import LauncherBase


class DiagnosticsWindow(LauncherBase):
    """RedByte Diagnostics main window"""

    app_name = "diagnostics"

    def __init__(self):
        super().__init__()
        self.setWindowTitle("🟩 RedByte Diagnostics - Live Ops & Fault Injection")
        self.resize(1400, 900)

        # Apply diagnostics theme
        self.setStyleSheet(get_diagnostics_style())

        # Initialize core engines (hil_core layer)
        self.session.source_app = 'diagnostics'
        self.signal_engine = SignalEngine()
        self.fault_engine = FaultEngine()
        self.insight_engine = InsightEngine()

        # Initialize backend dependencies (src layer)
        self.serial_mgr = SerialManager()
        self.recorder = Recorder()
        self.scenario_ctrl = ScenarioController()

        # Wire signals
        self.serial_mgr.frame_received.connect(self.recorder.log_frame)
        self.serial_mgr.frame_received.connect(self._on_frame)
        self.scenario_ctrl.event_triggered.connect(self._on_scenario_event)

        # Create diagnostic panels
        self.create_panels()
        self.create_toolbar()
        self.create_menu()

        # Apply default layout
        self.apply_diagnostics_layout()
        self._setup_status_bar(self.serial_mgr)
        self._apply_panel_tooltips()
        self._finish_init()

    def create_panels(self):
        """Create diagnostic-focused panels"""
        # 3D System View - primary situational awareness
        self.view_3d = System3DView(self.serial_mgr, self.scenario_ctrl)
        sub_3d = self.mdi.addSubWindow(self.view_3d)
        sub_3d.setWindowTitle("⚙️ 3D System")
        sub_3d.show()
        self._register_subwindow(sub_3d)

        # Inverter Scope - live waveforms
        self.scope = InverterScope(self.serial_mgr)
        sub_scope = self.mdi.addSubWindow(self.scope)
        sub_scope.setWindowTitle("📊 Scope")
        sub_scope.show()
        self._register_subwindow(sub_scope)

        # Phasor View - phase relationships
        self.phasor = PhasorView(self.serial_mgr)
        sub_phasor = self.mdi.addSubWindow(self.phasor)
        sub_phasor.setWindowTitle("🌈 Phasor")
        sub_phasor.show()
        self._register_subwindow(sub_phasor)

        # Fault Injector - control interface
        self.injector = FaultInjector(self.scenario_ctrl, self.serial_mgr)
        sub_injector = self.mdi.addSubWindow(self.injector)
        sub_injector.setWindowTitle("💉 Fault Injector")
        sub_injector.show()
        self._register_subwindow(sub_injector)

        # Insights Panel - compact mode for live monitoring
        self.insights = InsightsPanel()
        sub_insights = self.mdi.addSubWindow(self.insights)
        sub_insights.setWindowTitle("💡 Insights")
        sub_insights.show()
        self._register_subwindow(sub_insights)

    def create_toolbar(self):
        """Create diagnostic toolbar"""
        toolbar = QToolBar("Diagnostics")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        # Start/Stop monitoring
        act_start = QAction("▶️ Start", self)
        act_start.triggered.connect(self.start_monitoring)
        toolbar.addAction(act_start)

        act_stop = QAction("⏸️ Pause", self)
        act_stop.triggered.connect(self.stop_monitoring)
        toolbar.addAction(act_stop)

        toolbar.addSeparator()

        # Export to other apps
        act_replay = QAction("🔵 Open in Replay Studio", self)
        act_replay.triggered.connect(self.export_to_replay)
        toolbar.addAction(act_replay)

        act_compliance = QAction("🟪 Send to Compliance Lab", self)
        act_compliance.triggered.connect(self.export_to_compliance)
        toolbar.addAction(act_compliance)

        toolbar.addSeparator()

        # Snapshot
        act_snapshot = QAction("📸 Capture", self)
        act_snapshot.triggered.connect(self.capture_snapshot)
        toolbar.addAction(act_snapshot)

        self._add_context_actions(toolbar)

    def create_menu(self):
        """Create menu bar"""
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("File")
        file_menu.addAction("Open Session...", self.load_session)
        file_menu.addAction("Save Session...", self.save_session)
        file_menu.addSeparator()
        file_menu.addAction("Exit", self.close)

        # View menu
        view_menu = menubar.addMenu("View")
        view_menu.addAction("Reset Layout", self.apply_diagnostics_layout)
        view_menu.addAction("Full Screen", self.toggle_fullscreen)

        # Tools menu
        tools_menu = menubar.addMenu("Tools")
        tools_menu.addAction("Clear Insights", self.insight_engine.clear)
        tools_menu.addAction("Reset Signals", self.signal_engine.clear)

    def apply_diagnostics_layout(self):
        """Apply diagnostics-optimized layout"""
        w = 370
        h = 260

        # Large 3D view (left side)
        self._apply_geometry_if_not_moved(self.view_3d, 0, 0, w * 2, h * 2)

        # Scope (bottom left)
        self._apply_geometry_if_not_moved(self.scope, 0, h * 2, w * 2, h * 1.5)

        # Phasor (top right)
        self._apply_geometry_if_not_moved(self.phasor, w * 2, 0, w, h)

        # Insights (middle right)
        self._apply_geometry_if_not_moved(self.insights, w * 2, h, w, h)

        # Fault Injector (bottom right)
        self._apply_geometry_if_not_moved(self.injector, w * 2, h * 2, w, h * 1.5)

    def _on_frame(self, frame):
        """Handle incoming data frame from serial manager"""
        # Push to signal engine
        channels = {}
        for key in ['v_an', 'v_bn', 'v_cn', 'i_a', 'i_b', 'i_c']:
            if key in frame:
                channels[key] = frame[key]
        timestamp = frame.get('timestamp', 0)
        if channels:
            self.signal_engine.push_sample(channels, timestamp)

        # Detect insights
        self.detect_insights(frame)

    def _on_scenario_event(self, event_type, details):
        """Handle scenario controller events"""
        self.statusBar().showMessage(f"Event: {event_type}")
        self.notify(f"Scenario event: {event_type}", "#f59e0b")

    def detect_insights(self, data):
        """Real-time insight detection"""
        timestamp = data.get('timestamp', 0)

        # THD detection
        for phase in ['A', 'B', 'C']:
            thd = self.signal_engine.get_thd(f'v_{phase.lower()}n')
            insight = self.insight_engine.detect_thd_event(thd, phase, timestamp)
            if insight:
                self.insight_engine.add_insight(insight)
                self.insights.add_insight(insight.to_dict())

        # Frequency detection
        freq = self.signal_engine.get_frequency('v_an')
        freq_insight = self.insight_engine.detect_frequency_event(freq, timestamp)
        if freq_insight:
            self.insight_engine.add_insight(freq_insight)
            self.insights.add_insight(freq_insight.to_dict())

    def export_to_replay(self):
        """Export current session to Replay Studio"""
        from hil_core.export_context import ContextExporter

        export_path = ContextExporter.export_for_replay(
            waveform_channels=self.signal_engine.get_all_channels(),
            sample_rate=self.signal_engine.sample_rate,
            scenario_name="Diagnostic Session",
            insights=self.insight_engine.export_insights(),
            tags=[]
        )

        self.notify("Exported to Replay Studio", "#06b6d4")

        # Launch Replay Studio
        import subprocess
        replay_launcher = Path(__file__).parent / 'launch_replay.py'
        subprocess.Popen([sys.executable, str(replay_launcher)])

    def export_to_compliance(self):
        """Export to Compliance Lab"""
        from hil_core.export_context import ContextExporter

        export_path = ContextExporter.export_for_compliance(
            waveform_channels=self.signal_engine.get_all_channels(),
            sample_rate=self.signal_engine.sample_rate,
            validation_results={},
            scenario_name="Diagnostic Session"
        )

        self.notify("Exported to Compliance Lab", "#8b5cf6")

    def start_monitoring(self):
        """Start data acquisition via mock mode"""
        self.serial_mgr.start_mock_mode()
        self.notify("Monitoring started", "#10b981")

    def stop_monitoring(self):
        """Pause data acquisition"""
        self.serial_mgr.stop_mock_mode()
        self.notify("Monitoring paused", "#f59e0b")

    def capture_snapshot(self):
        """Capture current state"""
        self.notify("Snapshot captured", "#38bdf8")

    def load_session(self):
        """Load saved session"""
        self._import_context()

    def save_session(self):
        """Save current session"""
        self._export_context()

    def toggle_fullscreen(self):
        """Toggle fullscreen mode"""
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()


def main():
    args = LauncherBase.parse_args()
    app = QApplication(sys.argv)

    # Show splash screen
    splash = RotorSplashScreen()
    splash.show()
    app.processEvents()

    # Create main window
    window = DiagnosticsWindow()

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

    # Close splash and show window
    splash.finish(window)
    window.show()

    sys.exit(app.exec())


if __name__ == '__main__':
    main()
