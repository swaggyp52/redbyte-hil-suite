# System Architecture

## Overview

The GFM HIL Suite is a PyQt6 desktop application with three layers:

1. **IO & ingestion** — adapters for live hardware, file parsers for captured data
2. **Core services** — signal processing, event detection, compliance, session management
3. **UI** — 6-page shell with widgets for waveforms, events, comparison, compliance

The app exposes **two input modes that share one unified session pipeline**:

| Mode | Entry point | Normalisation | Session object |
|------|-------------|---------------|----------------|
| **Imported file** (CSV/Excel/JSON) | `ImportDialog` → `ingest_file()` | `ChannelMapper.apply()` → `dataset_to_session()` | `ActiveSession.from_capsule(capsule)` |
| **Live telemetry** (Demo/Serial/OPAL-RT) | `SerialManager` → `normalize_frame()` → `Recorder` | `normalize_frame()` in real-time | `Recorder.to_capsule()` → `ActiveSession.from_capsule(capsule)` |

Both paths produce the same **Data Capsule v1.2** dict and the same `ActiveSession` object.
All downstream analysis (ReplayStudio, EventLane, CompliancePage) consumes either without distinction.

---

## Module Layout

### `src/` — Backend

| Module | Purpose |
|--------|---------|
| `io_adapter.py` | Adapter base class + `DemoAdapter` (mock 3-phase), `SerialAdapter` (UART), `OpalRTAdapter` (TCP stub) |
| `serial_reader.py` | `SerialManager` — background thread reads frames, calls `normalize_frame()`, tracks `LiveStats` (fps, present channels, warnings), emits `frame_received` and `live_stats_updated` Qt signals |
| `models.py` | `normalize_frame()` — single normalization point for **all** adapter outputs; `present_canonical_keys()` — frozenset of channels that had real source data (not zero-filled); Arduino key aliases + pre-alias unit scaling |
| `signal_processing.py` | `compute_rms()`, `compute_thd()` (FFT), `compute_phasor()` (Hilbert), `compute_step_metrics()` |
| `recorder.py` | Records live frames to a Data Capsule v1.2 JSON session file; `to_capsule()` returns in-memory capsule without saving (used for live→analysis bridge) |
| `replayer.py` | Replays a recorded session, emitting frames via `frame_received` at playback speed |
| `insight_engine.py` | Anomaly detection with 3-second debounce; clusters events by type; feeds `InsightsPanel` |
| `compliance_checker.py` | Simplified IEEE 2800: 3 rules — ride-through (≥50% nominal), freq stability (±0.5 Hz), voltage recovery |
| `file_ingestion.py` | `ingest_file()` → `ImportedDataset`; handles Rigol CSV (stdlib csv, chunked, NaN trimming), Excel (first non-empty sheet), Data Capsule JSON |
| `channel_mapping.py` | `ChannelMapper`, `auto_suggest_mapping()`, `UNMAPPED` sentinel; profile persistence (JSON) |
| `dataset_converter.py` | `dataset_to_session()` — converts `ImportedDataset` to Data Capsule v1.2; decimation to ≤4000 frames; full-res preserved in `capsule["_dataset"]` |
| `session_state.py` | `ActiveSession` dataclass — in-memory descriptor of the current live/imported session; `from_capsule()` factory works for both paths |
| `event_detector.py` | `DetectedEvent` dataclass + `detect_events(dataset)` — 8 batch detectors; sorted by `ts_start` |
| `comparison.py` | `find_overlapping_channels()`, `align_datasets()`, `compare_channels()`, `generate_delta_trace()`, `compare_datasets()`, `dataset_from_capsule()` |

### `ui/` — User Interface

| Module | Purpose |
|--------|---------|
| `app_shell.py` | `AppShell` — unified single-window shell; owns all managers; wires all Qt signals; bridges live→analysis on recording stop |
| `pages/overview_page.py` | Overview — Import Run File (primary action), Start Demo Session (secondary), `DatasetInfoPanel` |
| `pages/diagnostics_page.py` | Diagnostics — `LiveStatusPanel` (source badge, fps, channels, warnings) + fault injector + real-time waveform view |
| `pages/replay_page.py` | Replay — hosts `ReplayStudio`; wires `load_imported_session()` |
| `pages/compliance_page.py` | Compliance — scorecard display; Run Compliance Check button |
| `pages/console_page.py` | Console — single-screen live overview: metrics header, scope, phasor, insights |
| `pages/tools_page.py` | Tools — developer configuration panel |
| `live_status_panel.py` | `LiveStatusPanel` — compact live telemetry status bar (source badge, fps, active channels, stale detection, warnings) |
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
   ActiveSession.from_capsule()              ← session_state.py
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
   present_canonical_keys(raw)               ← models.py (track what was ACTUALLY measured)
         |
   normalize_frame(raw)                      ← models.py (aliases + unit scaling + 0-fill)
         |
         v
   SerialManager (LiveStats tracking)        ← fps, present_channels, warnings
         |
         v
   frame_received (Qt signal)
         |
         ├── Recorder                        ← logs to in-memory buffer
         ├── InsightEngine                   ← anomaly detection + clustering
         ├── InverterScope                   ← real-time waveform scope
         ├── PhasorView                      ← phasor diagram
         ├── Console metrics header          ← FREQ / RMS / THD / P
         └── live_stats_updated (Qt signal)  → LiveStatusPanel (fps, channels, warnings)

   [User clicks Stop]
         |
         v
   Recorder.to_capsule()                     ← in-memory Data Capsule (same schema as import)
         |
         v
   ActiveSession.from_capsule(capsule)       ← source_type="live"
         |
         v
   ─── SAME analysis pipeline as Import path ───
   ReplayStudio / EventLane / CompliancePage
```

---

## Hardware Truth — Current State

The real breadboard hardware (Arduino Uno + potentiometer) sends:

```json
{"t_ms": 499, "vdc": 449.3, "freq": 60.03, "p_kw": 0.99, "q_kvar": 0.20, "fault": 0}
```

After `normalize_frame()` and `present_canonical_keys()`:
- **Measured channels**: `v_dc`, `freq`, `p_mech`, `q`, `status`
- **Zero-filled** (not measured): `v_an`, `v_bn`, `v_cn`, `i_a`, `i_b`, `i_c`
- `SerialManager` emits a **DC bus only** warning in `LiveStats.warnings`
- `LiveStatusPanel` displays the warning so the operator knows the source is partial

The full 3-phase inverter hardware (not yet built) will send complete waveform data.
Until it exists, 3-phase channels remain truthfully absent — see **Invariant 2** below.

---

## Key Invariants

1. **`normalize_frame()` is the only normalization point.** Never read raw adapter output
   directly in UI code or analytics.

2. **No signal fabrication.** If a channel is absent from the source, it does not
   exist downstream. Code must check `if "v_bn" in frame` rather than read a default.
   `present_canonical_keys()` makes the measured subset explicit and testable.

3. **Full-resolution data for analysis.** `capsule["_dataset"]` contains all samples from
   the original file. Event detection and FFT always use this, not the decimated frame list.

4. **EventLane is compute-only.** `detect_events()` is a pure batch function with no side
   effects. It is called from `_update_event_lane()` after session load, never from a timer.

5. **Live sessions use the same pipeline as imported files.** `Recorder.to_capsule()`
   produces the same Data Capsule v1.2 format as `dataset_to_session()`. Both feed
   `ActiveSession.from_capsule()` and the same downstream analysis components.

---

## Adding a New Hardware Source

1. Subclass `IOAdapter` in `src/io_adapter.py`
2. Add `_KEY_ALIASES` and `_PRE_ALIAS_SCALE` entries to `normalize_frame()` in `src/models.py`
3. Register the adapter in `SerialManager.connect_serial()` — add a port-name check
4. Optionally add channel-presence warnings in `SerialManager._update_stats()`

No UI changes are needed — waveform scope, phasor view, event detectors, and compliance
checker all autodiscover available channels from the normalized frame dict.

See `docs/INGESTION_PIPELINE.md` for a worked example.

---

## Launch Modes

| Command | Adapter | Live port |
|---------|---------|-----------|
| `python run.py` | DemoAdapter (mock 3-phase) | n/a |
| `python run.py --live` | SerialAdapter (port from `config/system_config.json`) | COM port in config |
| `python run.py --live --port COM5` | SerialAdapter | COM5 |
| `python run.py --live --port OPAL` | OpalRTAdapter | TCP 127.0.0.1:5100 |

---

## Reliability Notes

- Data acquisition runs on a dedicated background thread in `SerialManager`.
- All UI updates are event-driven via Qt signals — no polling loops.
- Replay uses the same `frame_received` path as live streaming, so the UI is tested by both.
- `detect_events()` degrades gracefully: channels shorter than 4 samples are skipped,
  and each detector has its own minimum-duration guard.

*Last Updated: April 2026*
