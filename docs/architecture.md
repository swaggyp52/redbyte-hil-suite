# System Architecture

## Overview

The GFM HIL Suite is a PyQt6 desktop application with three layers:

1. **IO & ingestion** — adapters for live hardware, file parsers for captured data
2. **Core services** — signal processing, event detection, compliance, session management
3. **UI** — 6-page shell with widgets for waveforms, events, comparison, compliance

---

## Module Layout

### `src/` — Backend

| Module | Purpose |
|--------|---------|
| `io_adapter.py` | Adapter base class + `DemoAdapter` (mock 3-phase), `SerialAdapter` (UART), `OpalRTAdapter` (TCP stub) |
| `serial_reader.py` | `SerialManager` — background thread reads frames, calls `normalize_frame()`, emits `frame_received` Qt signal |
| `models.py` | `normalize_frame()` — single normalization point for **all** adapter outputs; handles Arduino key aliases + pre-alias unit scaling |
| `signal_processing.py` | `compute_rms()`, `compute_thd()` (FFT), `compute_phasor()` (Hilbert), `compute_step_metrics()` |
| `recorder.py` | Records live frames to a Data Capsule v1.2 JSON session file |
| `replayer.py` | Replays a recorded session, emitting frames via `frame_received` at playback speed |
| `insight_engine.py` | Anomaly detection with 3-second debounce; clusters events by type; feeds `InsightsPanel` |
| `compliance_checker.py` | Simplified IEEE 2800: 3 rules — ride-through (≥50% nominal), freq stability (±0.5 Hz), voltage recovery |
| `file_ingestion.py` | `ingest_file()` → `ImportedDataset`; handles Rigol CSV (chunked, NaN trimming), Excel (first non-empty sheet), Data Capsule JSON |
| `channel_mapping.py` | `ChannelMapper`, `auto_suggest_mapping()`, `UNMAPPED` sentinel; profile persistence (JSON) |
| `dataset_converter.py` | `dataset_to_session()` — converts `ImportedDataset` to Data Capsule v1.2; decimation to ≤4000 frames; full-res preserved in `capsule["_dataset"]` |
| `session_state.py` | `ActiveSession` dataclass — in-memory descriptor of the current live/imported session |
| `event_detector.py` | `DetectedEvent` dataclass + `detect_events(dataset)` — 8 batch detectors; sorted by `ts_start` |
| `comparison.py` | `find_overlapping_channels()`, `align_datasets()`, `compare_channels()`, `generate_delta_trace()`, `compare_datasets()`, `dataset_from_capsule()` |

### `ui/` — User Interface

| Module | Purpose |
|--------|---------|
| `app_shell.py` | `AppShell` — unified single-window shell; owns all managers; wires all Qt signals between components |
| `pages/overview_page.py` | Overview — Import Run File (primary action), Start Demo Session (secondary), `DatasetInfoPanel` |
| `pages/diagnostics_page.py` | Diagnostics — fault injector + real-time waveform view |
| `pages/replay_page.py` | Replay — hosts `ReplayStudio`; wires `load_imported_session()` |
| `pages/compliance_page.py` | Compliance — scorecard display; Run Compliance Check button |
| `pages/console_page.py` | Console — single-screen live overview: metrics header, scope, phasor, insights |
| `pages/tools_page.py` | Tools — developer configuration panel |
| `replay_studio.py` | `ReplayStudio` — 5 tabs: Waveforms, Metrics, Spectrum, Compare, Events; hosts ComparisonPanel and EventLane |
| `event_lane.py` | `EventLane` — severity-colored event list; engineering summary cards; inline user annotations; `event_selected(float)` signal |
| `comparison_panel.py` | `ComparisonPanel` — dual-session overlay + delta traces + per-channel metrics tab |
| `dataset_info_panel.py` | Compact widget showing source metadata and channel summary |
| `import_dialog.py` | Two-panel dialog: file metadata (left), channel mapping table (right); emits `session_imported(dict)` |
| `inverter_scope.py` | 3-phase waveform plot at 25 Hz |
| `phasor_view.py` | Phasor diagram with Hilbert-transform extraction |
| `fault_injector.py` | Sends fault commands (`fault_sag`, `fault_drift`, `clear_fault`) through the adapter |

---

## Data Flow — Import Path

```
User selects file (CSV / XLSX / JSON)
         |
         v
   ingest_file(path)                         ← file_ingestion.py
         |
         v
   ImportedDataset                           ← numpy arrays + original headers + warnings
         |
         v
   auto_suggest_mapping()                    ← channel_mapping.py
   User edits mapping in ImportDialog        ← ui/import_dialog.py
         |
         v
   ChannelMapper.apply()                     ← returns new ImportedDataset with renamed channels
         |
         v
   dataset_to_session()                      ← dataset_converter.py
         |
   ┌─────┴──────────────────────────────┐
   │  Data Capsule dict (v1.2)          │   ← frames decimated to ≤4000 for replay
   │    + capsule["_dataset"]           │   ← full-res ImportedDataset for FFT/event detection
   └────────────────────────────────────┘
         |
         v
   ReplayStudio.load_session_from_dict()
         |
         ├── _render_all_sessions()          ← plots waveforms
         ├── _update_comparison_tab()        ← dual-session diff
         └── _update_event_lane()            ← detect_events(dataset) → EventLane.load_events()
```

---

## Data Flow — Live Telemetry Path

```
[Hardware / DemoAdapter]
         |
         v
   IOAdapter.read_frame()                    ← raw dict (hardware-specific keys)
         |
         v
   normalize_frame()                         ← models.py (aliases + unit scaling)
         |
         v
   SerialManager.frame_received (Qt signal)
         |
         ├── Recorder                        ← logs to session file
         ├── InsightEngine                   ← anomaly detection + clustering
         ├── InverterScope                   ← real-time waveform scope
         ├── PhasorView                      ← phasor diagram
         └── Console metrics header          ← FREQ / RMS / THD / P
```

---

## Key Invariants

1. **`normalize_frame()` is the only normalization point.** Never read raw adapter output
   directly in UI code or analytics.

2. **No signal fabrication.** If a channel is absent from the source, it does not
   exist downstream. Code must check `if "v_bn" in frame` rather than read a default.

3. **Full-resolution data for analysis.** `capsule["_dataset"]` contains all samples from
   the original file. Event detection and FFT always use this, not the decimated frame list.

4. **EventLane is compute-only.** `detect_events()` is a pure batch function with no side
   effects. It is called from `_update_event_lane()` after session load, never from a timer.

---

## Adding a New Hardware Source

1. Subclass `IOAdapter` in `src/io_adapter.py`
2. Add `_KEY_ALIASES` and `_PRE_ALIAS_SCALE` entries to `normalize_frame()` in `src/models.py`
3. Register the adapter in `AppShell._init_backends()`

No UI changes are needed — waveform scope, phasor view, event detectors, and compliance
checker all autodiscover available channels from the normalized frame dict.

See `docs/INGESTION_PIPELINE.md` for a worked example.

---

## Reliability Notes

- Data acquisition runs on a dedicated background thread in `SerialManager`.
- All UI updates are event-driven via Qt signals — no polling loops.
- Replay uses the same `frame_received` path as live streaming, so the UI is tested by both.
- `detect_events()` degrades gracefully: channels shorter than 4 samples are skipped,
  and each detector has its own minimum-duration guard.

*Last Updated: April 2026*
