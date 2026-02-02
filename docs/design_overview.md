# System Design & Architecture Overview

## 1. High-Level Block Diagram

```mermaid
graph TD
    HIL[HIL Hardware / Simulation] -->|Serial/UART| Driver[SerialReader (Threaded)]
    Driver -->|Signals| Monitor[Monitor App (Oscilloscope)]
    Driver -->|Signals| Recorder[Data Recorder]
    
    User[User] -->|Control| Scenario[Scenario Controller]
    Scenario -->|Event Markers| Recorder
    Scenario -->|Commands| HIL
    
    User -->|Offline| Analysis[Analysis / Replayer]
    File[JSON Capsule] --> Analysis
    File --> Replayer
    Replayer --> Monitor
```

## 2. Software Modules

### Backend (`src/`)

- **SerialReader**: Threaded, auto-reconnecting UART handler. Parses properties like `v`, `i`, `freq`.
- **Recorder**: Saves session data + events to JSON format suitable for replay.
- **ScenarioController**: Executes time-based test sequences (e.g. voltage steps).
- **AnalysisEngine**: Computes statistical differences (RMSE, Max Delta) between two session files.

### Frontend (`ui/`)

- **MainWindow**: MDI (Multi-Document Interface) shell hosting all apps.
- **MonitorApp**: Real-time plotting using `pyqtgraph`.
- **SessionManager**: Controls for recording and playback.
- **ScenarioApp**: UI for running automated tests.
- **AnalysisApp**: Tool for side-by-side comparison of test runs.

## 3. Data Flow

1. **Ingest**: Serial -> JSON -> Dict -> Signals.
2. **Storage**: Signals -> In-Memory Buffer -> JSON File on Stop.
3. **Validation**: File A + File B -> Analysis Engine -> Metrics (RMSE).
