# System Architecture

## Overview
The HIL Verifier Suite is a PyQt6 desktop application composed of three main layers:

1. **IO Adapters** (data acquisition and command transport)
2. **Core Services** (recording, replay, validation, signal processing)
3. **UI Widgets** (scopes, phasor view, 3D visualization, replay, etc.)

## Module Layout

- **src/**
  - `io_adapter.py`: adapter base + Serial/Demo/OpalRT implementations
  - `serial_reader.py`: `SerialManager` frame bus + thread reader
  - `recorder.py`: session logging
  - `replayer.py`: session replay
  - `scenario.py`: scenario execution + validation
  - `signal_processing.py`: RMS/THD/phasor extraction utilities

- **ui/**
  - `inverter_scope.py`: real-time waveform scope
  - `phasor_view.py`: phasor diagram with Hilbert extraction
  - `system_3d_view.py`: 3D VSM visualization
  - `fault_injector.py`: scenario runner + fault commands
  - `signal_sculptor.py`: waveform generator + injector
  - `replay_studio.py`: session playback + overlay metrics
  - `analysis_app.py`: session comparison
  - `validation_dashboard.py`: scorecard display

## Data Flow

```
[Serial/OpalRT/Demo Adapter]
            |
            v
      SerialManager
     (frame_received)
            |
            +--> Recorder (logs frames)
            |
            +--> UI widgets (scope, phasor, 3D, etc.)
```

### Key Signals
- `SerialManager.frame_received`: emitted for each incoming frame
- `ScenarioController.event_triggered`: emitted for scenario events
- `ScenarioController.validation_complete`: broadcast to scorecard

## Command Flow

```
UI (Fault Injector / Signal Sculptor)
            |
            v
      SerialManager.write_command()
            |
            v
     IOAdapter.write_command()
```

Adapters implement the transport for command packets:
- Serial: JSON packets with prefix `CMD:`
- OpalRT: TCP length-prefixed JSON
- Demo: internal state for simulation

## Reliability Notes
- Data acquisition runs on a dedicated thread in `SerialManager`.
- UI updates are event-driven via Qt signals.
- Replay uses the same `frame_received` signal to drive the UI.
