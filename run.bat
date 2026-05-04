@echo off
setlocal EnableExtensions

cd /d "%~dp0"
set "PROJECT_ROOT=%CD%"
set "VENV_PYTHON=%PROJECT_ROOT%\.venv\Scripts\python.exe"
set "PYTHONPATH=%PROJECT_ROOT%;%PROJECT_ROOT%\src;%PYTHONPATH%"

if not exist "%VENV_PYTHON%" (
    echo [ERROR] Project environment not found.
    echo         First run install.cmd.
    pause
    exit /b 1
)

"%VENV_PYTHON%" scripts\package_self_check.py --mode launch
if errorlevel 1 (
    echo.
    echo [ERROR] Launch checks failed. Rerun install.cmd to repair the package.
    pause
    exit /b 1
)

"%VENV_PYTHON%" run.py %*
if errorlevel 1 (
    echo.
    echo [ERROR] The application exited with an error.
    pause
    exit /b 1
)

endlocal
