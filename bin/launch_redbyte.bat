@echo off
:: VSM Evidence Workbench — App Selector Launcher

echo.
echo ========================================
echo   VSM Evidence Workbench
echo ========================================
echo.

cd /d "%~dp0.."

python src\redbyte_launcher.py

if errorlevel 1 (
    echo.
    echo [ERROR] Failed to launch VSM Evidence Workbench
    echo Check that Python and PyQt6 are installed
    pause
)
