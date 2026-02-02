# RedByte Launcher Architecture

## Overview

The RedByte HIL Verifier Suite uses a modular launcher architecture where each specialized application runs as an independent process with its own window, theme, and panel set. All launchers inherit from a shared `LauncherBase` class that provides consistent UX behavior.

## Architecture Diagram

```
redbyte_launcher.py (App Selector Card UI)
    |
    |-- launch_diagnostics.py --> DiagnosticsWindow(LauncherBase)
    |     Backends: SerialManager, Recorder, ScenarioController
    |     hil_core: SessionContext, SignalEngine, FaultEngine, InsightEngine
    |     Panels:   System3DView, InverterScope, PhasorView, FaultInjector, InsightsPanel
    |     Theme:    Emerald (#10b981)
    |
    |-- launch_replay.py -------> ReplayWindow(LauncherBase)
    |     Backends: SerialManager, Recorder
    |     hil_core: SessionContext
    |     Panels:   ReplayStudio, PhasorView, InsightsPanel
    |     Theme:    Cyan (#06b6d4)
    |
    |-- launch_compliance.py ---> ComplianceWindow(LauncherBase)
    |     Backends: ScenarioController
    |     hil_core: SessionContext
    |     Panels:   ValidationDashboard
    |     Theme:    Purple (#8b5cf6)
    |
    |-- launch_insights.py -----> InsightStudioWindow(LauncherBase)
    |     Backends: (none)
    |     hil_core: SessionContext, InsightEngine
    |     Panels:   InsightsPanel
    |     Theme:    Amber (#f59e0b)
    |
    +-- launch_sculptor.py -----> SculptorWindow(LauncherBase)
          Backends: SerialManager
          hil_core: SessionContext
          Panels:   SignalSculptor, InverterScope
          Theme:    Orange (#f97316)
```

## Two-Layer Backend Architecture

### Layer 1: `src/` Backends (Qt-based, with signals)

These are the original backend managers used by UI panels. They use PyQt6 signals for real-time data flow.

| Class              | Module              | Constructor   | Key Signal            |
|--------------------|---------------------|---------------|-----------------------|
| `SerialManager`    | `serial_reader.py`  | `()`          | `frame_received(dict)`|
| `Recorder`         | `recorder.py`       | `(data_dir?)` | -                     |
| `ScenarioController` | `scenario.py`     | `()`          | `event_triggered(str, dict)` |

### Layer 2: `hil_core/` Engines (Pure Python, cross-app)

These provide session sharing and modular analysis. They do NOT use Qt signals.

| Class            | Module                | Purpose                           |
|------------------|-----------------------|-----------------------------------|
| `SessionContext` | `hil_core/session.py` | Singleton for cross-app state     |
| `SignalEngine`   | `hil_core/signals.py` | Circular buffer + FFT/RMS         |
| `FaultEngine`    | `hil_core/faults.py`  | Fault injection state machine     |
| `InsightEngine`  | `hil_core/insights.py`| Event detection + clustering      |

## LauncherBase Class

All 5 launcher windows inherit from `LauncherBase` (`src/launcher_base.py`), which provides:

| Feature                | Method                          | Description                               |
|------------------------|---------------------------------|-------------------------------------------|
| Geometry persistence   | `eventFilter()`, `_register_subwindow()` | Tracks user panel movements     |
| Overlay notifications  | `notify(text, color)`           | Fade-out overlay messages                 |
| Help overlay           | `help_overlay`                  | Conditional first-run tips                |
| Status bar             | `_setup_status_bar(serial_mgr?)` | Live metrics (RMS, THD, mode)            |
| Tooltips               | `_apply_panel_tooltips()`       | Per-panel tooltip injection               |
| Context export/import  | `_add_context_actions(toolbar)` | File dialog for session bundles           |
| CLI arguments          | `parse_args()`                  | `--mock` and `--load` flags               |

## Dependency Matrix

| Launcher      | SerialManager | Recorder | ScenarioController | Signal wiring needed |
|---------------|:---:|:---:|:---:|---|
| Diagnostics   | X | X | X | `frame_received -> recorder.log_frame`, `frame_received -> _on_frame` |
| Replay        | X | X |   | `frame_received -> recorder.log_frame` |
| Compliance    |   |   | X | - |
| Insights      |   |   |   | - |
| Sculptor      | X |   |   | - |

## Panel Constructor Requirements

| UI Panel            | Required Arguments                       |
|---------------------|------------------------------------------|
| `InverterScope`     | `serial_mgr`                             |
| `PhasorView`        | `serial_mgr`                             |
| `System3DView`      | `serial_mgr`, optional `scenario_ctrl`   |
| `FaultInjector`     | `scenario_ctrl`, optional `serial_mgr`   |
| `ReplayStudio`      | `recorder`, `serial_mgr`                 |
| `ValidationDashboard` | `scenario_controller`                  |
| `SignalSculptor`    | `serial_mgr`                             |
| `InsightsPanel`     | *(none)*                                 |

## Launcher Startup Sequence

```python
def main():
    args = LauncherBase.parse_args()       # 1. Parse CLI args
    app = QApplication(sys.argv)           # 2. Create Qt application
    splash = RotorSplashScreen()           # 3. Show animated splash
    splash.show()
    app.processEvents()
    window = DiagnosticsWindow()           # 4. Create window (panels, toolbar, backends)
    if args.mock:                          # 5. Optional: start mock mode
        window.serial_mgr.start_mock_mode()
    if args.load:                          # 6. Optional: auto-load context
        # copy file + import
    splash.finish(window)                  # 7. Close splash
    window.show()                          # 8. Show window
    sys.exit(app.exec())                   # 9. Enter Qt event loop
```

## Batch Launchers

| Script           | Command                                       |
|------------------|-----------------------------------------------|
| `diagnostics.bat`| `python src\launchers\launch_diagnostics.py`  |
| `replay.bat`     | `python src\launchers\launch_replay.py`       |
| `compliance.bat` | `python src\launchers\launch_compliance.py`   |
| `insights.bat`   | `python src\launchers\launch_insights.py`     |
| `sculptor.bat`   | `python src\launchers\launch_sculptor.py`     |
| `launch_redbyte.bat` | `python src\redbyte_launcher.py`          |

All batch files support `--mock` and `--load <path>` flags passed through via `%*`.
