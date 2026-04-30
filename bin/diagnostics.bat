@echo off
:: Quick Launch - VSM Evidence Workbench Diagnostics (demo adapter mode)

cd /d "%~dp0.."
call scripts\bootstrap.cmd
if errorlevel 1 (
    echo.
    echo [ERROR] Startup setup failed.
    pause
    exit /b 1
)
"%REDBYTE_PYTHON%" src\launchers\launch_diagnostics.py %*
if errorlevel 1 pause
