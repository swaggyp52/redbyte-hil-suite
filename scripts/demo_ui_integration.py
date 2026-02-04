"""
Quick UI integration demo - shows telemetry watchdog and CSV export in action
"""
import sys
import time
from pathlib import Path
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from ui.main_window import MainWindow


def demo_ui_integration():
    """Launch app and demonstrate new UI features"""
    app = QApplication(sys.argv)
    
    window = MainWindow()
    window.show()
    
    print("\n" + "="*60)
    print("UI INTEGRATION DEMO")
    print("="*60)
    print("\n✅ Telemetry Watchdog: Active")
    print("   - Monitors data health in real-time")
    print("   - Shows stale data warning after 2 seconds")
    print("   - Displays frame rate in toolbar\n")
    
    print("✅ CSV Exporter: Ready")
    print("   - Format selector: Simple | Detailed | Analysis")
    print("   - One-click export from toolbar")
    print("   - Professional metadata and validation\n")
    
    print("✅ Visual Indicators:")
    print("   - Telemetry health label shows live frame rate")
    print("   - Stale data overlay appears when data stops")
    print("   - All controls visible in main toolbar\n")
    
    print("="*60)
    print("DEMO INSTRUCTIONS")
    print("="*60)
    print("1. Look for 📡 Telemetry label in toolbar (shows frame rate)")
    print("2. Export dropdown shows: Simple CSV | Detailed | Analysis")
    print("3. Click 📤 Export CSV to save last session")
    print("4. If telemetry stops, ⚠️ STALE warning appears at top")
    print("="*60)
    print("\nPress Ctrl+C in terminal to exit\n")
    
    # Demo stale indicator after 5 seconds
    def show_stale_demo():
        print("🎬 DEMO: Simulating stale telemetry...")
        window._on_telemetry_stale(2.5)
        
        # Hide after 3 seconds
        QTimer.singleShot(3000, lambda: (
            window._on_telemetry_resumed(),
            print("✅ DEMO: Telemetry resumed")
        ))
    
    QTimer.singleShot(5000, show_stale_demo)
    
    sys.exit(app.exec())


if __name__ == "__main__":
    demo_ui_integration()
