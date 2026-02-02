# RedByte Context Export/Import Workflow

## Overview

RedByte launchers share session data through **context files** - JSON bundles containing waveform snapshots, scenario parameters, insights, and timeline tags. This enables a multi-stage analysis workflow where data flows from live capture through replay, validation, and insight analysis.

## Data Flow

```
Diagnostics (source)
    |
    |-- export_for_replay() ---------> temp/redbyte_session_replay.json
    |                                      |
    |                                      +--> Replay Studio
    |                                               |
    |                                               +-- export_for_insights() --> Insight Studio
    |
    |-- export_for_compliance() -----> temp/redbyte_session_compliance.json
    |                                      |
    |                                      +--> Compliance Lab
    |
    +-- export_context('diagnostics') -> temp/redbyte_session_diagnostics.json
                                              |
                                              +--> Any launcher via import_context()
```

## Context File Format

All context files use JSON with this structure:

```json
{
  "session_id": "20260201_143022",
  "source_app": "diagnostics",
  "target_app": "replay",
  "timestamp": "2026-02-01T14:30:22.123456",
  "waveform": {
    "timestamp": 1738418422.123,
    "channels": {
      "v_an": [120.1, 119.8, ...],
      "v_bn": [120.3, 120.1, ...],
      "v_cn": [119.9, 120.2, ...],
      "i_a": [10.5, 10.3, ...],
      "i_b": [10.4, 10.6, ...],
      "i_c": [10.5, 10.4, ...]
    },
    "sample_rate": 10000,
    "duration": 5.0,
    "metadata": {}
  },
  "scenario": {
    "name": "Grid Fault Test",
    "fault_type": "three_phase_sag",
    "parameters": {"magnitude": 0.5, "duration": 0.2},
    "start_time": 1738418420.0,
    "insights": [...]
  },
  "insights": [
    {
      "type": "thd",
      "severity": "warning",
      "message": "THD exceeded 10% on Phase A",
      "timestamp": 1.234,
      "metrics": {"thd_value": 12.5, "phase": "A"}
    }
  ],
  "tags": [
    {
      "timestamp": 0.5,
      "label": "Fault Injection Start",
      "color": "#ef4444",
      "notes": "3-phase voltage sag initiated"
    }
  ],
  "config": {}
}
```

## Export Methods

### From Code (ContextExporter)

```python
from hil_core.export_context import ContextExporter

# Export for Replay Studio
path = ContextExporter.export_for_replay(
    waveform_channels=signal_engine.get_all_channels(),
    sample_rate=10000,
    scenario_name="My Test",
    insights=insight_engine.export_insights(),
    tags=[]
)

# Export for Compliance Lab
path = ContextExporter.export_for_compliance(
    waveform_channels=signal_engine.get_all_channels(),
    sample_rate=10000,
    validation_results={"freq_check": "pass"},
    scenario_name="My Test"
)

# Export for Insight Studio
path = ContextExporter.export_for_insights(
    insights=insight_engine.export_insights()
)
```

### From SessionContext

```python
from hil_core import SessionContext

session = SessionContext()
session.set_waveform(channels, sample_rate=10000, duration=5.0)
session.set_scenario("Grid Fault", fault_type="sag", parameters={"mag": 0.5})
session.add_insight("thd", "warning", "THD > 10%", timestamp=1.2)

# Export
path = session.export_context("replay")

# Import (in another launcher)
session2 = SessionContext()
if session2.import_context("diagnostics"):
    print(f"Loaded {len(session2.insights)} insights")
```

### From the UI

Every launcher toolbar includes Export Context and Load Context buttons:

- **Export Context**: Saves the current session to a user-chosen `.json` file
- **Load Context**: Opens a file dialog, loads a `.json` context file, and refreshes the UI

### From the CLI

```bash
# Auto-load a context file on startup
python src\launchers\launch_replay.py --load path/to/context.json

# Start in mock mode with simulated data
python src\launchers\launch_diagnostics.py --mock
```

## Standard Workflow

### 1. Capture (Diagnostics)

```
bin\diagnostics.bat --mock
```

- Start monitoring (toolbar: Start)
- Inject faults via Fault Injector panel
- Observe insights in real-time
- Export to Replay or Compliance (toolbar buttons)

### 2. Review (Replay Studio)

```
bin\replay.bat
```

- Automatically loads context from Diagnostics
- Scrub timeline, add tags
- Export tags or forward to Insight Studio

### 3. Validate (Compliance Lab)

```
bin\compliance.bat
```

- Automatically loads context from Diagnostics
- Run automated validation tests
- Export compliance report

### 4. Analyze (Insight Studio)

```
bin\insights.bat
```

- Loads insights from Diagnostics or Replay
- View event clusters and patterns
- Export CSV summaries

### 5. Edit (Signal Sculptor)

```
bin\sculptor.bat --mock
```

- Edit waveforms and apply filters
- Preview results in scope
- Standalone or with loaded context

## File Locations

| File | Location |
|------|----------|
| Replay context | `temp/redbyte_session_replay.json` |
| Compliance context | `temp/redbyte_session_compliance.json` |
| Insights context | `temp/redbyte_session_insights.json` |
| Diagnostics context | `temp/redbyte_session_diagnostics.json` |
| User-exported files | User-chosen path via file dialog |
| Session recordings | `data/sessions/session_*.json` |
