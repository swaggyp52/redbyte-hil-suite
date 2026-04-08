# Project Overview: RedByte GFM HIL Suite

**Senior Design Capstone Project — Gannon University**
**Academic Year 2025–2026**
**Team:** Cyber Engineering + Electrical Engineering

---

## What Is This Project?

The **RedByte GFM HIL Suite** is a desktop engineering analysis platform for
**Grid-Forming Inverters (GFM)** built on the **Virtual Synchronous Machine (VSM)** control model.
It is the software contribution to a senior design capstone that spans both Cyber Engineering
(this codebase) and Electrical Engineering (hardware, firmware, control algorithms).

The software is designed to be used in two complementary ways:

1. **Import and analyze captured test data** — load oscilloscope captures (Rigol CSV),
   simulation output (Excel), or session files (JSON) and run automated power-quality analysis.
2. **Live monitoring** — connect to a VSM inverter system via UART and watch waveforms,
   compute metrics, inject faults, and record sessions in real time.

As of April 2026, the import-and-analyze path is fully operational. The live-monitoring path
works in demo mode (synthetic telemetry). Connecting to the full 3-phase inverter hardware
is the next integration milestone after the power stage is completed by the EE team.

---

## The Problem This Solves

Grid-forming inverters are a critical enabling technology for renewable energy integration.
They must respond correctly to grid disturbances — voltage sags, frequency excursions,
harmonic injection — without tripping offline. Testing this behavior requires:

- Capturing high-bandwidth waveforms during fault events
- Computing power-quality metrics (RMS, THD, phasors) from raw oscilloscope data
- Verifying compliance with interconnection standards (IEEE 2800)
- Comparing measured inverter behavior against simulation predictions

Before this tool existed, that workflow required stitching together oscilloscope software,
spreadsheets, and manual threshold checks. This suite consolidates it into a single desktop
application with automated event detection, side-by-side session comparison, and a compliance
scorecard — no domain expertise required to interpret the results.

---

## Who Is This For?

**Primary audience:** The Gannon EE capstone team, using the suite during hardware-in-the-loop
testing of the 3-phase VSI prototype.

**Secondary audience:** Any lab engineer analyzing power-quality data from oscilloscope captures
or simulation runs — the import pipeline handles Rigol DSO CSV files and simulation Excel output.

---

## What Sources Does It Currently Support?

| Source | Format | Status |
|--------|--------|--------|
| Rigol oscilloscope captures | `.csv` | Operational |
| Simulation output | `.xlsx` / `.xls` | Operational |
| Previously recorded sessions | `.json` (Data Capsule v1.2) | Operational |
| DemoAdapter (synthetic 3-phase) | in-memory | Operational (demo mode) |
| Arduino Uno R3 breadboard prototype | UART JSON at 115200 baud | Structurally wired; schema mismatch (DC-bus only, not 3-phase) |
| Full 3-phase VSI hardware | UART JSON at 115200 baud | Planned — not yet built |

The Arduino prototype sends `t_ms, vdc, freq, p_kw, q_kvar, fault` — a DC-bus summary frame.
The software translates these fields through `normalize_frame()` in `src/models.py` so they
appear in the correct canonical slots.  Once the full 3-phase inverter hardware is built, adding
the expanded telemetry fields requires only alias entries in `normalize_frame()` — no UI changes.

---

## What Analysis Does It Currently Provide?

### File Import Pipeline
- Auto-detect CSV / Excel / JSON formats; parse and normalize to internal `ImportedDataset`
- Large-file ingestion runs on a background thread — ingesting a 1M-row 1 MHz Rigol capture does not block the UI
- Channel mapping dialog: map source column names to canonical signal names (e.g., `CH1(V) → v_an`)
  - Per-channel value range column (min → max) immediately surfaces dead or constant channels in amber
  - Duplicate-column warning fires automatically when two source channels carry identical data
    (encountered in the field: `VSGFrequency_Simulation.xlsx` contains `Pinv` power data
    despite its filename suggesting frequency — a labeling error surfaced by the range and duplicate checks)
- Save and load per-instrument mapping profiles

### Waveform Replay
- Timeline scrubber over captured sessions
- Overlaid multi-session comparison (dual-load A vs. B)
- Delta traces and channel-level statistical comparison
- FFT spectrum view; metrics tab (RMS, peak, σ, THD per channel)

### Automated Event Detection
Eight deterministic detectors run over every imported dataset:

| Detector | What it flags | Severity |
|----------|--------------|----------|
| Voltage sag | Per-cycle RMS < 90% of nominal | warning / critical |
| Voltage swell | Per-cycle RMS > 110% of nominal | warning |
| Frequency excursion | Deviation > 0.5 Hz from 60 Hz for ≥ 100 ms | warning / critical |
| Flatline | Signal std < 0.1% of range in any 50 ms window | warning |
| Step change | Single-sample Δ > 8% of total signal range | warning / critical |
| Clipping / saturation | ≥ 5 ms of samples at signal min or max | warning |
| Duplicate channel | Pearson r ≥ 0.999 between any channel pair | info |
| THD spike | FFT-based total harmonic distortion > 10% | warning / critical |

Results appear in the **Events** tab of the Replay Studio with:
- Severity color-coded rows (critical / warning / info)
- Engineering summary cards (worst sag depth, max freq deviation, max THD, max flatline duration, confidence range)
- Click a row → replay scrubber jumps to that timestamp
- Double-click the Note column → inline annotation (in-memory)

### Compliance Checking
Simplified IEEE 2800 rule set (3 rules):
- **Ride-through:** Minimum voltage during any sag event ≥ 50% nominal
- **Frequency stability:** Frequency stays within ±0.5 Hz of nominal
- **Voltage recovery:** No sustained under-voltage after a fault clears

Scorecard shows measured value, threshold, and PASS / FAIL for each rule.

### Export and Reporting

After analysis, four export options are available from the **Replay Studio** and **Compliance Lab** pages:

| Export | Format | What it contains |
|--------|--------|-----------------|
| Session CSV | `.csv` | All normalized frame data, metadata preamble, comment headers |
| Events CSV | `.csv` | One row per detected event; includes annotation notes |
| Analysis JSON | `.json` | Full analysis summary (session info, events, compliance) |
| Engineering Report | `.html` | Self-contained HTML with waveform plots, compliance scorecard, events table, channel mapping, and import warnings |

**Truthfulness rules enforced at the exporter boundary:**
- The session CSV discovers which columns actually exist in the frame data at export time.
  A channel that was absent from the source file produces no column — not a column of zeros.
- Frames that lack a particular field (because the source file had variable structure)
  get an *empty cell*, not `0.0`. This preserves the distinction between "not recorded"
  and "recorded as zero."
- The HTML report only generates a waveform plot for channel groups that have actual data.
  If none of `v_an / v_bn / v_cn` were mapped, the Voltage Waveforms section is omitted.
- The compliance section in the JSON and HTML is `null` when compliance was not run —
  it is never filled with made-up pass/fail values.
- The events section shows only what the detectors found; an empty file means no events
  were detected, which is different from "events were not checked."

All four export functions work from the in-memory Data Capsule (the same object used by all
analysis pages). No intermediate file save is required before exporting.


- 3-phase waveform scope at 25 Hz
- Phasor diagram with Hilbert-transform extraction
- Live metrics header (RMS, THD, frequency, power)
- Insight engine (3-second debounce, anomaly clustering)
- Fault injector controls (sag, frequency drift, clear)
- Session recording → auto-saved Data Capsule JSON

---

## What This Software Does NOT Do (Yet)

| Capability | Status |
|------------|--------|
| Real-time 3-phase waveforms from full inverter hardware | Planned — hardware not yet built |
| Unified pipeline merging live telemetry with import analysis | Done — live recording uses same capsule path as import |
| Large-file background workers (>500k samples) | Done — import dialog spawns a daemon thread; UI stays responsive for 1M+ row Rigol captures |
| Persistent annotation storage (survives app restart) | Planned — currently in-memory only |
| OpalRT / Typhoon HIL adapter | Stub only |

---

## What "Truthful Analysis" Means

**No signal fabrication.** If a channel is absent from the source file, it does not appear in
the analysis. The software will not invent `v_bn` from `v_an` by applying a 120° shift, will not
synthesize a time axis from frame indices if the timestamps are unreliable, and will not fill
missing samples with zeros or averages.

Concretely:
- Rigol channels `CH1(V)–CH4(V)` are left `[unmapped]` until a human explicitly assigns them.
- All event detection runs on the actual signal samples in the imported file.
- The compliance checker evaluates only the measurements present in the session;
  it does not assume a field is within spec because it was not recorded.

---

## How the Architecture Supports Future Hardware Integration

The entire software stack is insulated from hardware-specific details by a thin
normalization layer:

```
Hardware / File → ingest or adapter → normalize_frame() → canonical dict
                                                              ↓
                                           All analysis, display, recording
```

To add a new hardware source (e.g., the completed 3-phase VSI outputting `v_an/v_bn/v_cn`):
1. Write an `IOAdapter` subclass in `src/io_adapter.py`
2. Add alias entries to `_KEY_ALIASES` in `src/models.py`
3. Register the adapter in `AppShell._init_backends()`

No UI changes are needed. The waveform scope, phasor view, event detectors, compliance checker,
and session recorder all autodiscover available channels from the normalized frame.

See `docs/INGESTION_PIPELINE.md` for step-by-step instructions.

---

## End-to-End Demo Story

The recommended demo flow for the capstone evaluation:

1. **Overview page → Import Run File** — open a Rigol CSV capture from the bench oscilloscope
2. **Channel mapping dialog** — assign `CH1(V) → v_an`, `CH2(V) → i_a`, etc.
3. **Replay Studio → Waveforms** — inspect the full capture timeline; scrub to the fault window
4. **Replay Studio → Events** — automated event detection shows flagged anomalies; click a row to jump
5. **Replay Studio → Compare** — load a second run (pre-fault baseline) and compare side by side
6. **Compliance page → Run Compliance Check** — IEEE 2800 scorecard based on the imported data
7. **Replay Studio → Spectrum** — FFT spectrum of the fault window; THD readout
8. **Compliance page → Export Engineering Report** — single self-contained HTML with plots,
   compliance scorecard, detected events, and all provenance metadata baked in

This demo works entirely from file import — no hardware required, no mock data generated by the
software itself. Every number shown traces back to samples in the file the user selected.

---

## Architecture Summary

```
gfm_hil_suite/
├── run.py                          Entry point → src/main.py → AppShell
├── src/
│   ├── io_adapter.py               DemoAdapter (mock), SerialAdapter (UART), OpalRTAdapter (stub)
│   ├── serial_reader.py            SerialManager threaded frame bus
│   ├── models.py                   normalize_frame() — single normalization point for all sources
│   ├── signal_processing.py        RMS, THD (FFT), phasor (Hilbert), step metrics
│   ├── recorder.py / replayer.py   Session v1.2 "Data Capsule" JSON format
│   ├── insight_engine.py           Anomaly detection with 3-second debounce
│   ├── compliance_checker.py       Simplified IEEE 2800 (3 rules)
│   ├── file_ingestion.py           ImportedDataset — ingest .csv/.xlsx/.json
│   ├── channel_mapping.py          ChannelMapper, auto_suggest_mapping, UNMAPPED sentinel
│   ├── dataset_converter.py        dataset_to_session() + decimation + full-res access
│   ├── session_state.py            ActiveSession dataclass
│   ├── event_detector.py           DetectedEvent + detect_events() — 8 batch detectors
│   ├── comparison.py               align_datasets, compare_channels, delta traces
│   └── session_exporter.py         Truth-first export engine — CSV, events CSV, JSON, HTML report
├── ui/
│   ├── app_shell.py                Unified shell — owns all managers, wires all Qt signals
│   ├── pages/                      6 pages: Overview, Diagnostics, Replay, Compliance, Tools, Console
│   ├── replay_studio.py            ReplayStudio — Waveforms, Metrics, Spectrum, Compare, Events tabs
│   ├── event_lane.py               EventLane widget — event list + stats cards + annotations
│   ├── comparison_panel.py         ComparisonPanel — dual-session overlay + delta + metrics
│   ├── dataset_info_panel.py       Source metadata widget with channel summary
│   ├── inverter_scope.py           25 Hz real-time waveform scope
│   ├── phasor_view.py              Phasor diagram with Hilbert extraction
│   └── fault_injector.py           Fault command panel
└── tests/                          407 passing tests, 3 skipped (as of April 2026)
```

---

## Current Test Coverage

407 tests passing (3 skipped — Excel tests requiring pandas) across all modules (excluding UI
integration tests that require a display server). Run with:

```bash
cd gfm_hil_suite
pytest tests/ --ignore=tests/test_ui_integration.py -q
```

Key test files:

| File | Covers | Tests |
|------|--------|-------|
| `test_session_exporter.py` | Truth-first CSV/events/JSON/HTML export; missing channel → empty cell invariant | 45 |
| `test_event_detector.py` | All 8 detectors, DetectedEvent, graceful degradation | 27 |
| `test_comparison.py` | align_datasets, delta traces, compare_channels | 34 |
| `test_file_ingestion.py` | Rigol CSV (incl. 1 MHz), Excel, JSON, NaN trimming, ms→s conversion, dead-channel detection, no fabrication guarantee | ~44 |
| `test_channel_mapping.py` | auto_suggest, apply(), UNMAPPED invariant, profiles | ~20 |
| `test_dataset_converter.py` | Decimation, frame content, round-trip, full-res | ~20 |
| `test_compliance_checker.py` | IEEE 2800 rule evaluation | ~15 |
| `test_signal_processing.py` | RMS, THD, phasor extraction | ~12 |

---

## What Makes This a Strong Senior Design Project

1. **It solves a real problem.** The Gannon EE team has actual oscilloscope captures from the
   breadboard prototype. This tool processes them and produces structured engineering results.

2. **The scope is honest.** The project documentation distinguishes clearly between what is
   implemented, what is wired but not yet usable (live 3-phase hardware), and what comes next.
   This is more credible to evaluators than inflated claims.

3. **The architecture is forward-compatible.** Adding full 3-phase hardware requires three
   targeted changes (one adapter file, a few alias entries, one config line). The rest of the
   stack is already correct.

4. **The analysis is algorithmic and deterministic.** Event detection results can be reproduced
   exactly from the source file. Every flagged event traces to a specific sample window with a
   recorded metric and confidence score.

5. **The test coverage matches the complexity.** 407 tests cover the signal processing, ingestion,
   channel mapping, event detection, session comparison, compliance, and export subsystems independently.
   The ingestion tests include 1 MHz Rigol format, dead-channel detection, and explicit no-fabrication assertions.

---

*Last Updated: April 2026*
