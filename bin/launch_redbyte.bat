@echo off
:: VSM Evidence Workbench — App Selector Launcher

echo.
echo ========================================
echo   VSM Evidence Workbench
echo ========================================
echo.

cd /d "%~dp0.."

call scripts\bootstrap.cmd
if errorlevel 1 (
    echo.
    echo [ERROR] Startup setup failed.
    pause
    exit /b 1
)

"%REDBYTE_PYTHON%" src\redbyte_launcher.py %*

if errorlevel 1 (
    echo.
    echo [ERROR] Failed to launch VSM Evidence Workbench
    echo Check the setup output above for details
    pause
)
