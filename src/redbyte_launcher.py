"""
RedByte Suite Launcher
Main entry point with app selection cards
"""

import sys
from pathlib import Path

# Add project root to path for ui module access
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / 'src'))

from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                              QHBoxLayout, QLabel, QPushButton, QFrame, QGridLayout)
from PyQt6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QRect
from PyQt6.QtGui import QFont, QIcon, QPixmap
import subprocess


class AppCard(QFrame):
    """Themed application launch card with hover animations"""
    
    def __init__(self, app_name: str, app_id: str, accent_color: str,
                 icon: str, description: str, launcher_script: str,
                 mock_mode: bool = False, parent=None):
        super().__init__(parent)
        self.app_name = app_name
        self.app_id = app_id
        self.accent_color = accent_color
        self.launcher_script = launcher_script
        self.mock_mode = mock_mode
        
        self.setFrameStyle(QFrame.Shape.Box | QFrame.Shadow.Raised)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumSize(280, 200)
        self.setMaximumSize(300, 220)
        
        # Apply themed style
        self.setStyleSheet(f"""
            AppCard {{
                background: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(30, 41, 59, 0.9),
                    stop:1 rgba(15, 23, 42, 0.9)
                );
                border: 2px solid {accent_color};
                border-radius: 16px;
                padding: 16px;
            }}
            AppCard:hover {{
                background: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(30, 41, 59, 1.0),
                    stop:1 rgba(15, 23, 42, 1.0)
                );
                border: 3px solid {accent_color};
            }}
        """)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        
        # Icon/emoji
        icon_label = QLabel(icon)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setFont(QFont('Segoe UI Emoji', 48))
        layout.addWidget(icon_label)
        
        # App name
        name_label = QLabel(app_name)
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name_label.setFont(QFont('JetBrains Mono', 14, QFont.Weight.Bold))
        name_label.setStyleSheet(f"color: {accent_color};")
        layout.addWidget(name_label)
        
        # Description
        desc_label = QLabel(description)
        desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc_label.setWordWrap(True)
        desc_label.setFont(QFont('JetBrains Mono', 9))
        desc_label.setStyleSheet("color: #94a3b8;")
        layout.addWidget(desc_label)
        
        layout.addStretch()
    
    def mousePressEvent(self, event):
        """Launch app on click"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.launch_app()
    
    def launch_app(self):
        """Launch the associated RedByte application"""
        launcher_path = Path(__file__).parent.parent / 'src' / 'launchers' / self.launcher_script

        if launcher_path.exists():
            cmd = [sys.executable, str(launcher_path)]
            if self.mock_mode:
                cmd.append('--mock')
            subprocess.Popen(cmd, cwd=str(launcher_path.parent.parent.parent))
        else:
            print(f"Launcher not found: {launcher_path}")


class RedByteLauncher(QMainWindow):
    """Main RedByte Suite launcher window"""

    def __init__(self, mock_mode: bool = False, auto_app: str | None = None):
        super().__init__()
        self.mock_mode = mock_mode
        self.setWindowTitle("RedByte HIL Suite")
        self.setMinimumSize(1000, 700)
        
        # Apply dark theme
        self.setStyleSheet("""
            QMainWindow {
                background: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 #0f172a,
                    stop:1 #1e293b
                );
            }
            QLabel {
                color: #e2e8f0;
            }
            QPushButton {
                background: rgba(59, 130, 246, 0.3);
                border: 2px solid rgba(59, 130, 246, 0.6);
                border-radius: 12px;
                color: #3b82f6;
                font-weight: bold;
                padding: 10px 20px;
                font-size: 11pt;
                font-family: 'JetBrains Mono', monospace;
            }
            QPushButton:hover {
                background: rgba(59, 130, 246, 0.5);
                border-color: #3b82f6;
            }
        """)
        
        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(40, 40, 40, 40)
        main_layout.setSpacing(30)
        
        # Header
        header = QLabel("🔴 RedByte HIL Verifier Suite")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.setFont(QFont('JetBrains Mono', 28, QFont.Weight.Bold))
        header.setStyleSheet("color: #ef4444;")
        main_layout.addWidget(header)
        
        # Subtitle
        subtitle = QLabel("Select Your Application")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setFont(QFont('JetBrains Mono', 14))
        subtitle.setStyleSheet("color: #94a3b8; margin-bottom: 20px;")
        main_layout.addWidget(subtitle)
        
        # App cards grid
        grid = QGridLayout()
        grid.setSpacing(20)
        grid.setContentsMargins(20, 20, 20, 20)
        
        # App definitions
        apps = [
            {
                'name': 'RedByte Diagnostics',
                'id': 'diagnostics',
                'accent': '#10b981',
                'icon': '🟩',
                'desc': 'Live Ops + Fault Injection',
                'launcher': 'launch_diagnostics.py'
            },
            {
                'name': 'RedByte Replay Studio',
                'id': 'replay',
                'accent': '#06b6d4',
                'icon': '🔵',
                'desc': 'Timeline Playback & Review',
                'launcher': 'launch_replay.py'
            },
            {
                'name': 'RedByte Compliance Lab',
                'id': 'compliance',
                'accent': '#8b5cf6',
                'icon': '🟪',
                'desc': 'Standards & Scoring',
                'launcher': 'launch_compliance.py'
            },
            {
                'name': 'RedByte Insight Studio',
                'id': 'insights',
                'accent': '#f59e0b',
                'icon': '🟨',
                'desc': 'AI Cognitive Analysis',
                'launcher': 'launch_insights.py'
            },
            {
                'name': 'RedByte Signal Sculptor',
                'id': 'sculptor',
                'accent': '#f97316',
                'icon': '🟧',
                'desc': 'Live Waveform Editing',
                'launcher': 'launch_sculptor.py'
            }
        ]
        
        # Create cards in grid layout
        for idx, app in enumerate(apps):
            card = AppCard(
                app_name=app['name'],
                app_id=app['id'],
                accent_color=app['accent'],
                icon=app['icon'],
                description=app['desc'],
                launcher_script=app['launcher'],
                mock_mode=self.mock_mode,
            )
            row = idx // 3
            col = idx % 3
            grid.addWidget(card, row, col, Qt.AlignmentFlag.AlignCenter)
        
        main_layout.addLayout(grid)
        main_layout.addStretch()
        
        # Footer buttons
        footer_layout = QHBoxLayout()
        footer_layout.setSpacing(12)
        
        btn_legacy = QPushButton("🔧 Legacy Demo")
        btn_legacy.clicked.connect(self.launch_legacy)
        footer_layout.addWidget(btn_legacy)
        
        btn_docs = QPushButton("📚 Documentation")
        btn_docs.clicked.connect(self.open_docs)
        footer_layout.addWidget(btn_docs)
        
        btn_exit = QPushButton("❌ Exit")
        btn_exit.clicked.connect(self.close)
        footer_layout.addWidget(btn_exit)
        
        main_layout.addLayout(footer_layout)
    
    def launch_legacy(self):
        """Launch original monolithic demo"""
        legacy_path = Path(__file__).parent.parent / 'src' / 'main.py'
        if legacy_path.exists():
            # Launch the legacy app with the project root as working dir so imports like `ui` resolve
            subprocess.Popen([sys.executable, str(legacy_path)], cwd=str(project_root))
    
    def open_docs(self):
        """Open documentation"""
        docs_path = Path(__file__).parent.parent / 'docs' / 'index.md'
        if docs_path.exists():
            import webbrowser
            webbrowser.open_new_tab('file://' + str(docs_path.resolve()))


def main():
    import argparse
    parser = argparse.ArgumentParser(description="RedByte HIL Suite Launcher")
    parser.add_argument(
        "--mock", action="store_true",
        help="Launch child apps in mock/demo mode (no hardware required)"
    )
    parser.add_argument(
        "--app", type=str, default=None,
        choices=["diagnostics", "replay", "compliance", "insights", "sculptor"],
        help="Directly launch a specific app (skips selector)"
    )
    parser.add_argument(
        "--load", type=str, default=None,
        help="Path to a session JSON to auto-load in the launched app"
    )
    args = parser.parse_args()

    app = QApplication(sys.argv)

    if args.app:
        # Direct launch of a specific sub-app
        launcher_map = {
            "diagnostics": "launch_diagnostics.py",
            "replay":      "launch_replay.py",
            "compliance":  "launch_compliance.py",
            "insights":    "launch_insights.py",
            "sculptor":    "launch_sculptor.py",
        }
        script = launcher_map.get(args.app)
        if script:
            launcher_path = Path(__file__).parent / 'launchers' / script
            cmd = [sys.executable, str(launcher_path)]
            if args.mock:
                cmd.append('--mock')
            if args.load:
                cmd.extend(['--load', args.load])
            subprocess.Popen(cmd, cwd=str(project_root))
            sys.exit(0)

    launcher = RedByteLauncher(mock_mode=args.mock)
    launcher.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
