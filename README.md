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

## Fresh Windows Install

1. Download the GitHub ZIP.
2. Extract it to a normal folder.
3. Double-click `install.cmd`.
4. Wait for setup to finish.
5. Double-click `run.bat`.

`install.cmd` now handles the full end-user setup flow:

- finds an existing Python 3.12+ runtime when available
- installs Python 3.12 for the current user when needed
- creates the project `.venv`
- installs runtime dependencies
- runs a package self-check
- runs smoke validation that does not depend on private OneDrive files

Supported bootstrap targets: Windows 11 x64 and ARM64.
## Launch

**Windows (double-click or terminal):**

```bat
run.bat
```

`run.bat` uses only the project `.venv\Scripts\python.exe` and launches `run.py`.
If `.venv` is missing or broken, rerun `install.cmd`.

**Alternative (already inside the project `.venv`):**

```powershell
.\.venv\Scripts\python.exe run.py
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

Evidence export writes real analysis artifacts under `artifacts/evidence_exports/<session>_<timestamp>/`, including:

- `report_<session>_<timestamp>.html` — self-contained HTML engineering report
- `waveform_phase.png` — phase-to-neutral voltage waveforms (PNG)
- `waveform_line.png` — line-to-line voltage waveforms (PNG)
- `metrics.json` — computed engineering metrics (RMS, THD, frequency, etc.)
- `compliance.json` — standards-inspired check results with PASS/FAIL/N/A per rule (written only when compliance has been run)
- `events.json` — detected power-quality events
- `metadata.json` — session provenance (source file, mapping, scale factors, sample count)
- `preview.csv` — normalized session data (downsampled to 20 k rows for large captures)

Up to 8 artifacts total. `compliance.json` is written only when the Compliance page has been opened and checks have been run before export. For very large captures, `preview.csv` is a downsampled preview; full-resolution export is a known future-work item.

## Sample Data

Bundled sample files are in `sample_data/`:

- `sample_data/demo_three_phase.csv`
- `sample_data/demo_session.json`

Use **Import Run File** and choose one of those files on a fresh install.

Optional local senior-design validation files can still be used when available, but the packaged install and smoke validation no longer depend on them.

## Troubleshooting

If Windows SmartScreen appears:

- click **More info**
- click **Run anyway**

If `install.cmd` cannot download Python:

- check the internet connection
- install Python 3.12 or newer manually
- rerun `install.cmd`

If the app does not open:

- run `run.bat` from Command Prompt
- keep the console open and capture the error text

If your own data files are not ready yet:

- use **Import Run File** and choose a CSV, XLSX, or JSON file
- bundled examples are in `sample_data/`

## Known Limitations

- Excel simulation files in the current dataset folder expose `Pinv` only, so compliance remains `N/A` without voltage or frequency channels.
- Current and fault checks remain `N/A` unless the imported dataset actually includes those channels.
- The default evidence bundle exports a preview CSV for very large captures; full-resolution CSV export can still be added later if needed.

## Future Work

- richer scale-factor and probe-calibration workflow
- explicit full-resolution CSV export toggle in the UI
- broader simulation auto-mapping for more power-system file layouts
