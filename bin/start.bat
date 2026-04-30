@echo off
cd /d "%~dp0.."
call scripts\bootstrap.cmd
if errorlevel 1 (
    echo.
    echo [ERROR] Startup setup failed.
    pause
    exit /b 1
)
echo Starting RedByte GFM HIL Suite...
"%REDBYTE_PYTHON%" run.py %*
if errorlevel 1 pause
