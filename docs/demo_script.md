# RedByte HIL Verifier Suite -- Capstone Demo Script

## Setup (Before Presentation)

1. Open a terminal in `gfm_hil_suite/`
2. Activate the virtual environment: `.venv\Scripts\activate`
3. Verify all tests pass: `python -m pytest tests/ -v`
4. Have these files ready:
   - `data/demo_context_baseline.json` (normal operation)
   - `data/demo_context_fault_sag.json` (voltage sag fault)

---

## Act 1: The App Selector (2 min)

**Narration:** "RedByte is a modular HIL testing platform for 3-phase grid-forming inverters. Instead of one monolithic UI, we built 5 specialized applications."

**Action:**
```cmd
bin\launch_redbyte.bat
```

**Talk through:**
- Point out the 5 app cards with distinct color themes
- Each card shows the app name, icon, and one-line description
- Click any card to launch that app independently
- Mention: "Each app loads only the panels it needs -- no clutter"

---

## Act 2: Diagnostics in Mock Mode (3 min)

**Narration:** "Diagnostics is the primary data acquisition tool. It runs live signal capture, FFT analysis, and fault injection."

**Action:**
```cmd
bin\diagnostics.bat --mock
```

**Talk through:**
- **System3DView**: 3D rotor visualization linked to live telemetry
- **InverterScope**: Real-time oscilloscope showing V_an, V_bn, V_cn, I_a, I_b, I_c
- **PhasorView**: Phasor diagram with Hilbert-based angle extraction
- **FaultInjector**: Panel for triggering fault scenarios
- **InsightsPanel**: Live event detection (THD spikes, frequency deviations)

**Key point:** "All data flows through `SerialManager.frame_received` -- a single PyQt6 signal that fans out to every panel and the recorder simultaneously."

---

## Act 3: Cross-App Context Handoff (3 min)

**Narration:** "The key innovation is seamless data handoff between apps. A diagnostics session can be exported and loaded into Replay or Insights for post-analysis."

**Action:**
1. In the Diagnostics toolbar, click **Export Context**
2. Save as `demo_export.ctx.json`
3. Close Diagnostics
4. Launch Replay with the exported context:
   ```cmd
   bin\replay.bat --load demo_export.ctx.json
   ```

**Talk through:**
- Waveform data, insights, and tags are all preserved
- ReplayStudio shows the timeline with tagged events
- PhasorView reconstructs the phasor state at any point

**Alternative (pre-built demo):**
```cmd
bin\replay.bat --load data\demo_context_fault_sag.json
```
- Show the 3-phase voltage sag scenario
- Point out the 3 timeline tags: Pre-Fault Baseline, Fault Injection, Recovery Start
- Show the 4 insights: critical THD spike, elevated THD, frequency dip, phase unbalance

---

## Act 4: Insights Studio (2 min)

**Narration:** "Insight Studio is a dedicated event analysis tool. It clusters and categorizes power quality events."

**Action:**
```cmd
bin\insights.bat --load data\demo_context_fault_sag.json
```

**Talk through:**
- InsightsPanel displays all detected events with severity badges
- Critical: THD spike 15.2% on Phase A during fault
- Warning: Elevated THD 9.8% on Phase B during recovery
- Warning: Frequency dip to 59.2 Hz
- Info: Minor phase unbalance 3.2 degrees
- Each insight has a timestamp, type, and associated metrics

---

## Act 5: Architecture Walkthrough (2 min)

**Narration:** "Under the hood, the suite uses a two-layer backend architecture."

**Show the architecture diagram** (from README or `docs/launcher_architecture.md`):

- **Layer 1**: Qt-based backends (`SerialManager`, `Recorder`, `ScenarioController`) with real-time signals
- **Layer 2**: Pure Python engines (`SessionContext`, `SignalEngine`, `FaultEngine`, `InsightEngine`) for cross-app logic
- **LauncherBase**: Shared base class providing geometry persistence, overlays, tooltips, and context export/import

**Key design decisions:**
- "Singleton `SessionContext` ensures all apps share the same state"
- "Context files are plain JSON -- inspectable, diffable, version-controllable"
- "Each launcher inherits from `LauncherBase` for consistent UX across all 5 apps"

---

## Act 6: Testing & Quality (1 min)

**Action:**
```cmd
python -m pytest tests/ -v
```

**Talk through:**
- Launcher stability tests verify all 5 windows instantiate correctly
- Deep QA tests cover context corruption, theme regression, round-trip serialization
- Signal engine and session context have dedicated unit tests

---

## Closing

**Narration:** "RedByte transforms HIL verification from a monolithic debug tool into a professional-grade, modular platform. Each app is purpose-built for its workflow, but they all share data seamlessly through context export. The result is a toolkit that scales from single-engineer bench testing to full team workflows."

---

## Quick Reference

| Demo Command | What It Shows |
|---|---|
| `bin\launch_redbyte.bat` | App selector with 5 cards |
| `bin\diagnostics.bat --mock` | Live diagnostics with simulated data |
| `bin\replay.bat --load data\demo_context_fault_sag.json` | Voltage sag replay |
| `bin\insights.bat --load data\demo_context_fault_sag.json` | Event analysis |
| `bin\compliance.bat` | Standards validation dashboard |
| `bin\sculptor.bat --mock` | Waveform engineering |
| `python -m pytest tests/ -v` | Full test suite |
