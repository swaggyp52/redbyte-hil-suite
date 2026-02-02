# RedByte Modular Suite Architecture

## 🎯 Overview

The RedByte HIL Verifier Suite has been transformed from a monolithic demo application into **5 distinct, purpose-built applications**, each with its own visual identity, workflow scope, and specialized tooling.

## 🧩 Application Suite

### 1. 🟩 RedByte Diagnostics
**Purpose:** Live signal capture + fault injection  
**Accent Color:** Green (#10b981)  
**Entry Point:** `src/launchers/launch_diagnostics.py`  
**Quick Launch:** `bin\diagnostics.bat`

**Panels:**
- 3D System View (primary situational awareness)
- Inverter Scope (live waveforms)
- Phasor Diagram (phase relationships)
- Fault Injector (control interface)
- Insights Panel (compact monitoring mode)

**Key Features:**
- Real-time signal streaming at 20 Hz
- Live fault injection with parameter control
- Automatic insight detection (THD, frequency, unbalance)
- Export to Replay Studio or Compliance Lab
- Scene capture and annotation

**Use Cases:**
- Live system monitoring during HIL tests
- Fault scenario injection and observation
- Real-time anomaly detection
- Rapid diagnostic capture for later analysis

---

### 2. 🔵 RedByte Replay Studio
**Purpose:** Timeline playback & waveform review  
**Accent Color:** Cyan (#06b6d4)  
**Entry Point:** `src/launchers/launch_replay.py`  
**Quick Launch:** `bin\replay.bat`

**Panels:**
- Timeline View (main playback interface)
- Phasor History (scrollable phase view)
- Event Log (expandable insights panel)

**Key Features:**
- Timeline playback with position scrubbing
- Tag-based annotation system
- Import sessions from Diagnostics
- Export insights to Insight Studio
- Variable speed playback control

**Use Cases:**
- Post-test waveform review
- Event correlation and timing analysis
- Collaborative review with tagged annotations
- Detailed inspection of transient events

---

### 3. 🟪 RedByte Compliance Lab
**Purpose:** Automated test suites & validation scoring  
**Accent Color:** Purple (#8b5cf6)  
**Entry Point:** `src/launchers/launch_compliance.py`

**Panels:**
- Validation Dashboard (scorecard grid)
- Waveform Thumbnails (inline visual context)
- Compliance Scorecard (pass/fail metrics)

**Key Features:**
- Automated standards compliance testing
- Waveform snapshot comparison
- HTML report generation
- Inline thumbnail previews
- Pass/fail scoring system

**Use Cases:**
- IEEE 1547 compliance validation
- Automated regression testing
- Standards certification preparation
- Batch scenario validation

---

### 4. 🟨 RedByte Insight Studio
**Purpose:** AI cognitive insight layers & event clustering  
**Accent Color:** Amber (#f59e0b)  
**Entry Point:** `src/launchers/launch_insights.py`

**Panels:**
- Insight Cluster Explorer (full-screen tree)
- Event Timeline Heatmap (temporal visualization)
- Cognitive Overlay (AI-powered patterns)

**Key Features:**
- Event clustering by type and severity
- Temporal pattern recognition
- Critical event prioritization
- CSV/JSON export for external analysis
- Import from Diagnostics or Replay Studio

**Use Cases:**
- Deep dive into detected anomalies
- Pattern analysis across multiple tests
- Root cause investigation
- Insight reporting and documentation

---

### 5. 🟧 RedByte Signal Sculptor
**Purpose:** Live waveform editing & filter tuning  
**Accent Color:** Orange (#f97316)  
**Entry Point:** `src/launchers/launch_sculptor.py`

**Panels:**
- Signal Editor (live filter controls)
- Mini Scope (real-time preview)
- FFT Preview (frequency domain)
- Filter Bank (save/load presets)

**Key Features:**
- Live signal manipulation
- Real-time filter application
- FFT spectrum analysis
- Custom waveform synthesis
- Export filtered signals

**Use Cases:**
- Signal conditioning experiments
- Filter parameter tuning
- Custom waveform generation
- Pre-processing for compliance tests

---

## 🏗️ Technical Architecture

### Core Infrastructure (`src/hil_core/`)

**SessionContext** (`session.py`)
- Global singleton for cross-app state management
- Waveform snapshot preservation
- Scenario context tracking
- Session export/import for app handoff

**SignalEngine** (`signals.py`)
- Unified signal processing
- Circular buffer management (10k samples)
- RMS, peak, THD, frequency computation
- Real-time streaming support

**FaultEngine** (`faults.py`)
- Centralized fault injection
- Scenario-based fault sequences
- Real-time parameter modulation
- Fault event callbacks

**InsightEngine** (`insights.py`)
- AI-powered event detection
- Severity classification
- Temporal clustering
- Insight aggregation

**ContextExporter** (`export_context.py`)
- Cross-app context export/import
- Optimized handoff for each app type
- Session file management (`temp/redbyte_session_*.json`)

### App-Specific Theming (`ui/app_themes.py`)

Each app has unique styling:
```python
get_diagnostics_style()  # Green accent
get_replay_style()       # Cyan accent
get_compliance_style()   # Purple accent
get_insights_style()     # Amber accent
get_sculptor_style()     # Orange accent
```

All share core RedByte aesthetics:
- Cyber-industrial gradient backgrounds
- Glassmorphic panel effects
- JetBrains Mono typography
- Neon accent borders

### Launcher System

**Main Launcher** (`src/redbyte_launcher.py`)
- App selection cards with hover animations
- Visual app identity showcase
- Quick access to legacy demo
- Documentation links

**Individual Launchers** (`src/launchers/launch_*.py`)
- Focused panel subsets per app
- App-specific toolbar actions
- Context import on startup
- Export actions to sibling apps

---

## 🔄 Cross-App Workflow

### Example: Diagnostics → Replay Studio

1. **Diagnostics:** Capture live fault scenario
   - Monitor signals in real-time
   - Inject voltage sag fault
   - Insights auto-detect THD spike
   
2. **Export:** Click "🔵 Open in Replay Studio"
   - Waveform data exported to `temp/redbyte_session_replay.json`
   - Replay Studio launches automatically
   
3. **Replay Studio:** Review captured session
   - Timeline loaded with waveforms
   - Insights preserved and visible
   - Add tags at key events
   - Scrub timeline to analyze transient

4. **Further Analysis:** Click "🟨 Open in Insight Studio"
   - Insights exported for clustering
   - Deep dive into event patterns

### Session Context Handoff

All apps use `SessionContext` singleton:

```python
from hil_core import SessionContext

# Export from Diagnostics
session = SessionContext()
session.source_app = 'diagnostics'
session.set_waveform(channels, sample_rate, duration)
export_path = session.export_context('replay')

# Import in Replay Studio
session = SessionContext()
if session.import_context('diagnostics'):
    # Waveform and insights restored
    waveforms = session.waveform
    insights = session.insights
```

**Temp Files:**
- `temp/redbyte_session_replay.json` - For Replay Studio
- `temp/redbyte_session_compliance.json` - For Compliance Lab
- `temp/redbyte_session_insights.json` - For Insight Studio

---

## 📁 Directory Structure

```
gfm_hil_suite/
├── src/
│   ├── hil_core/              # Shared backend
│   │   ├── __init__.py
│   │   ├── session.py         # SessionContext singleton
│   │   ├── signals.py         # SignalEngine
│   │   ├── faults.py          # FaultEngine
│   │   ├── insights.py        # InsightEngine
│   │   └── export_context.py  # ContextExporter
│   │
│   ├── launchers/             # App-specific entrypoints
│   │   ├── launch_diagnostics.py
│   │   ├── launch_replay.py
│   │   ├── launch_compliance.py
│   │   ├── launch_insights.py
│   │   └── launch_sculptor.py
│   │
│   ├── redbyte_launcher.py    # Main app selector UI
│   └── main.py                # Legacy demo (preserved)
│
├── ui/
│   ├── app_themes.py          # Per-app themed stylesheets
│   ├── main_window.py         # Legacy window (preserved)
│   ├── inverter_scope.py      # Waveform plots
│   ├── phasor_view.py         # Phasor diagram
│   ├── insights_panel.py      # Insight clusters
│   └── ...                    # Other panels
│
├── bin/
│   ├── launch_redbyte.bat     # Main launcher
│   ├── diagnostics.bat        # Quick launch Diagnostics
│   ├── replay.bat             # Quick launch Replay Studio
│   └── start.bat              # Legacy demo launcher
│
└── temp/                      # Session handoff files
    └── redbyte_session_*.json
```

---

## 🚀 Quick Start

### Launch Main Selector
```bash
# Windows
bin\launch_redbyte.bat

# Or directly
python src\redbyte_launcher.py
```

### Quick Launch Individual Apps
```bash
# Diagnostics
bin\diagnostics.bat
python src\launchers\launch_diagnostics.py

# Replay Studio
bin\replay.bat
python src\launchers\launch_replay.py

# Compliance Lab
python src\launchers\launch_compliance.py

# Insight Studio
python src\launchers\launch_insights.py

# Signal Sculptor
python src\launchers\launch_sculptor.py

# Legacy Demo (all-in-one)
bin\start.bat
python src\main.py
```

---

## ✅ UX Success Criteria

### ✅ Clear Purpose & Reduced Scope
Each app has a focused mission - no UI clutter from unrelated features

### ✅ Visual Separation
Distinct color accents create instant brand recognition per app

### ✅ Workflow Clarity
Users understand exactly which tool to use for each task

### ✅ Seamless Handoff
Context export/import enables fluid workflow between apps

### ✅ Reusable Core
Shared `hil_core` module eliminates code duplication

### ✅ Testable Modules
Each component can be tested independently

### ✅ New User Onboarding
App cards with descriptions make purpose immediately clear

---

## 🔧 Developer Guide

### Adding a New App

1. **Create Launcher:**
   ```python
   # src/launchers/launch_myapp.py
   from hil_core import SessionContext
   from ui.app_themes import get_base_style
   
   class MyAppWindow(QMainWindow):
       def __init__(self):
           self.session = SessionContext()
           self.session.source_app = 'myapp'
   ```

2. **Add Theme:**
   ```python
   # ui/app_themes.py
   def get_myapp_style():
       return get_base_style() + """
       QPushButton {
           border: 2px solid #YOUR_COLOR;
           color: #YOUR_COLOR;
       }
       """
   ```

3. **Add to Launcher UI:**
   ```python
   # src/redbyte_launcher.py
   apps.append({
       'name': 'My App',
       'id': 'myapp',
       'accent': '#YOUR_COLOR',
       'icon': '🟦',
       'desc': 'Description',
       'launcher': 'launch_myapp.py'
   })
   ```

### Cross-App Export

```python
# In source app
from hil_core.export_context import ContextExporter

export_path = ContextExporter.quick_export(
    target_app='myapp',
    custom_data={'key': 'value'}
)

# In target app
session = SessionContext()
if session.import_context('sourceapp'):
    data = session.config.get('custom_data')
```

---

## 📊 Performance

**Session Context:**
- Singleton pattern: O(1) instance access
- JSON export: < 50ms for 10k samples
- Import caching: Reuse loaded sessions

**Signal Engine:**
- Circular deques: O(1) append
- FFT computation: O(n log n) with scipy
- Buffer size: 10k samples default (configurable)

**UI Updates:**
- Diagnostics: 20 Hz (50ms interval)
- Replay: 20 FPS (50ms frame time)
- Geometry persistence: < 5ms per panel

---

## 🎨 Visual Identity Matrix

| App                  | Accent   | Icon | Primary Focus       | Secondary Focus      |
| -------------------- | -------- | ---- | ------------------- | -------------------- |
| **Diagnostics**      | Green    | 🟩    | Live Monitoring     | Fault Injection      |
| **Replay Studio**    | Cyan     | 🔵    | Timeline Playback   | Event Tagging        |
| **Compliance Lab**   | Purple   | 🟪    | Validation Scoring  | Standards Testing    |
| **Insight Studio**   | Amber    | 🟨    | Event Clustering    | Pattern Analysis     |
| **Signal Sculptor**  | Orange   | 🟧    | Waveform Editing    | Filter Design        |

---

## 🔮 Future Enhancements

- **Remote Collaboration:** Multi-user session sharing
- **Cloud Storage:** Azure Blob integration for sessions
- **Plugin System:** External app extensions
- **AI Models:** ML-based fault prediction
- **Mobile Companion:** iOS/Android monitoring app
- **REST API:** External tool integration

---

## 📖 References

- [Original UX Polish Documentation](REDBYTE_UX_COMPLETE.md)
- [Geometry Persistence Fix](geometry_persistence_fix.md)
- [HIL Core API Reference](api_reference.md)
- [Test Plan](test_plan.md)

---

**Last Updated:** 2026-02-01  
**Architecture Version:** 2.0 (Modular)  
**Status:** ✅ Production Ready
