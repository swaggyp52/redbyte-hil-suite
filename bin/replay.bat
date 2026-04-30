@echo off
:: Quick Launch - VSM Evidence Workbench Replay Studio

cd /d "%~dp0.."
call scripts\bootstrap.cmd
if errorlevel 1 (
    echo.
    echo [ERROR] Startup setup failed.
    pause
    exit /b 1
)
"%REDBYTE_PYTHON%" src\launchers\launch_replay.py %*
if errorlevel 1 pause
