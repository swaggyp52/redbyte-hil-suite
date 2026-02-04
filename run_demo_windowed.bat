@echo off
REM Launch GFM HIL Demo in WINDOWED mode (not fullscreen)
REM This makes it easier to test and close
echo ====================================================
echo   GFM HIL VERIFIER SUITE - WINDOWED DEMO
echo ====================================================
echo.
echo [*] Starting demo in windowed mode...
echo [?] Use ESC or Alt+F4 to close
echo [?] Click RUN button to start telemetry stream
echo [?] Simulation controls: RUN / PAUSE / RESUME / STOP
echo.

cd /d "%~dp0"
set PYTHONPATH=.
.venv\Scripts\python.exe src\main.py --demo --windowed

pause
