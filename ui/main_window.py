import sys
import logging
import os
import json
import math
import time
import webbrowser
from PyQt6.QtWidgets import QMainWindow, QMdiArea, QMdiSubWindow, QToolBar, QStatusBar, QLabel, QComboBox
from PyQt6.QtGui import QAction
from PyQt6.QtCore import Qt, pyqtSlot, QTimer

from ui.inverter_scope import InverterScope
from ui.fault_injector import FaultInjector
from ui.session_manager import SessionApp
from ui.analysis_app import AnalysisApp
from ui.validation_dashboard import ValidationDashboard
from ui.phasor_view import PhasorView
from ui.system_3d_view import System3DView
from ui.replay_studio import ReplayStudio
from ui.signal_sculptor import SignalSculptor
from ui.status_bar import StatusBarWidget
from ui.insights_panel import InsightsPanel
from ui.help_overlay import HelpOverlay
from ui.overlay import OverlayMessage
from ui.tooltip_manager import apply_all_tooltips
from src.serial_reader import SerialManager
from src.recorder import Recorder
from src.scenario import ScenarioController
from src.scenario import ScenarioValidator
from src.compliance_checker import evaluate_ieee_2800
from src.insight_engine import InsightEngine
from src.layout_manager import LayoutManager
from src.report_generator import generate_report
from src.system_status import evaluate_system_status
from ui.layout_presets import apply_diagnostics_matrix

logger = logging.getLogger(__name__)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("HIL Verifier Suite - RedByte PROD")
        self.resize(1400, 900)
        self.demo_enabled = False
        self.layout_locked = False
        self.initializing = True
        
        # Geometry persistence for floating panels
        self.saved_geometries = {}
        self.user_moved_panels = set()  # Track manually positioned panels
        self.last_auto_pin_time = {}  # Debounce auto-pinning
        
        # Backend Managers
        self.serial_mgr = SerialManager()
        self.recorder = Recorder()
        self.scenario_ctrl = ScenarioController()
        self.insight_engine = InsightEngine()
        
        # Connect backend
        self.serial_mgr.frame_received.connect(self.recorder.log_frame)
        self.scenario_ctrl.event_triggered.connect(self._on_scenario_event)
        self.serial_mgr.frame_received.connect(self.insight_engine.update)
        self.serial_mgr.frame_received.connect(self._on_frame)
        
        # MDI Area
        self.mdi = QMdiArea()
        self.setCentralWidget(self.mdi)
        
        # Create Sub-Apps (Specialized)
        self.scope = InverterScope(self.serial_mgr)
        self.injector = FaultInjector(self.scenario_ctrl, self.serial_mgr)
        self.session_mgr = SessionApp() 
        self.analysis = AnalysisApp()
        self.dashboard = ValidationDashboard(self.scenario_ctrl)
        self.phasor_view = PhasorView(self.serial_mgr)
        self.view_3d = System3DView(self.serial_mgr, self.scenario_ctrl)
        self.replay_studio = ReplayStudio(self.recorder, self.serial_mgr)
        self.sculptor = SignalSculptor(self.serial_mgr)
        self.insights = InsightsPanel()
        
        self.windows = []
        self._add_subwindow(self.scope, "Inverter Scope (Live)")
        self._add_subwindow(self.injector, "Fault Injector")
        self._add_subwindow(self.dashboard, "Validation Dashboard")
        self._add_subwindow(self.phasor_view, "Phasor Diagram")
        self._add_subwindow(self.view_3d, "3D System")
        self._add_subwindow(self.replay_studio, "Replay Studio")
        self._add_subwindow(self.sculptor, "Signal Sculptor")
        self._add_subwindow(self.insights, "Insights")
        
        # Status Badge (Floating Overlay)
        self.status_badge = QLabel("SYSTEM: NOMINAL", self)
        self.status_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_badge.setStyleSheet("""
            QLabel {
                background-color: rgba(16, 185, 129, 220);
                color: #0b111a;
                border-radius: 12px;
                padding: 8px 12px;
                font-weight: 700;
                font-size: 12pt;
                border: 1px solid rgba(255,255,255,0.2);
            }
        """)
        self.status_badge.setFixedSize(220, 45)
        self.status_badge.hide()
        self._last_frame = {}
        self._system_status = "NOMINAL"

        # Toolbar & Menu
        self._create_toolbar()
        
        # Status Bar
        self.statusBar().showMessage("Ready. System Config Loaded.")
        self.status_widget = StatusBarWidget(self.serial_mgr)
        self.statusBar().addPermanentWidget(self.status_widget)
        self.status_widget.metrics_updated.connect(self._on_metrics)

        self.insight_engine.insight_emitted.connect(self.insights.add_insight)
        self.insight_engine.insight_emitted.connect(self._on_insight)
        self.layout_manager = LayoutManager(self)

        self.overlay = OverlayMessage(self)
        self.help_overlay = HelpOverlay(self)
        self.help_overlay.hide()

        if not os.path.exists(os.path.join("config", "system_config.json")):
            self._show_help_overlay()
        
        # Initial Layout
        self.mdi.tileSubWindows()

        self._load_last_layout()
        
        # Apply comprehensive tooltips
        apply_all_tooltips(self)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'status_badge'):
            self.status_badge.move(self.width() - self.status_badge.width() - 20, 60)

    def _add_subwindow(self, widget, title):
        sub = QMdiSubWindow()
        sub.setWidget(widget)
        sub.setWindowTitle(title)
        self.mdi.addSubWindow(sub)
        sub.show()
        self.windows.append(sub)
        
        # Track user movements to prevent auto-repositioning
        sub.installEventFilter(self)
    
    def eventFilter(self, obj, event):
        """Track user-initiated panel movements"""
        if isinstance(obj, QMdiSubWindow):
            if event.type() == event.Type.Move and not self.layout_locked and not self.initializing:
                # User manually moved this panel
                widget_title = obj.windowTitle()
                self.user_moved_panels.add(widget_title)
                # Save geometry
                self.saved_geometries[widget_title] = obj.geometry()
        return super().eventFilter(obj, event)

    def _create_toolbar(self):
        toolbar = QToolBar("Main Toolbar")
        self.toolbar = toolbar
        self.addToolBar(toolbar)
        
        act_tile = QAction("Tile Windows", self)
        act_tile.triggered.connect(self.mdi.tileSubWindows)
        toolbar.addAction(act_tile)
        
        act_reset = QAction("Reset Layout", self)
        act_reset.triggered.connect(self._reset_layout)
        toolbar.addAction(act_reset)

        toolbar.addSeparator()
        
        self.act_demo = QAction("Demo Mode", self)
        self.act_demo.setCheckable(True)
        self.act_demo.toggled.connect(self._toggle_demo_mode)
        toolbar.addAction(self.act_demo)

        toolbar.addSeparator()
        
        pres_action = QAction("Presentation Mode", self)
        pres_action.setCheckable(True)
        pres_action.toggled.connect(self._toggle_presentation_mode)
        toolbar.addAction(pres_action)

        toolbar.addSeparator()

        self.layout_combo = QComboBox()
        self.layout_combo.addItems(["Diagnostics Matrix", "Full View", "Engineer View", "Analyst View", "3D Ops View"])
        self.layout_combo.currentTextChanged.connect(self._apply_layout_preset)
        toolbar.addWidget(self.layout_combo)

        toolbar.addSeparator()
        
        # === QUICK JUMP TABS ===
        toolbar.addWidget(QLabel("  Quick Jump:"))
        
        self.jump_diagnostics = QAction("⚡ Diagnostics", self)
        self.jump_diagnostics.setCheckable(True)
        self.jump_diagnostics.triggered.connect(lambda: self._quick_jump("Diagnostics"))
        toolbar.addAction(self.jump_diagnostics)
        
        self.jump_timeline = QAction("📊 Timeline", self)
        self.jump_timeline.setCheckable(True)
        self.jump_timeline.triggered.connect(lambda: self._quick_jump("Timeline"))
        toolbar.addAction(self.jump_timeline)
        
        self.jump_spectral = QAction("🌈 Spectral", self)
        self.jump_spectral.setCheckable(True)
        self.jump_spectral.triggered.connect(lambda: self._quick_jump("Spectral"))
        toolbar.addAction(self.jump_spectral)
        
        self.jump_grid = QAction("🎛️ Grid", self)
        self.jump_grid.setCheckable(True)
        self.jump_grid.triggered.connect(lambda: self._quick_jump("Grid"))
        toolbar.addAction(self.jump_grid)
        
        self.jump_minimal = QAction("🎯 Minimal", self)
        self.jump_minimal.setCheckable(True)
        self.jump_minimal.triggered.connect(lambda: self._quick_jump("Minimal"))
        toolbar.addAction(self.jump_minimal)
        
        toolbar.addSeparator()
        act_snapshot = QAction("📸 Capture Scene", self)
        act_snapshot.triggered.connect(self._capture_scene)
        toolbar.addAction(act_snapshot)

    def _apply_layout_preset(self, mode):
        if self.layout_locked:
            logger.debug(f"Layout change blocked (locked): {mode}")
            return
        logger.info(f"Applying layout: {mode}")
        self._save_layout(mode)
        
        # Save current geometries before layout change
        for sub in self.windows:
            title = sub.windowTitle()
            if title in self.user_moved_panels:
                self.saved_geometries[title] = sub.geometry()
        
        for sub in self.windows:
            sub.showNormal()

        if mode == "Diagnostics Matrix":
            self._show_only([self.view_3d, self.phasor_view, self.insights, self.scope, self.injector, self.replay_studio, self.dashboard])
            apply_diagnostics_matrix(self, respect_user_positions=True, saved_geometries=self.saved_geometries, user_moved=self.user_moved_panels)
        elif mode == "Engineer View":
            self._show_only([self.scope, self.phasor_view, self.injector, self.sculptor])
            self._apply_geometry_if_not_user_moved(self.scope, 0, 0, 900, 600)
            self._apply_geometry_if_not_user_moved(self.phasor_view, 900, 0, 450, 300)
            self._apply_geometry_if_not_user_moved(self.injector, 900, 300, 450, 300)
            self._apply_geometry_if_not_user_moved(self.sculptor, 0, 600, 900, 250)
        elif mode == "Analyst View":
            self._show_only([self.replay_studio, self.analysis, self.dashboard])
            self._apply_geometry_if_not_user_moved(self.replay_studio, 0, 0, 900, 650)
            self._apply_geometry_if_not_user_moved(self.analysis, 900, 0, 450, 325)
            self._apply_geometry_if_not_user_moved(self.dashboard, 900, 325, 450, 325)
        elif mode == "3D Ops View":
            self._show_only([self.view_3d, self.phasor_view, self.injector])
            self._apply_geometry_if_not_user_moved(self.view_3d, 0, 0, 900, 650)
            self._apply_geometry_if_not_user_moved(self.phasor_view, 900, 0, 450, 325)
            self._apply_geometry_if_not_user_moved(self.injector, 900, 325, 450, 325)
        else:
            for sub in self.windows:
                sub.show()
            self.mdi.tileSubWindows()
        
        # Restore user-moved panels to their saved positions
        self._restore_user_geometries()

    def _show_only(self, widgets):
        for sub in self.windows:
            if sub.widget() in widgets:
                sub.show()
            else:
                sub.hide()
    
    def _apply_geometry_if_not_user_moved(self, widget, x, y, w, h):
        """Apply geometry only if user hasn't manually positioned this panel"""
        sub = widget.parent()
        if not sub:
            return
        
        title = sub.windowTitle()
        
        # If user moved this panel, restore their position instead
        if title in self.user_moved_panels and title in self.saved_geometries:
            sub.setGeometry(self.saved_geometries[title])
            logger.debug(f"Restored user position for {title}")
        else:
            # Apply preset geometry
            sub.setGeometry(x, y, w, h)
    
    def _restore_user_geometries(self):
        """Restore saved geometries for user-moved panels"""
        for sub in self.windows:
            title = sub.windowTitle()
            if title in self.user_moved_panels and title in self.saved_geometries:
                sub.setGeometry(self.saved_geometries[title])
                logger.debug(f"Restored saved geometry for {title}")

    def _quick_jump(self, mode):
        """Quick Jump Tab handler - switches layout and focuses relevant panels"""
        logger.info(f"Quick Jump: {mode}")
        
        # Update Quick Jump button states
        for action in [self.jump_diagnostics, self.jump_timeline, self.jump_spectral, self.jump_grid, self.jump_minimal]:
            action.setChecked(False)
        
        if mode == "Diagnostics":
            self.jump_diagnostics.setChecked(True)
            self.layout_combo.blockSignals(True)
            self.layout_combo.setCurrentText("Diagnostics Matrix")
            self.layout_combo.blockSignals(False)
            self._apply_layout_preset("Diagnostics Matrix")
            self.insights.parent().activateWindow()
            
        elif mode == "Timeline":
            self.jump_timeline.setChecked(True)
            self._show_only([self.replay_studio, self.insights, self.dashboard])
            self.replay_studio.parent().setGeometry(0, 0, 1000, 700)
            self.insights.parent().setGeometry(1000, 0, 350, 350)
            self.dashboard.parent().setGeometry(1000, 350, 350, 350)
            self.replay_studio.parent().activateWindow()
            if hasattr(self.replay_studio, 'tabs'):
                self.replay_studio.tabs.setCurrentIndex(0)  # Waveform tab
            
        elif mode == "Spectral":
            self.jump_spectral.setChecked(True)
            self._show_only([self.replay_studio, self.scope, self.phasor_view])
            self.replay_studio.parent().setGeometry(0, 0, 900, 650)
            self.scope.parent().setGeometry(900, 0, 450, 325)
            self.phasor_view.parent().setGeometry(900, 325, 450, 325)
            self.replay_studio.parent().activateWindow()
            if hasattr(self.replay_studio, 'tabs'):
                self.replay_studio.tabs.setCurrentIndex(2)  # Spectrum tab
            
        elif mode == "Grid":
            self.jump_grid.setChecked(True)
            for sub in self.windows:
                sub.show()
            self.mdi.tileSubWindows()
            
        elif mode == "Minimal":
            self.jump_minimal.setChecked(True)
            self._show_only([self.scope, self.phasor_view])
            self.scope.parent().setGeometry(0, 0, 900, 700)
            self.phasor_view.parent().setGeometry(900, 0, 450, 700)
            self.scope.parent().activateWindow()
        
        self.overlay.show_message(f"⚡ Jumped to {mode} View", duration=1500)

    def _save_layout(self, mode):
        try:
            os.makedirs("config", exist_ok=True)
            with open(os.path.join("config", "last_layout.json"), "w") as f:
                json.dump({"layout": mode}, f)
        except Exception:
            pass

    def _load_last_layout(self):
        try:
            with open(os.path.join("config", "last_layout.json"), "r") as f:
                mode = json.load(f).get("layout", "Full View")
            self.layout_combo.blockSignals(True)
            self.layout_combo.setCurrentText(mode)
            self.layout_combo.blockSignals(False)
            self.layout_locked = True
            self._apply_layout_preset(mode)
            self.layout_locked = False
        except Exception:
            self.layout_locked = True
            self._apply_layout_preset("Full View")
            self.layout_locked = False
        finally:
            self.initializing = False

    def _on_metrics(self, rms, thd):
        self.layout_manager.on_metrics(thd)
        self._update_system_status(thd=thd, frame=self._last_frame)

    def _on_frame(self, frame):
        self._last_frame = frame
        self.layout_manager.on_frame(frame)

    def _update_system_status(self, thd, frame):
        freq = frame.get("freq", 60.0) if frame else 60.0
        fault_active = bool(frame.get("fault_type")) if frame else False
        status = evaluate_system_status(thd, fault_active=fault_active, freq=freq)
        if status != self._system_status:
            self._system_status = status
        if status == "CRITICAL":
            self.status_badge.setText("SYSTEM: CRITICAL")
            self.status_badge.setStyleSheet(self.status_badge.styleSheet().replace("16, 185, 129", "239, 68, 68"))
            if hasattr(self, "toolbar"):
                self.toolbar.setStyleSheet("QToolBar { background: #3f1d1d; }")
        elif status == "DEGRADED":
            self.status_badge.setText("SYSTEM: DEGRADED")
            self.status_badge.setStyleSheet(self.status_badge.styleSheet().replace("16, 185, 129", "234, 179, 8"))
            if hasattr(self, "toolbar"):
                self.toolbar.setStyleSheet("QToolBar { background: #3b2d0a; }")
        else:
            self.status_badge.setText("SYSTEM: NOMINAL")
            self.status_badge.setStyleSheet(self.status_badge.styleSheet().replace("239, 68, 68", "16, 185, 129").replace("234, 179, 8", "16, 185, 129"))
            if hasattr(self, "toolbar"):
                self.toolbar.setStyleSheet("")

    def _on_insight(self, payload):
        name = payload.get("type", "insight")
        self._capture_scene(event_type="insight", event_name=name)
        self._auto_pin_for_insight(name)
    
    def _auto_pin_for_insight(self, insight_type):
        """Auto-pin relevant panels based on insight type"""
        insight_lower = insight_type.lower()
        
        if "unbalance" in insight_lower or "phase" in insight_lower:
            # Pin phasor view top-left for phase issues
            self._auto_pin_panel(self.phasor_view, position="top-left")
            self.overlay.show_message(f"📍 Auto-pinned Phasor View: {insight_type}", duration=2000)
            
        elif "harmonic" in insight_lower or "thd" in insight_lower:
            # Pin replay studio (spectrum tab) for harmonic analysis
            self._auto_pin_panel(self.replay_studio, position="top-left")
            if hasattr(self.replay_studio, 'tabs'):
                self.replay_studio.tabs.setCurrentIndex(2)  # Spectrum tab
            self.overlay.show_message(f"📍 Auto-pinned Spectrum Analysis: {insight_type}", duration=2000)
            
        elif "frequency" in insight_lower or "undershoot" in insight_lower:
            # Pin scope and insights panel for frequency events
            self._auto_pin_panel(self.scope, position="top-left")
            self._auto_pin_panel(self.insights, position="top-right")
            self.overlay.show_message(f"📍 Auto-pinned Scope + Insights: {insight_type}", duration=2000)
            
        elif "recovery" in insight_lower:
            # Pin dashboard for recovery analysis
            self._auto_pin_panel(self.dashboard, position="bottom-right")
            self.overlay.show_message(f"📍 Auto-pinned Dashboard: {insight_type}", duration=2000)
    
    def _auto_pin_panel(self, panel, position="top-left"):
        """Pin a panel to a specific screen position with debouncing"""
        sub = panel.parent()
        if not sub:
            return
        
        title = sub.windowTitle()
        current_time = time.time()
        
        # Debounce: Don't re-pin if recently pinned (within 3 seconds)
        if title in self.last_auto_pin_time:
            if current_time - self.last_auto_pin_time[title] < 3.0:
                logger.debug(f"Auto-pin debounced for {title}")
                return
        
        # Don't override if user manually moved this panel
        if title in self.user_moved_panels:
            logger.debug(f"Auto-pin skipped: {title} was manually positioned")
            # Just raise and activate, don't reposition
            sub.show()
            sub.raise_()
            sub.activateWindow()
            return
        
        # Only pin if not already visible and focused
        if sub.isVisible() and sub.isActiveWindow():
            logger.debug(f"Auto-pin skipped: {title} already active")
            return
        
        sub.show()
        sub.raise_()
        sub.activateWindow()
        
        w = 500
        h = 400
        
        if position == "top-left":
            sub.setGeometry(20, 80, w, h)
        elif position == "top-right":
            sub.setGeometry(self.width() - w - 40, 80, w, h)
        elif position == "bottom-left":
            sub.setGeometry(20, self.height() - h - 100, w, h)
        elif position == "bottom-right":
            sub.setGeometry(self.width() - w - 40, self.height() - h - 100, w, h)
        
        # Record pin time for debouncing
        self.last_auto_pin_time[title] = current_time
        logger.debug(f"Auto-pinned {title} to {position}")

    def _capture_scene(self, event_type="snapshot", event_name="scene"):
        """Capture scene snapshots with rich auto-annotations"""
        os.makedirs("snapshots", exist_ok=True)
        ts = time.strftime("%Y%m%d_%H%M%S")
        safe_event = str(event_name).replace(" ", "_")
        
        # Gather annotation data
        annotations = self._gather_scene_annotations()
        
        for sub in self.windows:
            widget = sub.widget()
            if widget:
                pix = widget.grab()
                
                # Add text annotations overlay
                from PyQt6.QtGui import QPainter, QFont, QColor
                painter = QPainter(pix)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                
                # Semi-transparent annotation bar at top
                painter.fillRect(0, 0, pix.width(), 40, QColor(15, 17, 21, 220))
                
                # Annotation text
                font = QFont("JetBrains Mono", 9, QFont.Weight.Bold)
                painter.setFont(font)
                painter.setPen(QColor(16, 185, 129))
                
                anno_text = f"📸 {event_type.upper()}: {event_name} | "
                anno_text += f"t={annotations['timestamp']:.2f}s | "
                anno_text += f"THD={annotations['thd']:.1f}% | "
                anno_text += f"Freq={annotations['frequency']:.2f}Hz | "
                anno_text += f"Rotor={annotations['rotor_angle']:.0f}° | "
                anno_text += f"Insights={annotations['insight_count']}"
                
                painter.drawText(10, 25, anno_text)
                painter.end()
                
                name = widget.windowTitle().replace(" ", "_")
                path = os.path.join("snapshots", f"snapshot_{ts}_{event_type}_{safe_event}_{name}.png")
                pix.save(path)
        
        # Also save annotation metadata to JSON
        import json
        meta_path = os.path.join("snapshots", f"snapshot_{ts}_{event_type}_{safe_event}_metadata.json")
        with open(meta_path, 'w') as f:
            json.dump({
                "timestamp": ts,
                "event_type": event_type,
                "event_name": event_name,
                "annotations": annotations,
                "system_status": self._system_status
            }, f, indent=2)
    
    def _gather_scene_annotations(self):
        """Gather current system state for annotations"""
        # Get latest metrics from status widget
        thd = 0.0
        frequency = 60.0
        if hasattr(self, 'status_widget'):
            # Try to extract from status widget
            status_text = self.status_widget.lbl_rms.text()
            # Parse "RMS: 120.3V | THD: 3.2% | Freq: 60.01Hz"
            if "THD:" in status_text:
                try:
                    thd_str = status_text.split("THD:")[1].split("%")[0].strip()
                    thd = float(thd_str)
                except:
                    pass
            if "Freq:" in status_text:
                try:
                    freq_str = status_text.split("Freq:")[1].split("Hz")[0].strip()
                    frequency = float(freq_str)
                except:
                    pass
        
        # Get rotor angle from 3D view
        rotor_angle = 0.0
        if hasattr(self.view_3d, 'rotor_angle'):
            rotor_angle = self.view_3d.rotor_angle
        
        # Get insight count
        insight_count = 0
        if hasattr(self.insights, 'insight_count'):
            insight_count = self.insights.insight_count
        
        # Get current timestamp
        current_time = self._last_frame.get('ts', 0) if self._last_frame else 0
        
        return {
            "timestamp": current_time,
            "thd": thd,
            "frequency": frequency,
            "rotor_angle": rotor_angle,
            "insight_count": insight_count,
            "system_status": self._system_status
        }

    def _reset_layout(self):
        # Specific spatial layout for demo "Wow" Factor
        w = 450
        h = 400
        # Main monitoring column (Left)
        self.scope.parent().setGeometry(0, 0, w*2, h*2)
        
        # Secondary visuals column (Right Top)
        self.phasor_view.parent().setGeometry(w*2, 0, w, h)
        # 3D View (Right Bottom)
        self.view_3d.parent().setGeometry(w*2, h, w, h)
        
        # Analysis/Control row (Bottom)
        self.dashboard.parent().setGeometry(0, h*2, w, 200)
        self.injector.parent().setGeometry(w, h*2, w, 200)
        
        self.statusBar().showMessage("Layout Reset to Professional Grid")

    @pyqtSlot(str, dict)
    def _on_scenario_event(self, type_name, data):
        logger.info(f"Event: {type_name}")
        self.statusBar().showMessage(f"Event Trace: {type_name}")
        
        if "fault" in type_name.lower():
            self.status_badge.setText("SYSTEM: FAULT")
            self.status_badge.setStyleSheet(self.status_badge.styleSheet().replace("16, 185, 129", "239, 68, 68"))
            self._capture_scene(event_type="fault", event_name=type_name)
        else:
            self.status_badge.setText("SYSTEM: NOMINAL")
            self.status_badge.setStyleSheet(self.status_badge.styleSheet().replace("239, 68, 68", "16, 185, 129"))

    def _toggle_presentation_mode(self, enabled):
        if enabled:
            # Default to diagnostics matrix for presentation
            self.layout_locked = True
            self.layout_combo.blockSignals(True)
            self.layout_combo.setCurrentText("Diagnostics Matrix")
            self.layout_combo.blockSignals(False)
            self.layout_locked = False
            for sub in self.windows:
                widget_type = type(sub.widget())
                if widget_type in [SessionApp, AnalysisApp, FaultInjector, ReplayStudio, SignalSculptor]:
                    sub.hide()
                else:
                    sub.showMaximized()
            self.mdi.tileSubWindows()
            self._set_dark_theme(True)
            self.status_badge.show()
            self.statusBar().showMessage("Presentation Mode: ON")
        else:
            for sub in self.windows:
                sub.showNormal()
            self.mdi.tileSubWindows()
            self._set_dark_theme(False)
            self.status_badge.hide()
            self.statusBar().showMessage("Presentation Mode: OFF")
            
    def _set_dark_theme(self, enabled):
        if enabled:
            self.setStyleSheet("""
                QMainWindow { background-color: #0f1115; }
                QMdiArea { background-color: #0f1115; }
                QLabel { color: #e6e9ef; font-family: 'Segoe UI'; }
                QStatusBar { background: #141824; color: #cbd5e1; }
            """)
        else:
            self.setStyleSheet("")
            
    def _toggle_demo_mode(self, enabled):
        if enabled:
            self.enable_demo_mode()
        else:
            self.disable_demo_mode()

    def enable_demo_mode(self):
        if self.demo_enabled:
            logger.debug("Demo mode already enabled, skipping")
            return
        logger.info("Enabling demo mode...")
        self.demo_enabled = True
        self.statusBar().showMessage("Demo Mode Enabled: Simulating 3-Phase Data")
        self.status_widget.set_mode("DEMO")
        self.serial_mgr.start_mock_mode()
        self._ensure_demo_assets()
        self._show_help_overlay()

        # Fullscreen presentation for demo
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        self.showFullScreen()
        
        # Lock layout during presentation mode to prevent reset loop
        self.layout_locked = True
        self._toggle_presentation_mode(True)
        self.layout_locked = False

        demo_scenario = os.path.join("data", "demo_scenario.json")
        if os.path.exists(demo_scenario):
            self.scenario_ctrl.load_scenario(demo_scenario)

        demo_replay = os.path.join("data", "demo_replay.json")
        demo_overlay = os.path.join("data", "demo_replay_overlay.json")

        if os.path.exists(demo_replay):
            self.replay_studio._clear_all()
            self.replay_studio._load_session(demo_replay, is_primary=True)
            if os.path.exists(demo_overlay):
                self.replay_studio._load_session(demo_overlay, is_primary=False)

            # Auto-validate using scenario rules if present
            try:
                with open(demo_replay, 'r') as f:
                    session_data = json.load(f)
                rules = self.scenario_ctrl.scenario_data.get("validation", {}) if self.scenario_ctrl.scenario_data else {}
                if rules:
                    result = ScenarioValidator.validate(session_data, rules)
                    compliance = evaluate_ieee_2800(session_data)
                    pkg = {
                        "ts": time.time(),
                        "scenario": self.scenario_ctrl.scenario_data.get("name", "Demo") if self.scenario_ctrl.scenario_data else "Demo",
                        "passed": result.get("passed", False),
                        "details": "; ".join(result.get("logs", [])),
                        "compliance": compliance
                    }
                    self.scenario_ctrl.validation_complete.emit(pkg)
            except Exception:
                pass

        demo_script = os.path.join("data", "demo_script.json")
        if os.path.exists(demo_script):
            self._run_demo_script(demo_script)

    def disable_demo_mode(self):
        if not self.demo_enabled:
            return
        self.demo_enabled = False
        self.statusBar().showMessage("Demo Mode Disabled: Connecting to Serial")
        self.status_widget.set_mode("LIVE")
        self.serial_mgr.stop_mock_mode()
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, False)
        self.showNormal()

    def _ensure_demo_assets(self):
        os.makedirs("data", exist_ok=True)

        demo_replay = os.path.join("data", "demo_replay.json")
        demo_overlay = os.path.join("data", "demo_replay_overlay.json")

        def _generate_replay(path, drift=2.0, sag=0.6):
            frames = []
            events = []
            start_ts = time.time()
            dt = 0.05  # 20 Hz
            angle = 0.0

            for i in range(200):  # ~10s
                t_rel = i * dt
                freq = 60.0 + 0.1 * math.sin(t_rel * 0.5)
                v_scale = 1.0

                if 4.0 <= t_rel <= 6.0:
                    freq += drift
                    if i == int(4.0 / dt):
                        events.append({"ts": start_ts + t_rel, "type": "fault", "details": "frequency_drift"})

                if 7.0 <= t_rel <= 8.0:
                    v_scale = sag
                    if i == int(7.0 / dt):
                        events.append({"ts": start_ts + t_rel, "type": "fault", "details": "voltage_sag"})

                omega = 2 * math.pi * freq
                angle = (angle + omega * dt) % (2 * math.pi)

                v_peak = 120.0 * math.sqrt(2) * v_scale
                v_an = v_peak * math.sin(omega * t_rel)
                v_bn = v_peak * math.sin(omega * t_rel - 2.0944)
                v_cn = v_peak * math.sin(omega * t_rel + 2.0944)

                i_peak = 5.0 * math.sqrt(2)
                i_a = i_peak * math.sin(omega * t_rel - 0.1)
                i_b = i_peak * math.sin(omega * t_rel - 2.0944 - 0.1)
                i_c = i_peak * math.sin(omega * t_rel + 2.0944 - 0.1)

                v_an += v_peak * 0.03 * math.sin(5 * omega * t_rel)
                v_bn += v_peak * 0.03 * math.sin(5 * (omega * t_rel - 2.0944))
                v_cn += v_peak * 0.03 * math.sin(5 * (omega * t_rel + 2.0944))

                frames.append({
                    "ts": start_ts + t_rel,
                    "v_an": v_an, "v_bn": v_bn, "v_cn": v_cn,
                    "i_a": i_a, "i_b": i_b, "i_c": i_c,
                    "freq": freq,
                    "angle": math.degrees(angle),
                    "p_mech": 1000.0 + 10 * math.sin(t_rel * 0.3),
                })

            payload = {
                "meta": {"generated": True, "duration_s": 10.0, "frame_count": len(frames)},
                "events": events,
                "frames": frames,
            }
            with open(path, 'w') as f:
                json.dump(payload, f)

        def _needs_generate(path):
            return (not os.path.exists(path)) or os.path.getsize(path) < 100

        if _needs_generate(demo_replay):
            _generate_replay(demo_replay, drift=2.0, sag=0.6)
        if _needs_generate(demo_overlay):
            _generate_replay(demo_overlay, drift=1.0, sag=0.8)

    def _run_demo_script(self, path):
        try:
            with open(path, 'r') as f:
                actions = json.load(f)
        except Exception:
            return

        def schedule_next(idx):
            if idx >= len(actions):
                self._on_demo_complete()
                return
            action = actions[idx]
            delay = float(action.get("delay", 0.5))

            def execute():
                cmd = action.get("action")
                params = {k: v for k, v in action.items() if k not in ("delay", "action")}
                if cmd == "inject_sag":
                    self.serial_mgr.write_command("fault_sag", params)
                elif cmd == "inject_drift":
                    self.serial_mgr.write_command("fault_drift", params)
                elif cmd == "inject_phase_jump":
                    self.serial_mgr.write_command("fault_phase_jump", params)
                elif cmd == "inject_unbalance":
                    self.serial_mgr.write_command("fault_unbalance", params)
                elif cmd == "send_custom_waveform":
                    self.serial_mgr.write_command("inject_waveform", params)
                schedule_next(idx + 1)

            QTimer.singleShot(int(delay * 1000), execute)

        schedule_next(0)

    def _on_demo_complete(self):
        try:
            demo_replay = os.path.join("data", "demo_replay.json")
            os.makedirs("exports", exist_ok=True)
            report_path = generate_report(demo_replay, "exports")
            webbrowser.open(report_path)
            self.overlay.show_message("DEMO COMPLETE", color="#22c55e", pos=(10, 80))
        except Exception:
            pass

    def _show_help_overlay(self):
        self.help_overlay.setGeometry(20, 80, 360, 160)
        self.help_overlay.show()
