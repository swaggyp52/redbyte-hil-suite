import sys
import logging
import os
import pyqtgraph as pg
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer
from ui.style import get_global_stylesheet
from ui.splash_screen import RotorSplashScreen
from ui.app_shell import AppShell
from src.opengl_check import check_opengl_available

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--demo", action="store_true", help="Start in Demo Mode")
    parser.add_argument("--mock", action="store_true", help="Use mock telemetry (alias for demo)")
    parser.add_argument("--autoplay", action="store_true", help="Auto-start demo on launch")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    parser.add_argument("--no-3d", action="store_true", help="Disable 3D view")
    parser.add_argument("--windowed", action="store_true", help="Stay windowed in demo mode")
    args = parser.parse_args()

    env_demo = os.getenv("DEMO_MODE", "0") == "1"
    env_windowed = os.getenv("WINDOWED", "0") == "1"

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    logger.info("Starting RedByte GFM HIL Suite...")

    opengl_ok = False
    if not args.no_3d:
        opengl_ok, opengl_error = check_opengl_available()
        if not opengl_ok:
            logger.warning(f"OpenGL check failed: {opengl_error}. 3D view disabled.")
        else:
            logger.info("OpenGL check passed.")

    app = QApplication(sys.argv)
    app.setApplicationName("RedByte GFM HIL Suite")

    splash = RotorSplashScreen()
    splash.show()
    app.processEvents()

    use_opengl = not args.no_3d and opengl_ok
    pg.setConfigOptions(
        useOpenGL=use_opengl, antialias=True,
        background='#0f1115', foreground='#e6e9ef'
    )

    demo = args.demo or args.mock or args.autoplay or env_demo
    mock = args.demo or args.mock or args.autoplay or env_demo
    windowed = args.windowed or env_windowed

    window = AppShell(
        demo_mode=demo,
        mock_mode=mock,
        enable_3d=not args.no_3d and opengl_ok,
        windowed=windowed,
    )

    QTimer.singleShot(2000, lambda: splash.finish_animation(window))
    window.show()

    app.setStyleSheet(get_global_stylesheet())

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
