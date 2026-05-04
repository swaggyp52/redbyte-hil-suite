@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "BOOTSTRAP_DIR=%~dp0"
for %%I in ("%BOOTSTRAP_DIR%..") do set "PROJECT_ROOT=%%~fI"
set "VENV_DIR=%PROJECT_ROOT%\.venv"
set "VENV_PYTHON=%VENV_DIR%\Scripts\python.exe"
set "RUNTIME_REQ=%PROJECT_ROOT%\requirements.txt"
set "DEV_REQ=%PROJECT_ROOT%\requirements-dev.txt"
set "PACKAGE_SELF_CHECK=%PROJECT_ROOT%\scripts\package_self_check.py"
set "PYTHON_BOOTSTRAP_VERSION=3.12.10"
set "PYTHON_INSTALLER_DIR=%TEMP%\redbyte-python-bootstrap"
set "PYTHON_INSTALLER_BASENAME="
set "PYTHON_INSTALLER_URL="
set "PYTHON_INSTALLER_SHA256="
set "INSTALL_DEV=0"

call :configure_python_installer
if errorlevel 1 exit /b 1
set "PYTHON_INSTALLER_PATH=%PYTHON_INSTALLER_DIR%\%PYTHON_INSTALLER_BASENAME%"

:parse_args
if "%~1"=="" goto args_done
if /i "%~1"=="--dev" set "INSTALL_DEV=1"
shift
goto parse_args

:args_done
if not exist "%RUNTIME_REQ%" (
    echo [ERROR] Missing requirements.txt at "%RUNTIME_REQ%".
    exit /b 1
)

call :ensure_runtime_python
if errorlevel 1 exit /b 1

set "REDBYTE_PYTHON=%VENV_PYTHON%"
set "PYTHONPATH=%PROJECT_ROOT%;%PROJECT_ROOT%\src;%PYTHONPATH%"

set "NEEDS_RUNTIME_INSTALL=0"
call :requirements_current
if errorlevel 1 (
    set "NEEDS_RUNTIME_INSTALL=1"
) else (
    call :runtime_self_check
    if errorlevel 1 set "NEEDS_RUNTIME_INSTALL=1"
)

if "!NEEDS_RUNTIME_INSTALL!"=="1" (
    call :install_runtime
    if errorlevel 1 exit /b 1
    call :runtime_self_check
    if errorlevel 1 (
        echo [ERROR] Runtime validation failed after dependency installation.
        exit /b 1
    )
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
    set "REDBYTE_PYTHON=%VENV_PYTHON%"
    set "PYTHONPATH=%PYTHONPATH%"
    set "PROJECT_ROOT=%PROJECT_ROOT%"
)
exit /b 0

:ensure_runtime_python
if exist "%VENV_PYTHON%" (
    call :python_path_is_supported "%VENV_PYTHON%"
    if not errorlevel 1 exit /b 0
    echo [setup] Existing .venv is stale or uses an unsupported Python. Rebuilding it...
    call :remove_stale_venv
    if errorlevel 1 exit /b 1
)

call :resolve_base_python
if errorlevel 1 exit /b 1

echo [setup] Creating virtual environment in .venv...
if /i "!BASE_PYTHON_KIND!"=="path" (
    "!BASE_PYTHON!" -m venv "%VENV_DIR%"
) else (
    !BASE_PYTHON! -m venv "%VENV_DIR%"
)
if errorlevel 1 (
    echo [ERROR] Could not create .venv.
    exit /b 1
)

call :python_path_is_supported "%VENV_PYTHON%"
if errorlevel 1 (
    echo [ERROR] The new virtual environment does not contain a supported Python 3.12+ runtime.
    exit /b 1
)
exit /b 0

:resolve_base_python
call :try_python_command "py -3.12"
if not errorlevel 1 exit /b 0

call :try_python_command "python"
if not errorlevel 1 exit /b 0

call :try_python_path "%LocalAppData%\Programs\Python\Python312\python.exe"
if not errorlevel 1 exit /b 0

call :try_python_path "%LocalAppData%\Programs\Python\Python313\python.exe"
if not errorlevel 1 exit /b 0

call :try_python_command "py -3"
if not errorlevel 1 exit /b 0

echo [setup] Python 3.12+ was not found. Installing local Python for this user...
call :install_python_for_current_user
if errorlevel 1 exit /b 1

call :try_python_path "%LocalAppData%\Programs\Python\Python312\python.exe"
if not errorlevel 1 exit /b 0

call :try_python_path "%LocalAppData%\Programs\Python\Python313\python.exe"
if not errorlevel 1 exit /b 0

call :try_python_command "py -3.12"
if not errorlevel 1 exit /b 0

call :try_python_command "python"
if not errorlevel 1 exit /b 0

call :try_python_command "py -3"
if not errorlevel 1 exit /b 0

echo [ERROR] Python installation finished, but python.exe could not be located.
echo         Rerun install.cmd while connected to the internet, install Python 3.12+ manually,
echo         or use a release bundle that already includes Python.
exit /b 1

:try_python_command
%~1 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 12) else 1)" >nul 2>&1
if errorlevel 1 exit /b 1
set "BASE_PYTHON_KIND=command"
set "BASE_PYTHON=%~1"
exit /b 0

:try_python_path
if not exist "%~1" exit /b 1
call :python_path_is_supported "%~1"
if errorlevel 1 exit /b 1
set "BASE_PYTHON_KIND=path"
set "BASE_PYTHON=%~1"
exit /b 0

:python_path_is_supported
if not exist "%~1" exit /b 1
"%~1" -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 12) else 1)" >nul 2>&1
exit /b %errorlevel%

:remove_stale_venv
if not exist "%VENV_DIR%" exit /b 0
rmdir /s /q "%VENV_DIR%" >nul 2>&1
if exist "%VENV_DIR%" (
    echo [ERROR] Could not remove the existing .venv.
    echo         Close any open terminals or apps using it, then rerun install.cmd.
    exit /b 1
)
exit /b 0

:install_python_for_current_user
if not exist "%PYTHON_INSTALLER_DIR%" mkdir "%PYTHON_INSTALLER_DIR%" >nul 2>&1

if exist "%PYTHON_INSTALLER_PATH%" (
    call :validate_python_installer
    if errorlevel 1 (
        echo [setup] Cached Python installer checksum mismatch. Re-downloading...
        del /f /q "%PYTHON_INSTALLER_PATH%" >nul 2>&1
    )
)

if not exist "%PYTHON_INSTALLER_PATH%" (
    echo [setup] Downloading Python %PYTHON_BOOTSTRAP_VERSION% installer...
    powershell -NoProfile -ExecutionPolicy Bypass -Command ^
        "$ProgressPreference = 'SilentlyContinue'; [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri $env:PYTHON_INSTALLER_URL -OutFile $env:PYTHON_INSTALLER_PATH"
    if errorlevel 1 (
        echo [ERROR] Could not download Python %PYTHON_BOOTSTRAP_VERSION%.
        echo         Internet access is required for the first install.
        echo         Connect to the internet and rerun install.cmd, install Python 3.12+ manually,
        echo         or use a release bundle that already includes Python.
        exit /b 1
    )
)

call :validate_python_installer
if errorlevel 1 (
    del /f /q "%PYTHON_INSTALLER_PATH%" >nul 2>&1
    echo [ERROR] Downloaded Python installer failed checksum verification.
    echo         The file may be corrupted or compromised. Rerun install.cmd on a trusted network.
    exit /b 1
)

echo [setup] Installing Python %PYTHON_BOOTSTRAP_VERSION% for this user...
"%PYTHON_INSTALLER_PATH%" /quiet InstallAllUsers=0 PrependPath=1 Include_pip=1 Include_launcher=1 Include_test=0 SimpleInstall=1
set "PYTHON_INSTALL_EXIT=%ERRORLEVEL%"
if not "%PYTHON_INSTALL_EXIT%"=="0" (
    echo [ERROR] Python installer exited with code %PYTHON_INSTALL_EXIT%.
    echo         Rerun install.cmd while connected to the internet, install Python 3.12+ manually,
    echo         or use a release bundle that already includes Python.
    exit /b 1
)
exit /b 0

:configure_python_installer
set "BOOTSTRAP_ARCH=%PROCESSOR_ARCHITECTURE%"
if defined PROCESSOR_ARCHITEW6432 set "BOOTSTRAP_ARCH=%PROCESSOR_ARCHITEW6432%"

if /i "%BOOTSTRAP_ARCH%"=="ARM64" (
    set "PYTHON_INSTALLER_BASENAME=python-%PYTHON_BOOTSTRAP_VERSION%-arm64.exe"
    set "PYTHON_INSTALLER_URL=https://www.python.org/ftp/python/%PYTHON_BOOTSTRAP_VERSION%/python-%PYTHON_BOOTSTRAP_VERSION%-arm64.exe"
    set "PYTHON_INSTALLER_SHA256=377ac8fd478987940088e879441e702a71b53164d2a1e6f1d51ff77a7e470258"
    exit /b 0
)

if /i "%BOOTSTRAP_ARCH%"=="AMD64" (
    set "PYTHON_INSTALLER_BASENAME=python-%PYTHON_BOOTSTRAP_VERSION%-amd64.exe"
    set "PYTHON_INSTALLER_URL=https://www.python.org/ftp/python/%PYTHON_BOOTSTRAP_VERSION%/python-%PYTHON_BOOTSTRAP_VERSION%-amd64.exe"
    set "PYTHON_INSTALLER_SHA256=67b5635e80ea51072b87941312d00ec8927c4db9ba18938f7ad2d27b328b95fb"
    exit /b 0
)

echo [ERROR] This installer currently supports Windows x64 and ARM64 only.
exit /b 1

:validate_python_installer
if not exist "%PYTHON_INSTALLER_PATH%" exit /b 1
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "$expected = $env:PYTHON_INSTALLER_SHA256.ToUpperInvariant(); $actual = (Get-FileHash -Path $env:PYTHON_INSTALLER_PATH -Algorithm SHA256).Hash.ToUpperInvariant(); exit ([int]($actual -ne $expected))" >nul 2>&1
exit /b %errorlevel%

:runtime_self_check
if not exist "%PACKAGE_SELF_CHECK%" exit /b 0
"%REDBYTE_PYTHON%" "%PACKAGE_SELF_CHECK%" --mode runtime --quiet
exit /b %errorlevel%

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
"%REDBYTE_PYTHON%" -m pip install --upgrade pip setuptools wheel
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
