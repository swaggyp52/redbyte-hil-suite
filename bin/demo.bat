@echo off
cd /d "%~dp0.."
call scripts\bootstrap.cmd
if errorlevel 1 (
    echo.
    echo [ERROR] Startup setup failed.
    pause
    exit /b 1
)
echo Starting RedByte GFM HIL Suite (Demo Mode)...
set "DEMO_MODE=1"
set "DEMO_AUTOPLAY=1"
"%REDBYTE_PYTHON%" run.py --demo %*
if errorlevel 1 pause
