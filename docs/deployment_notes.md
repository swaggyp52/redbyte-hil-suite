# Deployment Notes - HIL Verifier Suite

**Version**: 1.0.0 (Production)
**Target**: Lab PC (Windows 10/11)

## 📋 Prerequisites

1. **Python 3.10+**: Ensure `python` is in PATH.
2. **Drivers**: Install FTDI/Silicon Labs drivers for the HIL UART bridge.
3. **Dependencies**:

    ```bash
    pip install -r requirements.txt
    ```

## 🔌 Hardware Setup

1. Connect USB-UART cable to the Lab PC.
2. Identify COM Port (e.g., `COM3`).
3. Update `config/system_config.json` if port differs from default (`COM3`).

## 🧪 Verification

1. Run `bin\demo.bat` first to verify UI and Graphs load.
2. Close Demo.
3. Run `bin\start.bat`.
4. Check Status Bar: Should say "Connected to COM3".
5. Verify 3-phase signals appear on the Scope.
