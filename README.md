# VSM Evidence Workbench

Local Python/PyQt6 desktop application for offline recorded-session analysis.

## What It Is

- local-first recorded-data analysis workbench
- deterministic post-run waveform and metric review
- standards-inspired engineering checks
- evidence package generation for reports, plots, and normalized data

## What It Is Not

- live monitoring product
- cloud dashboard
- Blynk application
- UART streaming deliverable
- hardware control or formal certification tool

## Launch

```powershell
.\.venv\Scripts\python.exe -m src.main
```

The app opens to **Overview**. After import, it stays on the dataset overview screen and pre-loads Replay and Compliance in the background.

## Supported Inputs

- `CSV`
- `XLSX` / `XLS`
- `JSON` saved session capsules

Supported datasets include:

- three-phase oscilloscope captures
- simulation exports
- generic numeric CSV files with a time column
- generic numeric CSV files without inverter-specific channel names

## Main Product Workflow

1. Import a recorded file from **Overview**.
2. Review the import preview:
   raw columns, detected time column, canonical mappings, derived channels, and generic channels.
3. Use **Overview** to confirm:
   source file, sample count, sample rate, analysis mode, mapped channels, derived channels, and missing expected channels.
4. Open **Replay & Analysis** to inspect:
   phase voltages, line-to-line overlays, current or clean N/A messaging, auxiliary channels, metrics, spectrum, events, and comparison.
5. Open **Compliance** to run:
   `project_demo`, `ieee_2800_inspired`, or `ieee_519_thd`.
6. Export the evidence package.

## Generic Data Workflow

Files that do not map to a full inverter session still import successfully when they contain numeric columns.

The app will:

- use a detected time-like column when present
- preserve numeric columns for plotting
- compute basic stats such as min, max, mean, RMS, peak-to-peak, sample count, and time window
- mark VSM-specific compliance checks as `N/A` with an explicit reason when required channels are missing

## Evidence Export

Evidence export writes real analysis artifacts under `exports/`, including:

- `evidence_report.html`
- `waveform_overview.png`
- `line_to_line_overlay.png`
- `normalized_frames.csv`
- `metrics.json`
- `compliance.json`
- `events.json`
- `metadata.json`
- `session_capsule.json`

For very large captures, `normalized_frames.csv` defaults to a preview/downsampled export so the package completes quickly. Metrics and compliance values are still computed from the real imported analysis context.

## Demo-Validated Files

- `RigolDS0.csv`
- `RigolDS1.csv`
- `InverterPower_Simulation.xlsx`
- `VSGFrequency_Simulation.xlsx`

## Known Limitations

- Excel simulation files in the current dataset folder expose `Pinv` only, so compliance remains `N/A` without voltage or frequency channels.
- Current and fault checks remain `N/A` unless the imported dataset actually includes those channels.
- The default evidence bundle exports a preview CSV for very large captures; full-resolution CSV export can still be added later if needed.

## Future Work

- richer scale-factor and probe-calibration workflow
- explicit full-resolution CSV export toggle in the UI
- broader simulation auto-mapping for more power-system file layouts
