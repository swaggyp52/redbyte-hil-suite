import sys
import logging
import os
import pyqtgraph as pg
from ui.style import get_global_stylesheet
from ui.splash_screen import RotorSplashScreen
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer
from ui.main_window import MainWindow

# Config logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    """Main entry point for the gfm_hil_suite application."""
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--demo", action="store_true", help="Start in Demo Mode")
    parser.add_argument("--autoplay", action="store_true", help="Run demo script on start")
    args = parser.parse_args()
    env_demo = os.getenv("DEMO_MODE", "0") == "1"
    env_autoplay = os.getenv("DEMO_AUTOPLAY", "0") == "1"

    logger.info("Starting hil-verifier-suite...")
    app = QApplication(sys.argv)
    app.setApplicationName("HIL Verifier Suite")

    # Show animated splash screen with rotor
    splash = RotorSplashScreen()
    splash.show()
    app.processEvents()  # Ensure splash is rendered

    pg.setConfigOptions(useOpenGL=True, antialias=True, background='#0f1115', foreground='#e6e9ef')

    window = MainWindow()
    if args.demo or env_demo:
        window.act_demo.blockSignals(True)
        window.act_demo.setChecked(True)
        window.act_demo.blockSignals(False)
        window._toggle_demo_mode(True)
        if args.autoplay or env_autoplay:
            pass
        
    # Close splash after 2 seconds with smooth finish
    QTimer.singleShot(2000, lambda: splash.finish_animation(window))
    window.show()
    
    # Apply stylesheet AFTER window is shown to prevent style resets
    app.setStyleSheet(get_global_stylesheet())

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
