@echo off
:: RedByte Suite Launcher
:: Launch the unified RedByte application selector

echo.
echo ========================================
echo   RedByte HIL Verifier Suite
echo ========================================
echo.

cd /d "%~dp0.."

python src\redbyte_launcher.py

if errorlevel 1 (
    echo.
    echo [ERROR] Failed to launch RedByte Suite
    echo Check that Python and PyQt6 are installed
    pause
)
