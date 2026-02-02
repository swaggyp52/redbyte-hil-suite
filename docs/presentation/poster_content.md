# Grid-Forming Inverter HIL Telemetry Suite

**Senior Design Project - Gannon University (ECE/Cyber)**

## Problem Statement

Grid-forming inverters (VSM) lack physical inertia, making stability validation critical. Testing on real grids is risky; Hardware-in-the-Loop (HIL) is safer but requires advanced telemetry to visualize and verify control behavior in real-time.

## Solution: "RedByte-HIL"

A custom, desktop-first telemetry platform inspired by RedByte OS.

- **Live Monitoring**: Oscilloscope-style visualization of Voltage, Current, Frequency.
- **Verification**: "Record & Replay" ensures tests are reproducible.
- **Analysis**: Automatic comparison of test runs (RMSE) to validate VSM inertia settings.

## System Architecture

- **Front-End**: Python/PyQt6 (MDI Desktop Shell).
- **Back-End**: Threaded Serial Ingestion (JSON Protocol).
- **Data**: JSON "Data Capsules" for portability.

## Key Results

- **Latency**: <20ms updates via 115200 baud UART.
- **Reliability**: Zero data loss during 1-hour log stress test.
- **Impact**: Enabled safe tuning of Virtual Inertia constants before hardware deployment.

## Future Work

- Automated OPAL-RT scenario injection.
- Cloud-based telemetry sharing.
