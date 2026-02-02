# RedByte HIL Verifier Suite (v2.0)

![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue)
![PyQt6](https://img.shields.io/badge/UI-PyQt6-41cd52)
![License](https://img.shields.io/badge/license-MIT-green)
![Tests](https://img.shields.io/badge/tests-passing-brightgreen)
![Platform](https://img.shields.io/badge/platform-Windows-lightgrey)

**Modular, Purpose-Built HIL Testing Platform for 3-Phase Grid-Forming Inverters**

> **NEW in v2.0:** Transformed from monolithic demo app into **5 specialized RedByte applications** with distinct visual identities, focused workflows, and seamless cross-app data handoff.

---

## 🎓 Project Background

This is a **senior design capstone project** that demonstrates **Hardware-in-the-Loop (HIL) simulation** for testing three-phase power inverters. The project enables safe, comprehensive validation of grid-forming inverter control algorithms without risking physical equipment.

**The Challenge:** Grid-forming inverters must handle extreme fault conditions (voltage sags, frequency deviations, phase imbalances) while maintaining stability. Testing these scenarios on real grids is dangerous and impractical.

**The Solution:** A HIL testbed where a real inverter interfaces with a simulated electrical environment. This software suite provides the **monitoring, control, and analysis layer** that transforms raw simulation data into actionable insights.

**Project Scope:**
- **Hardware:** 3-phase inverter with Virtual Synchronous Machine (VSM) control algorithm
- **Simulation:** Real-time HIL platform (microcontroller-based with UART telemetry)
- **Software (This Repository):** Professional monitoring, fault injection, and validation suite
- **Team:** Cyber Engineering (software) + Electrical Engineering (hardware/firmware)

**Why "RedByte"?** The software architecture is derived from [RedByte OS](docs/REDBYTE_HERITAGE.md), a prior project featuring windowing systems and modular app frameworks. This heritage enabled rapid development of a sophisticated multi-app suite.

**→ For full project context, see [docs/PROJECT_OVERVIEW.md](docs/PROJECT_OVERVIEW.md)**

---

## 🚀 Application Suite

A professional-grade solution for verifying Grid-Forming (GFM/VSM) inverter control algorithms on HIL testbeds. Each RedByte app serves a specific purpose:

| App | Theme | Purpose |
|-----|-------|---------|
| **Diagnostics** | Emerald `#10b981` | Live signal capture + fault injection |
| **Replay Studio** | Cyan `#06b6d4` | Timeline playback & waveform review |
| **Compliance Lab** | Purple `#8b5cf6` | Automated standards testing & scoring |
| **Insight Studio** | Amber `#f59e0b` | Event clustering & pattern analysis |
| **Signal Sculptor** | Orange `#f97316` | Live waveform editing & filter design |

---

## ⚡ Quick Start

### Prerequisites

- Python 3.9+
- Windows (tested on Windows 10/11)

### Install

```cmd
git clone <repo-url>
cd gfm_hil_suite
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### Launch

```cmd
bin\launch_redbyte.bat          :: Visual app selector (recommended)
bin\diagnostics.bat             :: Live monitoring + fault injection
bin\replay.bat                  :: Timeline playback
bin\compliance.bat              :: Standards validation
bin\insights.bat                :: Event analysis
bin\sculptor.bat                :: Waveform engineering
```

All launchers support `--mock` (simulated serial data) and `--load <path>` (auto-import session context).

```cmd
bin\diagnostics.bat --mock                              :: Demo mode with simulated data
bin\replay.bat --load data\demo_context_fault_sag.json  :: Load a pre-built demo session
```

**→ For detailed workflows, see [docs/QUICK_START_MODULAR.md](docs/QUICK_START_MODULAR.md)**

---

## ✨ Key Features

### Real-Time Monitoring
- **Inverter Scope:** 3-phase waveform plotting (25 Hz refresh, FFT/RMS/THD)
- **Phasor Diagram:** Vector visualization of phase relationships with Hilbert transform
- **3D System View:** Animated rotor showing VSM virtual angle + power flow visualization
- **Insights Panel:** Automatic anomaly detection (THD warnings, frequency drift, phase imbalance)

### Fault Injection & Validation
- **Programmable Scenarios:** Voltage sags, frequency deviations, phase outages
- **Timeline Control:** Schedule faults with precise timing
- **IEEE 1547 Compliance:** Automated LVRT (Low Voltage Ride-Through) testing
- **Pass/Fail Scorecard:** RMSE metrics, recovery time measurement

### Analysis & Replay
- **Timeline Playback:** DVR-like scrubbing through captured sessions
- **Tag System:** Annotate critical moments for review
- **Event Clustering:** Group insights by type (Insight Studio)
- **Session Export/Import:** JSON-based context handoff between apps

### Professional UX
- **5 Themed Apps:** Per-app color schemes aid cognitive organization
- **55+ Tooltips:** Comprehensive UI guidance
- **Keyboard Shortcuts:** Accessible navigation (Ctrl+H for help, Ctrl+Q to quit)
- **Splash Screen Animation:** Professional startup experience

---

## 🏗️ Architecture

```
redbyte_launcher.py (App Selector Card UI)
    |
    |-- launch_diagnostics.py --> DiagnosticsWindow(LauncherBase)
    |     Backends: SerialManager, Recorder, ScenarioController
    |     hil_core: SessionContext, SignalEngine, FaultEngine, InsightEngine
    |     Panels:   System3DView, InverterScope, PhasorView, FaultInjector, InsightsPanel
    |
    |-- launch_replay.py -------> ReplayWindow(LauncherBase)
    |     Backends: SerialManager, Recorder
    |     hil_core: SessionContext
    |     Panels:   ReplayStudio, PhasorView, InsightsPanel
    |
    |-- launch_compliance.py ---> ComplianceWindow(LauncherBase)
    |     Backends: ScenarioController
    |     hil_core: SessionContext
    |     Panels:   ValidationDashboard
    |
    |-- launch_insights.py -----> InsightStudioWindow(LauncherBase)
    |     Backends: (none)
    |     hil_core: SessionContext, InsightEngine
    |     Panels:   InsightsPanel
    |
    +-- launch_sculptor.py -----> SculptorWindow(LauncherBase)
          Backends: SerialManager
          hil_core: SessionContext
          Panels:   SignalSculptor, InverterScope
```

### Two-Layer Backend Design

**Layer 1 -- `src/` Backends** (Qt-based, real-time signals)

| Class | Signal | Purpose |
|-------|--------|---------|
| `SerialManager` | `frame_received(dict)` | UART telemetry ingestion |
| `Recorder` | -- | Session recording to disk |
| `ScenarioController` | `event_triggered(str, dict)` | Fault scenario state machine |

**Layer 2 -- `hil_core/` Engines** (Pure Python, cross-app)

| Class | Purpose |
|-------|---------|
| `SessionContext` | Singleton for cross-app state |
| `SignalEngine` | Circular buffer + FFT/RMS |
| `FaultEngine` | Fault injection state machine |
| `InsightEngine` | Event detection + clustering |

### Cross-App Data Flow

```
Diagnostics --(export_context)--> temp/redbyte_session_replay.json
                                       |
                              Replay / Compliance / Insights
                              (--load flag or toolbar import)
```

Session context files (`.ctx.json`) bundle waveforms, insights, tags, and scenario metadata into a single portable JSON document. See [docs/context_workflow.md](docs/context_workflow.md) for the full specification.

---

## Shared Launcher Base

All 5 launcher windows inherit from `LauncherBase` (`src/launcher_base.py`):

| Feature | Description |
|---------|-------------|
| Geometry persistence | Tracks user panel movements across sessions |
| Overlay notifications | Fade-out overlay messages on context load/export |
| Help overlay | Conditional first-run tips (`?` toggle) |
| Status bar | Live metrics (RMS, THD, mode) when serial connected |
| Tooltips | Per-panel tooltip injection (55+ tooltips) |
| Context export/import | Toolbar buttons for session bundle file dialogs |
| CLI arguments | `--mock` and `--load <path>` flags |

---

## Demo Sessions

Pre-built demo context files are included in `data/` for quick evaluation:

| File | Scenario | Description |
|------|----------|-------------|
| `demo_context_baseline.json` | Normal operation | 3-phase at 120V/60Hz, clean waveforms |
| `demo_context_fault_sag.json` | Voltage sag fault | 3-phase sag to 40%, THD spike, frequency dip, recovery |

Load a demo session:
```cmd
bin\replay.bat --load data\demo_context_fault_sag.json
bin\insights.bat --load data\demo_context_fault_sag.json
```

---

## System Spec

- **Target Hardware**: 3-Phase Inverter Microcontroller (VSM Firmware)
- **Telemetry Protocol**: JSON over UART (115200 baud)
- **Channels**: `V_an`, `V_bn`, `V_cn`, `I_a`, `I_b`, `I_c`, `Freq`, `P_mech`
- **Configuration**: [config/system_config.json](config/system_config.json)

---

## Testing

```cmd
python -m pytest tests/ -v
```

Test coverage includes:
- **Launcher stability** (`verify_launchers.py`) -- All 5 windows instantiate with correct panels and backends
- **Deep QA** (`test_qa_deep.py`) -- Context corruption handling, theme regression, cross-app round-trip, insight serialization
- **Serial protocol** (`test_serial_manager.py`) -- Frame parsing and mock mode
- **HIL core engines** (`test_session_context.py`, `test_signal_engine.py`, etc.)

---

## 📚 Documentation

### Getting Started
| Document | Description |
|----------|-------------|
| **[docs/PROJECT_OVERVIEW.md](docs/PROJECT_OVERVIEW.md)** | 🎓 **Senior design project context & scope** |
| [docs/QUICK_START_MODULAR.md](docs/QUICK_START_MODULAR.md) | User-friendly workflow examples |
| [docs/index.md](docs/index.md) | Engineering documentation hub |

### Architecture & Design
| Document | Description |
|----------|-------------|
| **[docs/GAP_ANALYSIS.md](docs/GAP_ANALYSIS.md)** | ✨ **Plan vs. reality comparison** |
| [docs/MODULAR_ARCHITECTURE.md](docs/MODULAR_ARCHITECTURE.md) | 5-app suite design overview |
| [docs/launcher_architecture.md](docs/launcher_architecture.md) | Launcher class hierarchy & dependency matrix |
| [docs/REDBYTE_HERITAGE.md](docs/REDBYTE_HERITAGE.md) | Origin story & naming rationale |
| [docs/architecture.md](docs/architecture.md) | System architecture overview |

### Integration & Deployment
| Document | Description |
|----------|-------------|
| **[docs/HARDWARE_INTEGRATION.md](docs/HARDWARE_INTEGRATION.md)** | 🔌 **Serial protocol, firmware guide, troubleshooting** |
| [docs/context_workflow.md](docs/context_workflow.md) | Context export/import JSON spec & workflow |
| [docs/protocol.md](docs/protocol.md) | Command/telemetry protocol |
| [docs/deployment_notes.md](docs/deployment_notes.md) | Lab machine installation |

### Testing & Validation
| Document | Description |
|----------|-------------|
| [docs/test_plan.md](docs/test_plan.md) | Testing strategy |
| [docs/UX_CERTIFICATION_REPORT.md](docs/UX_CERTIFICATION_REPORT.md) | End-to-end validation results |

### Presentation & Demo
| Document | Description |
|----------|-------------|
| [docs/demo_script.md](docs/demo_script.md) | Capstone presentation walkthrough |
| [docs/before_after_comparison.md](docs/before_after_comparison.md) | UX enhancement metrics |

---

## Project Structure

```
gfm_hil_suite/
  bin/                  Batch launchers (.bat)
  config/               System configuration
  data/                 Demo context files & session storage
  docs/                 Technical documentation
  src/
    launcher_base.py    Shared base class for all launchers
    launchers/          5 modular launcher scripts
    serial_reader.py    SerialManager backend
    recorder.py         Recorder backend
    scenario.py         ScenarioController backend
  hil_core/
    session.py          SessionContext singleton
    signals.py          SignalEngine (FFT/RMS)
    faults.py           FaultEngine
    insights.py         InsightEngine + Insight dataclass
    context.py          ContextExporter
  ui/
    panels/             InverterScope, PhasorView, System3DView, etc.
    app_themes.py       Per-app theme stylesheets
    shared/             Overlays, tooltips, splash screen
  tests/                Pytest test suite
```

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| UI Framework | PyQt6 + pyqtgraph |
| Signal Processing | NumPy, SciPy (FFT, Hilbert) |
| Serial Comms | pyserial (JSON/UART) |
| Data Storage | pandas, JSON context files |
| Testing | pytest, pytest-qt |
| Styling | QSS (Qt Style Sheets), glassmorphic design |
