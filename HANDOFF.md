# VSM Evidence Workbench - Final Handoff

## Final Product Summary

This repository now presents a real offline evidence workbench for recorded inverter, simulation, and generic numeric datasets.

Primary product behavior:

- import recorded data from `CSV`, `XLSX`, or `JSON`
- map source columns to canonical engineering channels
- derive `v_ab`, `v_bc`, `v_ca` when phase voltages exist
- inspect phase, line-to-line, current, and auxiliary plots
- compute metrics and event summaries
- run standards-inspired engineering checks
- compare baseline vs disturbed sessions
- export a real evidence package

## Product Truth

The app is:

- local-first
- offline
- deterministic
- post-run analysis
- evidence generation
- standards-inspired validation

The app is not:

- live monitoring
- Blynk
- cloud dashboard
- hardware control
- formal certification

Demo and adapter-preview pages still exist as secondary surfaces, but the final deliverable path is recorded-data analysis.

## Launch

**Windows (double-click or terminal):**

```bat
run.bat
```

`run.bat` locates the project `.venv`, checks Python 3.12+, installs missing
dependencies, and launches `run.py`. It is the supported user launcher.

**Alternative (already inside `.venv`):**

```powershell
.\.venv\Scripts\python.exe run.py
```

## Import Experience

The import dialog now shows:

- detected file type
- row count
- numeric column count
- detected time column
- source-to-canonical mapping suggestions
- derived channels that will be computed
- generic or auxiliary numeric channels that will remain available
- analysis mode after import

After import, the app stays on **Overview** and shows a dataset summary before you move into Replay or Compliance.

## Supported Data Types

- `CSV`
- `XLSX` / `XLS`
- `JSON` session capsules

Validated examples:

- `RigolDS0.csv`
- `RigolDS1.csv`
- `InverterPower_Simulation.xlsx`
- `VSGFrequency_Simulation.xlsx`
- generic numeric CSV with `time,signal_a,signal_b`

## VSM Workflow

1. Launch the app.
2. Import `RigolDS0.csv`.
3. Map:
   `CH1(V)->v_an`, `CH2(V)->v_bn`, `CH3(V)->v_cn`
4. Confirm Overview shows:
   mapped channels, derived channels, analysis mode, and missing channels.
5. Open **Replay & Analysis**.
6. Show:
   phase voltages, line-to-line overlay, metrics, events, and spectrum.
7. Open **Compliance** and run `ieee_2800_inspired`.
8. Export the evidence package.

## Generic Data Workflow

If a dataset does not provide full inverter channels, the app still imports it when it has numeric columns.

Behavior:

- time-like columns are used for the x-axis when detected
- numeric channels remain available for plotting
- basic stats are shown for generic or auxiliary channels
- compliance rows become `N/A` with explicit reasons when required channels are missing

## Evidence Export

The evidence bundle is written to `artifacts/evidence_exports/<session>_<timestamp>/` and includes:

- `report_<session>_<timestamp>.html` — self-contained HTML engineering report
- `waveform_phase.png` — phase-to-neutral voltage waveforms (PNG)
- `waveform_line.png` — line-to-line voltage waveforms (PNG)
- `metrics.json` — computed engineering metrics (RMS, THD, frequency, balance)
- `compliance.json` — standards-inspired check results (written only when compliance has been run)
- `events.json` — detected power-quality events list
- `metadata.json` — session provenance (source file, mapping, scale factors, sample count)
- `preview.csv` — normalized session data (downsampled to 20 k rows for large captures)

Up to 8 artifacts. `compliance.json` is only written when the Compliance page has been opened and checks run before export. The metadata file records the downsampling note explicitly for large captures.

## Final Demo Path

1. Launch `run.bat` (double-click or terminal from project root)
2. Import `RigolDS0.csv`
3. Show Overview
4. Open Replay and show phase plus line-to-line plots
5. Open Metrics
6. Open Compliance
7. Load `RigolDS1.csv` as comparison
8. Show line-to-line comparison overlays
9. Import `InverterPower_Simulation.xlsx`
10. Show the power-channel stats
11. Export the evidence bundle

## Known Limitations

- Current and explicit fault checks remain `N/A` unless the imported file actually contains those channels.
- The current Excel simulation samples only expose `Pinv`, so compliance remains `N/A` there by design.
- Full-resolution CSV export is not the default path for million-row captures; preview CSV export is used to keep the evidence bundle responsive.

## Future Work

- explicit UI toggle for full-resolution normalized CSV export
- richer scale-factor workflow for probes and sensors
- broader auto-mapping heuristics for additional simulation formats
