# Hardware Integration Guide

**RedByte HIL Verifier Suite**  
**Hardware Interface Documentation**

---

## 🔌 Overview

The RedByte HIL Suite interfaces with physical HIL testbeds through **UART serial communication**. This document describes the hardware setup, protocol specification, and deployment procedures for connecting to real inverter systems.

---

## 🏭 Supported HIL Platforms

### Current Implementation: Serial/UART

**Status:** ✅ **Fully Operational**

The primary interface is a **microcontroller-based telemetry system** that streams JSON-formatted measurement data over UART.

**Hardware Configuration:**
- **Interface:** USB-UART adapter (FTDI, CH340, CP2102, etc.)
- **Baud Rate:** 115200 bps
- **Data Bits:** 8
- **Parity:** None
- **Stop Bits:** 1
- **Flow Control:** None (software controlled)

**Typical Setup:**
```
Inverter Microcontroller (STM32/ESP32/etc.)
    ↓ (GPIO UART TX)
USB-UART Adapter (FTDI)
    ↓ (USB Cable)
Lab PC (Windows/Linux)
    ↓ (SerialManager)
RedByte Suite Applications
```

### Future Expansion: OPAL-RT/Typhoon HIL

**Status:** ⚠️ **Stub Implementation Only**

The codebase includes `OpalRTAdapter` class with placeholder methods for future integration with high-speed HIL platforms:

- **OPAL-RT OP5707/OP4510:** TCP/UDP-based real-time interface
- **Typhoon HIL 602/604:** Ethernet or USB with vendor SDK
- **dSPACE MicroAutoBox:** CAN/Ethernet interface

**Implementation Path:**
1. Implement `OpalRTAdapter.connect()` with platform SDK
2. Override `read_frame()` to parse vendor-specific data format
3. Override `write_command()` to send control signals
4. Test with platform's API in demo mode

**Note:** These adapters are NOT IMPLEMENTED in v2.0. Current deployment uses Serial only.

---

## 📡 Serial Communication Protocol

### Frame Format

**JSON Line-Delimited Protocol:**

Each frame is a single-line JSON object terminated by newline (`\n`):

```json
{"v_an": 120.5, "v_bn": 119.8, "v_cn": 121.2, "i_a": 8.3, "i_b": 8.1, "i_c": 8.2, "freq": 60.02, "p_mech": 2950, "ts": 1234567890.123}
```

### Required Fields

| Field | Type | Unit | Description |
|-------|------|------|-------------|
| `v_an` | float | Volts RMS | Phase A to Neutral voltage |
| `v_bn` | float | Volts RMS | Phase B to Neutral voltage |
| `v_cn` | float | Volts RMS | Phase C to Neutral voltage |
| `i_a` | float | Amps RMS | Phase A current |
| `i_b` | float | Amps RMS | Phase B current |
| `i_c` | float | Amps RMS | Phase C current |
| `freq` | float | Hz | Instantaneous frequency (PLL output) |
| `p_mech` | float | Watts | Mechanical power (or electrical power output) |
| `ts` | float | seconds | Unix timestamp (optional, auto-generated if missing) |

### Optional Fields

| Field | Type | Description |
|-------|------|-------------|
| `angle` | float | Rotor angle in radians (for 3D visualization override) |
| `thd_v` | float | Total Harmonic Distortion for voltage (pre-calculated) |
| `thd_i` | float | Total Harmonic Distortion for current |
| `status` | string | System status message ("NORMAL", "FAULT", etc.) |

### Example Frames

**Normal Operation:**
```json
{"v_an": 120.0, "v_bn": 120.0, "v_cn": 120.0, "i_a": 10.0, "i_b": 10.0, "i_c": 10.0, "freq": 60.0, "p_mech": 3000}
```

**Voltage Sag on Phase A:**
```json
{"v_an": 60.0, "v_bn": 120.0, "v_cn": 120.0, "i_a": 12.0, "i_b": 10.0, "i_c": 10.0, "freq": 59.8, "p_mech": 2800}
```

**Frequency Drift:**
```json
{"v_an": 120.0, "v_bn": 120.0, "v_cn": 120.0, "i_a": 10.0, "i_b": 10.0, "i_c": 10.0, "freq": 58.5, "p_mech": 3000}
```

### Frame Rate

**Recommended:** 20-50 Hz (one frame every 20-50ms)

- Too slow (<10 Hz): Waveform display will appear choppy
- Too fast (>100 Hz): Potential buffer overflows, UI lag
- Optimal: 20-30 Hz provides smooth real-time visualization without overwhelming the UI thread

---

## 🛠️ Microcontroller Firmware Requirements

If you're building the telemetry firmware for the inverter microcontroller:

### Firmware Checklist

1. **Measure Phase Voltages:**
   - Use ADCs with voltage dividers to sample `v_an`, `v_bn`, `v_cn`
   - Apply RMS calculation (sliding window or cycle-based)
   - Scale to actual voltage (e.g., 120V nominal)

2. **Measure Phase Currents:**
   - Use current sensors (Hall effect, shunt resistors + diff amp)
   - Apply RMS calculation
   - Scale to actual current (Amps)

3. **Calculate Frequency:**
   - Zero-crossing detection or PLL output
   - Update every cycle or every few cycles

4. **Calculate Power:**
   - Instantaneous P = V * I * cos(φ) for each phase
   - Sum for total power output

5. **Format JSON:**
   - Use lightweight JSON library (e.g., cJSON, ArduinoJson)
   - Construct single-line JSON string
   - Append newline `\n`

6. **Transmit via UART:**
   - Configure UART to 115200 baud
   - Send JSON frame every 20-50ms
   - Do NOT buffer multiple frames (line-delimited, not batched)

### Example Firmware Pseudocode

```c
void loop() {
    // Measure signals (every 20ms = 50 Hz)
    float v_an = measure_voltage_A();
    float v_bn = measure_voltage_B();
    float v_cn = measure_voltage_C();
    float i_a = measure_current_A();
    float i_b = measure_current_B();
    float i_c = measure_current_C();
    float freq = calculate_frequency();
    float power = calculate_power(v_an, v_bn, v_cn, i_a, i_b, i_c);
    
    // Format JSON
    char buffer[256];
    snprintf(buffer, sizeof(buffer),
        "{\"v_an\":%.2f,\"v_bn\":%.2f,\"v_cn\":%.2f,"
        "\"i_a\":%.2f,\"i_b\":%.2f,\"i_c\":%.2f,"
        "\"freq\":%.2f,\"p_mech\":%.0f}\n",
        v_an, v_bn, v_cn, i_a, i_b, i_c, freq, power);
    
    // Transmit
    uart_send(buffer);
    
    delay(20); // 50 Hz update rate
}
```

---

## 🖥️ PC Configuration

### Windows Setup

1. **Install USB-UART Drivers:**
   - FTDI: Download from [ftdichip.com](https://ftdichip.com/drivers/)
   - CH340: Usually auto-detected by Windows 10/11
   - Verify in Device Manager (Ports section)

2. **Identify COM Port:**
   - Open Device Manager → Ports (COM & LPT)
   - Note the COM port number (e.g., COM3, COM5)

3. **Configure RedByte Suite:**
   - Edit `config/system_config.json`
   - Set `"serial_port": "COM3"` (replace with your port)
   - Set `"baud_rate": 115200`

4. **Launch Diagnostics:**
   ```cmd
   bin\diagnostics.bat
   ```
   - Status bar should show **"CONNECTED"** in green
   - If red "DISCONNECTED", check COM port and baud rate

### Linux Setup

1. **Identify Device:**
   ```bash
   ls /dev/ttyUSB*
   # or
   ls /dev/ttyACM*
   ```

2. **Set Permissions:**
   ```bash
   sudo usermod -a -G dialout $USER
   # Log out and log back in
   ```

3. **Configure RedByte Suite:**
   - Edit `config/system_config.json`
   - Set `"serial_port": "/dev/ttyUSB0"` (replace with your device)

4. **Launch:**
   ```bash
   python src/launchers/launch_diagnostics.py
   ```

---

## 🔧 Configuration File Reference

**File:** `config/system_config.json`

```json
{
  "serial_port": "COM3",
  "baud_rate": 115200,
  "timeout": 1.0,
  "reconnect_interval": 5.0,
  "channel_mapping": {
    "v_an": "v_an",
    "v_bn": "v_bn",
    "v_cn": "v_cn",
    "i_a": "i_a",
    "i_b": "i_b",
    "i_c": "i_c",
    "freq": "freq",
    "p_mech": "p_mech"
  },
  "thresholds": {
    "v_min": 108.0,
    "v_max": 132.0,
    "freq_min": 59.5,
    "freq_max": 60.5,
    "thd_max": 5.0
  }
}
```

### Key Parameters

- **serial_port:** COM port (Windows) or device path (Linux)
- **baud_rate:** Must match firmware (115200 standard)
- **timeout:** Serial read timeout in seconds (1.0 recommended)
- **reconnect_interval:** Auto-reconnect attempt interval (5.0 seconds)
- **thresholds:** Validation limits for automated diagnostics

---

## 🧪 Testing Without Hardware

### Mock Mode

The suite includes a **DemoAdapter** that generates synthetic telemetry for testing without physical hardware.

**Activate Mock Mode:**
```cmd
bin\diagnostics.bat --mock
```

**What it does:**
- Generates 3-phase sine waves (120V RMS, 60 Hz)
- Simulates realistic noise (±2V, ±0.5A)
- Responds to fault injection commands (voltage sags, frequency shifts)
- Produces same JSON frame format as real hardware

**Use Cases:**
- Software development without inverter access
- Capstone demonstrations (safe, repeatable)
- UI testing and screenshot capture
- Training new users on workflow

---

## 🚨 Troubleshooting

### Problem: "DISCONNECTED" Status

**Possible Causes:**
1. Wrong COM port in config
2. UART drivers not installed
3. Baud rate mismatch
4. Cable not connected
5. Firmware not transmitting

**Debug Steps:**
1. Open Device Manager (Windows) or `dmesg | grep tty` (Linux)
2. Verify COM port exists
3. Try different COM ports if multiple devices present
4. Use serial monitor (PuTTY, CoolTerm) to verify firmware is sending data
5. Check baud rate matches (115200)

### Problem: Garbled Data

**Possible Causes:**
1. Baud rate mismatch
2. Data bits/parity/stop bits incorrect
3. Electrical noise on UART line
4. Buffer overflow (frames sent too fast)

**Debug Steps:**
1. Verify baud rate = 115200 on both ends
2. Check UART config (8N1: 8 data bits, No parity, 1 stop bit)
3. Use shielded USB cable
4. Reduce firmware transmit rate to 20 Hz

### Problem: UI Freezes

**Possible Causes:**
1. Frames sent too fast (>100 Hz)
2. Invalid JSON format crashing parser
3. Qt event loop blocked

**Debug Steps:**
1. Check frame rate (should be 20-50 Hz)
2. Validate JSON format (use jsonlint.com)
3. Enable debug logging in SerialManager
4. Test with `--mock` mode to isolate hardware vs. software issue

### Problem: Missing Channels

**Possible Causes:**
1. Firmware not sending all required fields
2. Channel mapping incorrect in config

**Debug Steps:**
1. Print raw JSON frames to console
2. Verify all fields present: `v_an`, `v_bn`, `v_cn`, `i_a`, `i_b`, `i_c`, `freq`, `p_mech`
3. Check `config/system_config.json` channel mapping

---

## 📋 Deployment Checklist

### Pre-Deployment

- [ ] Verify firmware is transmitting at 20-50 Hz
- [ ] Confirm JSON format matches specification
- [ ] Test with serial monitor (PuTTY/CoolTerm) before connecting RedByte Suite
- [ ] Install USB-UART drivers on target PC
- [ ] Identify correct COM port

### Initial Setup

- [ ] Edit `config/system_config.json` with correct COM port
- [ ] Test connection with `bin\diagnostics.bat`
- [ ] Verify "CONNECTED" status in status bar
- [ ] Confirm waveforms display correctly in Inverter Scope

### Validation

- [ ] Inject test fault (voltage sag) via Fault Injector
- [ ] Verify system responds correctly (voltage drops, recovers)
- [ ] Check Insights Panel logs events
- [ ] Export session to Replay Studio, verify playback works

### Production

- [ ] Configure thresholds in `config/system_config.json`
- [ ] Disable debug logging
- [ ] Create backup of working configuration
- [ ] Document COM port and settings in lab notebook

---

## 🔗 Related Documentation

- **Serial Protocol Implementation:** `src/serial_reader.py` (SerialManager class)
- **IO Adapter Architecture:** `src/io_adapter.py` (SerialAdapter, DemoAdapter)
- **Channel Mapping:** `src/channel_map.py`
- **Configuration Reference:** `config/system_config.json`
- **Deployment Notes:** `deployment_notes.md`

---

## 📞 Support

For hardware integration issues:
1. Check this document first
2. Review `deployment_notes.md` for lab-specific setup
3. Test with `--mock` mode to isolate software vs. hardware problems
4. Consult electrical engineering teammates for firmware questions

**Common Resources:**
- Serial terminal: [PuTTY](https://www.putty.org/), [CoolTerm](https://freeware.the-meiers.org/)
- FTDI drivers: [ftdichip.com](https://ftdichip.com/drivers/)
- JSON validator: [jsonlint.com](https://jsonlint.com/)

---

*Last Updated: February 1, 2026*
