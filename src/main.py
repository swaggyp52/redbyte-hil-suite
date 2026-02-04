import sys
import logging
import os
import pyqtgraph as pg
from ui.style import get_global_stylesheet
from ui.splash_screen import RotorSplashScreen
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer
from ui.main_window import MainWindow
from src.opengl_check import check_opengl_available

# Config logging (will be reconfigured based on --debug flag)
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
    parser.add_argument("--debug", action="store_true", help="Enable debug logging (verbose output)")
    parser.add_argument("--no-3d", action="store_true", help="Disable 3D view (for machines without OpenGL)")
    parser.add_argument("--windowed", action="store_true", help="Skip fullscreen mode (demo stays in window)")
    args = parser.parse_args()
    env_demo = os.getenv("DEMO_MODE", "0") == "1"
    env_autoplay = os.getenv("DEMO_AUTOPLAY", "0") == "1"
    env_windowed = os.getenv("WINDOWED", "0") == "1"

    # Reconfigure logging if debug mode enabled
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.info("Debug logging enabled")

    logger.info("Starting hil-verifier-suite...")
    
    # Check OpenGL availability early
    if not args.no_3d:
        opengl_ok, opengl_error = check_opengl_available()
        if not opengl_ok:
            logger.warning(f"OpenGL check failed: {opengl_error}")
            logger.info("3D view will be disabled. Use --no-3d to suppress this check.")
        else:
            logger.info("OpenGL check passed")
    app = QApplication(sys.argv)
    app.setApplicationName("HIL Verifier Suite")

    # Show animated splash screen with rotor
    splash = RotorSplashScreen()
    splash.show()
    app.processEvents()  # Ensure splash is rendered

    # Configure pyqtgraph - disable OpenGL if requested or unavailable
    use_opengl = not args.no_3d and opengl_ok
    pg.setConfigOptions(useOpenGL=use_opengl, antialias=True, background='#0f1115', foreground='#e6e9ef')
    if not use_opengl:
        logger.info("pyqtgraph OpenGL acceleration disabled")

    window = MainWindow()
    if args.demo or env_demo:
        window.act_demo.blockSignals(True)
        window.act_demo.setChecked(True)
        window.act_demo.blockSignals(False)
        # Pass windowed flag to demo mode
        window.windowed_mode = args.windowed or env_windowed
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
