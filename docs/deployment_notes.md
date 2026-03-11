# Deployment Notes - HIL Verifier Suite

> This document is for lab-PC deployment with hardware attached. For clean-clone demo setup and evaluation validation, use [README.md](../README.md) and [FRESH_MACHINE_SETUP.md](FRESH_MACHINE_SETUP.md).

**Version**: 2.0
**Target**: Lab PC (Windows 10/11)

## Prerequisites

1. **Python 3.12.x**: Ensure the supported runtime is available in PATH.
2. **Drivers**: Install FTDI/Silicon Labs drivers for the HIL UART bridge.
3. **Dependencies**:
   - Demo/evaluation machine: `pip install -e ".[dev]"`
   - Runtime-only lab machine: `pip install -r requirements_clean.txt`

## Hardware Setup

1. Connect the USB-UART cable to the lab PC.
2. Identify the COM port (for example `COM3`).
3. Update `config/system_config.json` if the port differs from the default.

## Verification

1. Optional suite smoke check: run `bin\launch_redbyte.bat`.
2. Hardware-attached workflow: run `python src\launchers\launch_diagnostics.py`.
3. Check the status bar: it should show the active serial connection.
4. Verify 3-phase signals appear on the scope.
5. If hardware is unavailable, use `python src\redbyte_launcher.py --mock` for demo validation.
