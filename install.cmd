@echo off
setlocal EnableExtensions

cd /d "%~dp0"
echo ============================================
echo  VSM Evidence Workbench - Setup
echo ============================================
echo.

call scripts\bootstrap.cmd
if errorlevel 1 (
    echo.
    echo [ERROR] Setup failed. Check the error above.
    pause
    exit /b 1
)

echo [setup] Running package self-check...
"%REDBYTE_PYTHON%" scripts\package_self_check.py --mode install
if errorlevel 1 (
    echo.
    echo [ERROR] Package self-check failed.
    pause
    exit /b 1
)

echo [setup] Running final demo smoke validation...
"%REDBYTE_PYTHON%" scripts\final_demo_smoke.py
if errorlevel 1 (
    echo.
    echo [ERROR] Demo smoke validation failed.
    pause
    exit /b 1
)

if exist scripts\final_gui_state_smoke.py (
    echo [setup] Running GUI-state smoke validation...
    "%REDBYTE_PYTHON%" scripts\final_gui_state_smoke.py
    if errorlevel 1 (
        echo.
        echo [ERROR] GUI-state smoke validation failed.
        pause
        exit /b 1
    )
)

echo.
echo ============================================
echo  Setup complete!
echo.
echo  Next step: double-click run.bat
echo ============================================
pause
