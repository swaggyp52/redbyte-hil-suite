# File Ingestion Pipeline — Engineering Notes

**Context:** The GFM HIL Suite was originally a mock-telemetry app that fabricated 3-phase
waveforms through DemoAdapter. This document describes the real-file ingestion pipeline added
in April 2026 to make it an actual engineering analysis platform for capstone work.

---

## Architecture Changes

### New Modules

| Module | Purpose |
|--------|---------|
| `src/file_ingestion.py` | Auto-detect and parse CSV / Excel / JSON files into `ImportedDataset` |
| `src/channel_mapping.py` | Map source column names to canonical engineering names; persist profiles |
| `src/dataset_converter.py` | Convert `ImportedDataset` → Data Capsule v1.2 dict for replay/analysis |
| `ui/import_dialog.py` | Two-panel Qt dialog: file metadata left, channel mapping table right |

### Modified Modules

**`src/models.py`** — `normalize_frame()` now handles Arduino hardware keys:

```
t_ms  → ts  (and scaled ÷ 1000  so the value is in seconds)
vdc   → v_dc
p_kw  → p_mech  (and scaled × 1000 so the value is in watts)
q_kvar → q     (and scaled × 1000 so the value is in VAR)
fault → status
```

Pre-alias scaling runs before the alias rename so downstream code always sees SI units.

**`src/serial_reader.py`** — `_reader_loop()` now calls `normalize_frame(frame)` before
emitting `frame_received`. All adapters (Serial, OpalRT, Demo) go through the same
normalization path automatically.

**`ui/replay_studio.py`** — `_render_all_sessions()` now auto-detects plottable channels
instead of hardcoding `v_an/v_bn/v_cn`. If canonical phase names are present they are
preferred; otherwise any numeric channel (up to 6) are plotted. An `import_meta` notice
is shown when an imported file with unmapped channels is loaded.

**`ui/pages/overview_page.py`** — "Import Run File" is now the primary action card.
"Start Demo Session" is secondary and explicitly labeled `[Demo]` to prevent confusion.

**`ui/app_shell.py`** — Wired `import_run_requested` → `_open_import_dialog()` →
`ImportDialog` → `_on_session_imported()` → `ReplayStudio.load_session_from_dict()`.

### Data Flow (Import Path)

```
User selects file (CSV / XLSX / JSON)
        |
        v
  ingest_file(path)          ← file_ingestion.py
        |
        v
  ImportedDataset             ← numpy arrays, original header names, warnings
        |
        v
  auto_suggest_mapping()     ← channel_mapping.py
  User edits mapping in UI   ← ui/import_dialog.py
        |
        v
  ChannelMapper.apply()      ← returns new ImportedDataset with renamed channels
        |
        v
  dataset_to_session()       ← dataset_converter.py
        |
   ┌────┴────────────────────────┐
   │ Data Capsule dict (v1.2)    │  ← frames decimated to ≤ 4000 for replay
   │   + capsule["_dataset"]     │  ← full-res ImportedDataset for FFT/THD
   └────────────────────────────┘
        |
        v
  ReplayStudio.load_session_from_dict()
```

---

## Assumptions

1. **No silent signal fabrication.** If `v_bn` is not in the source file, it will not appear
   in frames. Downstream code must test `if "v_bn" in frame` rather than read a default 0.

2. **Rigol CH1–CH4 are not phase voltages.** They are oscilloscope probe inputs. The
   auto-suggest mapping leaves them `__unmapped__`. A human must explicitly assign
   `CH1(V) → v_an` (or whatever the probe was measuring) in the Import dialog.

3. **Rigol fill value `9.9e37`.** Rigol firmware outputs this sentinel beyond the trigger
   window. Any value `|x| > 1e30` is treated as NaN and the trailing NaN rows are trimmed.

4. **Excel first-non-empty sheet.** `_ingest_simulation_excel` reads the first sheet that
   has at least one row and one column. If the workbook has a blank cover sheet, it is
   skipped automatically.

5. **Time axis normalization.** All ingestors subtract `time[0]` so the returned time
   array starts at exactly 0.0 seconds, regardless of the original timestamp origin.

6. **Sample rate estimation uses median inter-sample interval.** Zero or negative deltas
   (from duplicated rows or rounding) are ignored. The result is rounded to 2 decimal
   places.

7. **Decimation preserves endpoints.** `np.linspace` index selection is used so the first
   and last samples always appear in the decimated frame list.

8. **Full-resolution data.** The `ImportedDataset` is attached as `capsule["_dataset"]`
   in the converted capsule. Any analysis that needs all samples (FFT, THD, spectral
   density) should read from `capsule["_dataset"].channels[name]`, not the decimated
   frames.

---

## How to Import Files

### From the UI

1. Launch the application (`python run.py`).
2. The Overview page loads. Click **Import Run File** (the primary action card).
3. In the Import dialog, click **Browse** and select a `.csv`, `.xlsx`, or `.json` file.
4. The left panel shows file metadata and any parse warnings.
5. The right panel shows each source column and a dropdown for its canonical target:
   - Columns with recognised names (e.g. `Pinv`, `Van`) are pre-filled.
   - Rigol channels (`CH1(V)`…`CH4(V)`) are left as `[unmapped — keep original]`.
   - Change dropdowns as needed (e.g. `CH1(V) → v_an`).
6. Optionally: **Load Profile** to apply a saved mapping, or **Save Profile** to keep
   this mapping for future files from the same instrument.
7. Click **Import**. The Replay page opens automatically and the waveforms are plotted.

### From Python

```python
from src.file_ingestion import ingest_file
from src.channel_mapping import ChannelMapper, auto_suggest_mapping
from src.dataset_converter import dataset_to_session, get_channel_full_res

# Ingest
ds = ingest_file("RigolDS0.csv")

# Map channels
mapping = auto_suggest_mapping(ds.raw_headers)
mapping["CH1(V)"] = "v_an"   # assign manually
mapping["CH2(V)"] = "v_bn"
mapper = ChannelMapper()
ds_mapped = mapper.apply(ds, mapping)

# Convert to session
capsule = dataset_to_session(ds_mapped, session_id="run_001")

# Full-res analysis
t, v_an = get_channel_full_res(ds_mapped, "v_an")
# → use numpy arrays (all rows, not decimated) for scipy FFT, etc.
```

### Supported Formats

| Format | Notes |
|--------|-------|
| `.csv` | Rigol DSO captures. Handles metadata preamble lines, 100k-row chunked read, up to 2M rows. |
| `.xlsx` / `.xls` | Simulation Excel output. Requires `openpyxl`. Reads first non-empty sheet. |
| `.json` | Existing Data Capsule session files. Direct reload into ReplayStudio. |

---

## How Future Live MCU Support Plugs In

The ingestion pipeline and the live-streaming path share the same **canonical frame
format** downstream. To add a new live source:

### Step 1 — Write an Adapter

Create a class in `src/io_adapter.py` (or a new file) that inherits `IOAdapter`:

```python
class MyNewAdapter(IOAdapter):
    def read_frame(self) -> dict | None:
        # Read from hardware, return raw dict with whatever keys the hardware sends
        ...
    def send_command(self, cmd: str) -> None:
        ...
```

### Step 2 — Add Aliases to `normalize_frame()`

In `src/models.py`, add entries to `_KEY_ALIASES` (and `_PRE_ALIAS_SCALE` if unit
conversion is needed):

```python
_PRE_ALIAS_SCALE = {
    "t_ms":   1e-3,   # existing
    "p_kw":   1e3,
    # add new hardware keys here:
    "v_ll":   1.0,    # e.g. line-line voltage already in volts
}

_KEY_ALIASES = {
    "t_ms": "ts",     # existing
    # add new mappings:
    "v_rms_a": "v_an",   # example RMS phasor voltage label
}
```

`normalize_frame()` is called in `SerialManager._reader_loop()` before the frame is
emitted on `frame_received`, so all downstream consumers (Recorder, InsightEngine,
UI widgets) see canonical names automatically.

### Step 3 — Register the Adapter

In `AppShell._init_backends()` (or config-driven):

```python
if config.get("adapter") == "my_new_hw":
    self.serial_mgr.set_adapter(MyNewAdapter(port=config["port"]))
```

### Step 4 — No UI Changes Needed

Because `ReplayStudio._render_all_sessions()` and `InverterScope` both auto-detect
available channels, a new hardware source that produces `v_an / v_bn / v_cn` will
render three-phase waveforms immediately. A source that produces only `v_dc / freq`
will render the two channels it has and leave the rest absent — which is correct.

### Current Hardware Status (April 2026)

The Arduino Uno R3 prototype produces `t_ms, vdc, freq, p_kw, q_kvar, fault` — a
5-field summary frame representing the DC bus. It does **not** produce 3-phase
voltages or currents because the full 3-phase VSI hardware is not yet built. The
`normalize_frame()` aliases above translate these fields so they appear in
the correct canonical slots when the live serial port is connected.

To test with the real Arduino (COM5, 115200 baud):

```bash
python run.py --port COM5 --baud 115200
```

or update `config/system_config.json`:

```json
{
  "serial_port": "COM5",
  "baud_rate": 115200
}
```

Once the full 3-phase inverter hardware is built and produces the expanded frame
(v_an, v_bn, v_cn, i_a, i_b, i_c, …), add the corresponding aliases and the
entire software stack — scope, phasor view, compliance checker, FFT analysis —
will work without further UI modifications.

---

## Test Coverage

| Test file | What it covers |
|-----------|---------------|
| `tests/test_file_ingestion.py` | Rigol CSV (basic, NaN trimming, no fabrication), Excel (duplicate detection, time axis), JSON, error conditions, helper functions |
| `tests/test_channel_mapping.py` | auto_suggest rules (CH1–CH4 always UNMAPPED), infer_unit, apply() rename/conflict/immutability, profile persistence |
| `tests/test_dataset_converter.py` | Decimation, frame content (no fabrication, no NaN, absent fields absent), metadata, save/load round-trip, full-res access, statistics |

Run the ingestion suite:

```bash
cd gfm_hil_suite
pytest tests/test_file_ingestion.py tests/test_channel_mapping.py tests/test_dataset_converter.py -v
```

Expected result: **69 passed**.
