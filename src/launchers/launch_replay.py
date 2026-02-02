"""
RedByte Replay Studio - Timeline playback & waveform review
Entry point for temporal analysis and tagged replay
"""

import sys
from pathlib import Path

# Add parent and project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(Path(__file__).parent.parent))

from PyQt6.QtWidgets import (QApplication, QToolBar,
                              QSlider, QLabel, QHBoxLayout, QWidget)
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QAction

from hil_core import SessionContext
from ui.app_themes import get_replay_style
from ui.replay_studio import ReplayStudio
from ui.phasor_view import PhasorView
from ui.insights_panel import InsightsPanel
from ui.splash_screen import RotorSplashScreen
from serial_reader import SerialManager
from recorder import Recorder
from launcher_base import LauncherBase


class ReplayWindow(LauncherBase):
    """RedByte Replay Studio main window"""

    app_name = "replay"

    def __init__(self):
        super().__init__()
        self.setWindowTitle("🔵 RedByte Replay Studio - Timeline Playback & Review")
        self.resize(1400, 800)

        # Apply replay theme
        self.setStyleSheet(get_replay_style())

        # Initialize backend dependencies
        self.serial_mgr = SerialManager()
        self.recorder = Recorder()
        self.serial_mgr.frame_received.connect(self.recorder.log_frame)

        # Playback state
        self.playback_position = 0
        self.playing = False

        # Try to import context from diagnostics
        if self.session.import_context('diagnostics'):
            print("✅ Loaded session from Diagnostics")
        else:
            print("ℹ️ No session data found - starting empty")

        self.create_panels()
        self.create_toolbar()
        self.create_playback_controls()
        self.apply_replay_layout()
        self._setup_status_bar(self.serial_mgr)
        self._apply_panel_tooltips()
        self._finish_init()

        # Playback timer
        self.play_timer = QTimer()
        self.play_timer.timeout.connect(self.advance_playback)

    def create_panels(self):
        """Create replay-focused panels"""
        # Replay Studio (main timeline view)
        self.replay = ReplayStudio(self.recorder, self.serial_mgr)
        sub_replay = self.mdi.addSubWindow(self.replay)
        sub_replay.setWindowTitle("⏯️ Timeline")
        sub_replay.show()
        self._register_subwindow(sub_replay)

        # Phasor (scrollable for timeline)
        self.phasor = PhasorView(self.serial_mgr)
        sub_phasor = self.mdi.addSubWindow(self.phasor)
        sub_phasor.setWindowTitle("🌈 Phasor History")
        sub_phasor.show()
        self._register_subwindow(sub_phasor)

        # Insights (expandable)
        self.insights = InsightsPanel()
        sub_insights = self.mdi.addSubWindow(self.insights)
        sub_insights.setWindowTitle("💡 Event Log")
        sub_insights.show()
        self._register_subwindow(sub_insights)

        # Load session insights if available
        if self.session.insights:
            for insight in self.session.insights:
                self.insights.add_insight(insight)

    def create_toolbar(self):
        """Create replay toolbar"""
        toolbar = QToolBar("Replay")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        # Playback controls
        act_play = QAction("▶️ Play", self)
        act_play.triggered.connect(self.play)
        toolbar.addAction(act_play)

        act_pause = QAction("⏸️ Pause", self)
        act_pause.triggered.connect(self.pause)
        toolbar.addAction(act_pause)

        act_stop = QAction("⏹️ Stop", self)
        act_stop.triggered.connect(self.stop)
        toolbar.addAction(act_stop)

        toolbar.addSeparator()

        # Tagging
        act_tag = QAction("🏷️ Add Tag", self)
        act_tag.triggered.connect(self.add_tag)
        toolbar.addAction(act_tag)

        toolbar.addSeparator()

        # Export
        act_export = QAction("💾 Export Tags", self)
        act_export.triggered.connect(self.export_tags)
        toolbar.addAction(act_export)

        act_insights = QAction("🟨 Open in Insight Studio", self)
        act_insights.triggered.connect(self.export_to_insights)
        toolbar.addAction(act_insights)

        self._add_context_actions(toolbar)

    def create_playback_controls(self):
        """Create playback control bar at bottom"""
        control_widget = QWidget()
        control_layout = QHBoxLayout(control_widget)

        # Position label
        self.pos_label = QLabel("00:00.000")
        self.pos_label.setStyleSheet("color: #06b6d4; font-weight: bold;")
        control_layout.addWidget(self.pos_label)

        # Timeline slider
        self.timeline_slider = QSlider(Qt.Orientation.Horizontal)
        self.timeline_slider.setRange(0, 10000)
        self.timeline_slider.valueChanged.connect(self.seek)
        control_layout.addWidget(self.timeline_slider)

        # Duration label
        self.duration_label = QLabel("00:00.000")
        self.duration_label.setStyleSheet("color: #06b6d4; font-weight: bold;")
        control_layout.addWidget(self.duration_label)

        # Add to bottom toolbar
        bottom_toolbar = QToolBar("Timeline")
        self.addToolBar(Qt.ToolBarArea.BottomToolBarArea, bottom_toolbar)
        bottom_toolbar.addWidget(control_widget)

    def apply_replay_layout(self):
        """Apply replay-optimized layout"""
        w = 400
        h = 280

        # Large timeline view (left)
        self._apply_geometry_if_not_moved(self.replay, 0, 0, w * 2.5, h * 2)

        # Phasor (top right)
        self._apply_geometry_if_not_moved(self.phasor, w * 2.5, 0, w, h)

        # Insights (bottom right)
        self._apply_geometry_if_not_moved(self.insights, w * 2.5, h, w, h)

    def play(self):
        """Start playback"""
        self.playing = True
        self.play_timer.start(50)  # 20 FPS
        print("▶️ Playback started")

    def pause(self):
        """Pause playback"""
        self.playing = False
        self.play_timer.stop()
        print("⏸️ Playback paused")

    def stop(self):
        """Stop and reset playback"""
        self.playing = False
        self.play_timer.stop()
        self.playback_position = 0
        self.timeline_slider.setValue(0)
        print("⏹️ Playback stopped")

    def advance_playback(self):
        """Advance playback position"""
        self.playback_position += 1
        if self.playback_position >= self.timeline_slider.maximum():
            self.stop()
        else:
            self.timeline_slider.setValue(self.playback_position)

    def seek(self, position):
        """Seek to position"""
        self.playback_position = position
        seconds = position / 100.0  # Convert to seconds
        mins = int(seconds // 60)
        secs = seconds % 60
        self.pos_label.setText(f"{mins:02d}:{secs:06.3f}")

    def add_tag(self):
        """Add timeline tag at current position"""
        tag_label = f"Tag {len(self.session.tags) + 1}"
        self.session.add_tag(
            timestamp=self.playback_position / 100.0,
            label=tag_label,
            color="#06b6d4",
            notes=""
        )
        self.notify(f"Added tag: {tag_label}", "#06b6d4")

    def export_tags(self):
        """Export tags to JSON"""
        import json
        export_path = Path("temp") / "replay_tags.json"
        export_path.parent.mkdir(exist_ok=True)
        with open(export_path, 'w') as f:
            json.dump(self.session.tags, f, indent=2)
        self.notify(f"Exported tags to {export_path}")

    def export_to_insights(self):
        """Export to Insight Studio"""
        from hil_core.export_context import ContextExporter

        export_path = ContextExporter.export_for_insights(
            insights=self.session.insights
        )
        self.notify(f"Exported to Insight Studio")

    def _on_context_loaded(self):
        """Refresh UI after context import."""
        if self.session.insights:
            for insight in self.session.insights:
                self.insights.add_insight(insight)


def main():
    args = LauncherBase.parse_args()
    app = QApplication(sys.argv)

    splash = RotorSplashScreen()
    splash.show()
    app.processEvents()

    window = ReplayWindow()

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
        window._on_context_loaded()

    splash.finish(window)
    window.show()

    sys.exit(app.exec())


if __name__ == '__main__':
    main()
