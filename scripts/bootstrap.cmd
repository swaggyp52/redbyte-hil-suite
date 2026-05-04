@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "BOOTSTRAP_DIR=%~dp0"
for %%I in ("%BOOTSTRAP_DIR%..") do set "PROJECT_ROOT=%%~fI"
set "VENV_DIR=%PROJECT_ROOT%\.venv"
set "VENV_PYTHON=%VENV_DIR%\Scripts\python.exe"
set "RUNTIME_REQ=%PROJECT_ROOT%\requirements.txt"
set "DEV_REQ=%PROJECT_ROOT%\requirements-dev.txt"
set "INSTALL_DEV=0"

if /i "%~1"=="--dev" set "INSTALL_DEV=1"

if not exist "%RUNTIME_REQ%" (
    echo [ERROR] Missing requirements.txt at "%RUNTIME_REQ%".
    exit /b 1
)

if not exist "%VENV_PYTHON%" (
    call :find_python
    if errorlevel 1 exit /b 1

    echo [setup] Creating virtual environment in .venv...
    !BASE_PYTHON! -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo [ERROR] Could not create .venv.
        exit /b 1
    )
)

set "REDBYTE_PYTHON=%VENV_PYTHON%"
set "PYTHONPATH=%PROJECT_ROOT%;%PROJECT_ROOT%\src;%PYTHONPATH%"

"%REDBYTE_PYTHON%" -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 12) else 1)" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] RedByte HIL Suite requires Python 3.12 or newer.
    echo         Delete .venv and rerun after installing Python 3.12+ if this environment is stale.
    exit /b 1
)

call :requirements_current
if errorlevel 1 (
    call :install_runtime
    if errorlevel 1 exit /b 1
)

if "%INSTALL_DEV%"=="1" (
    if not exist "%DEV_REQ%" (
        echo [ERROR] Missing requirements-dev.txt at "%DEV_REQ%".
        exit /b 1
    )

    call :dev_requirements_current
    if errorlevel 1 (
        call :install_dev
        if errorlevel 1 exit /b 1
    )
)

endlocal & (
    set "REDBYTE_PYTHON=%REDBYTE_PYTHON%"
    set "PYTHONPATH=%PYTHONPATH%"
    set "PROJECT_ROOT=%PROJECT_ROOT%"
)
exit /b 0

:find_python
py -3.12 -c "import sys" >nul 2>&1
if not errorlevel 1 (
    set "BASE_PYTHON=py -3.12"
    exit /b 0
)

py -3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 12) else 1)" >nul 2>&1
if not errorlevel 1 (
    set "BASE_PYTHON=py -3"
    exit /b 0
)

python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 12) else 1)" >nul 2>&1
if not errorlevel 1 (
    set "BASE_PYTHON=python"
    exit /b 0
)

echo [ERROR] Python 3.12+ was not found.
echo         Install Python from https://www.python.org/downloads/ and enable "Add python.exe to PATH".
exit /b 1

:requirements_current
if not exist "%VENV_DIR%\.runtime-deps.stamp" exit /b 1
powershell -NoProfile -ExecutionPolicy Bypass -Command "exit ([int]((Get-Item $env:RUNTIME_REQ).LastWriteTimeUtc -gt (Get-Item (Join-Path $env:VENV_DIR '.runtime-deps.stamp')).LastWriteTimeUtc))" >nul 2>&1
exit /b %errorlevel%

:dev_requirements_current
if not exist "%VENV_DIR%\.dev-deps.stamp" exit /b 1
powershell -NoProfile -ExecutionPolicy Bypass -Command "exit ([int]((Get-Item $env:DEV_REQ).LastWriteTimeUtc -gt (Get-Item (Join-Path $env:VENV_DIR '.dev-deps.stamp')).LastWriteTimeUtc))" >nul 2>&1
exit /b %errorlevel%

:install_runtime
echo [setup] Installing runtime dependencies...
"%REDBYTE_PYTHON%" -m ensurepip --upgrade >nul 2>&1
"%REDBYTE_PYTHON%" -m pip install --upgrade pip
if errorlevel 1 exit /b 1
"%REDBYTE_PYTHON%" -m pip install -r "%RUNTIME_REQ%"
if errorlevel 1 (
    echo [ERROR] Runtime dependency install failed.
    exit /b 1
)
powershell -NoProfile -ExecutionPolicy Bypass -Command "New-Item -ItemType File -Force -Path (Join-Path $env:VENV_DIR '.runtime-deps.stamp') | Out-Null" >nul 2>&1
exit /b 0

:install_dev
echo [setup] Installing test/development dependencies...
"%REDBYTE_PYTHON%" -m pip install -r "%DEV_REQ%"
if errorlevel 1 (
    echo [ERROR] Test/development dependency install failed.
    exit /b 1
)
powershell -NoProfile -ExecutionPolicy Bypass -Command "New-Item -ItemType File -Force -Path (Join-Path $env:VENV_DIR '.dev-deps.stamp') | Out-Null" >nul 2>&1
exit /b 0
