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
    parser.add_argument("--mock", action="store_true", help="Use mock demo input (alias for --demo)")
    parser.add_argument("--autoplay", action="store_true", help="Auto-start demo on launch")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    parser.add_argument("--no-3d", action="store_true", help="Disable 3D view")
    parser.add_argument("--windowed", action="store_true", help="Stay windowed in demo mode")
    parser.add_argument(
        "--port", default="",
        help="Optional serial adapter preview port (future/demo path only; "
             "e.g. COM5, /dev/ttyUSB0). Reads system_config.json if not specified.",
    )
    args = parser.parse_args()

    env_demo = os.getenv("DEMO_MODE", "0") == "1"
    env_windowed = os.getenv("WINDOWED", "0") == "1"

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    logger.info("Starting VSM Evidence Workbench...")

    opengl_ok = False
    if not args.no_3d:
        opengl_ok, opengl_error = check_opengl_available()
        if not opengl_ok:
            logger.warning(f"OpenGL check failed: {opengl_error}. 3D view disabled.")
        else:
            logger.info("OpenGL check passed.")

    app = QApplication(sys.argv)
    app.setApplicationName("VSM Evidence Workbench")

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

    # Resolve optional adapter-preview port: CLI arg > system_config.json > empty.
    live_port = args.port
    if not live_port and not demo:
        try:
            import json as _json
            cfg_path = os.path.join(os.path.dirname(__file__), "..", "config", "system_config.json")
            with open(cfg_path) as _f:
                _cfg = _json.load(_f)
            live_port = _cfg.get("hardware", {}).get("port", "")
        except Exception:
            live_port = ""

    window = AppShell(
        demo_mode=demo,
        mock_mode=mock,
        enable_3d=not args.no_3d and opengl_ok,
        windowed=windowed,
        live_port=live_port,
    )

    QTimer.singleShot(2000, lambda: splash.finish_animation(window))
    window.show()

    # Apply stylesheet AFTER window is shown to avoid rendering artefacts
    app.setStyleSheet(get_global_stylesheet())

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
