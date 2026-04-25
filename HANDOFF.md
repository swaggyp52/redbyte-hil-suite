# VSM Evidence Workbench — Handoff & Run Guide

This is the single source of truth for running this project on another machine.
Read this if you are a reviewer, teammate, or evaluator who has just received
the repository.

---

## What this is

A **local Python/PyQt6 desktop application** for post-run analysis of
Virtual Synchronous Machine (VSM) / Grid-Forming inverter test data.

**There is no web server, no cloud service, no native installer.**
You run it by installing Python dependencies and running `python -m src.main`.

---

## Prerequisites

| Item | Requirement |
|------|-------------|
| Python | 3.10 or newer (3.12 recommended) |
| pip | bundled with Python 3.10+ |
| OS | Windows 10/11 (primary), Linux/macOS (supported, no batch files) |
| RAM | 4 GB minimum, 8 GB recommended |
| Display | 1280×720 minimum |
| Git | Optional — only needed if cloning |

---

## Step-by-step: Run on a clean machine

### Windows (primary)

```bat
REM 1. Get the repo (clone or unzip)
cd redbyte-hil-suite

REM 2. Create a virtual environment
python -m venv venv

REM 3. Activate it
venv\Scripts\activate

REM 4. Install dependencies
pip install -r requirements.txt

REM 5. (Optional) Install Excel + 3D-view support
pip install openpyxl PyOpenGL

REM 6. Launch the app
python -m src.main
```

### Linux / macOS

```bash
cd redbyte-hil-suite
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install openpyxl PyOpenGL       # optional
python -m src.main
```

---

## Verify it works

```bat
REM Quick check (imports + fast tests):
bin\test_system.bat

REM Full test suite:
bin\test.bat
```

Expected outcome: **94+ tests passed, 1 skipped** (Excel import test skips
unless `openpyxl` is installed).

---

## How to run the demo

```bat
bin\demo.bat
REM or:
python -m src.main --demo
```

This starts the app in demo mode with synthetic 3-phase VSM signals. No
external data file is needed. The demo adapter generates a ride-through
event sequence (frequency drift + voltage sag) and auto-loads it into the
Replay Studio.

---

## How to use the primary workflow

1. **Launch:** `python -m src.main`
2. **Import External File:** Replay Studio toolbar → *Import External File…*
   - Supports: `.csv`, `.xlsx`, `.json`
   - Wizard auto-detects column names, time units, sample rates
   - Manual override available for each channel
3. **Replay:** Waveform, Spectrum, Run Summary tabs with auto-event markers
4. **Compare:** *Load Overlay* → second run → delta metrics panel
5. **Evaluate:** profile dropdown → `ieee_2800_inspired` → run compliance
6. **Export:** *Export Evidence Report* → HTML + PNG + CSV + JSON bundle

---

## Output locations

| What | Where |
|------|-------|
| Evidence package | `exports/<session_id>/evidence_report.html` + siblings |
| Imported session | `data/sessions/<name>.json` |
| Scene snapshots | `snapshots/` |
| Demo data | `data/demo_replay.json` (auto-generated on first demo run) |

---

## Dependency quick reference

| Package | Required | Purpose |
|---------|----------|---------|
| PyQt6 | YES | UI framework |
| pyqtgraph | YES | Waveform plots |
| numpy, scipy | YES | Signal processing |
| pandas | YES | Data import |
| matplotlib | YES | Evidence-package plot export |
| python-dotenv | YES | Config |
| pyserial | YES (installed) | Demo adapter / future serial |
| openpyxl | NO | Excel (.xlsx) import |
| PyOpenGL | NO | 3D System View |
| pytest | NO | Test suite |

---

## Known limitations / caveats

1. **openpyxl not pre-installed:** Excel import is disabled until `pip install openpyxl`.
   The wizard will still open but the .xlsx file path will fail to load.
2. **PyOpenGL not pre-installed:** The 3D System View shows a "3D view unavailable"
   placeholder. All other panels work normally.
3. **venv is not committed:** The `venv/` directory lives on the development machine.
   A fresh machine must run `pip install -r requirements.txt`.
4. **snapshots/ is large:** The `snapshots/` directory contains ~1 300 PNG files
   (~75 MB) from development runs. It is safe to delete before handing off.
5. **Git ownership warning:** On Windows, if the repo was cloned by a different
   user, git may show a "dubious ownership" warning. This does not affect running
   the app — only git commands.
6. **Displays:** The app expects a desktop GUI. Headless/SSH environments will
   not work without a virtual display (Xvfb on Linux).

---

## Canonical commands summary

| Task | Command |
|------|---------|
| Install deps | `pip install -r requirements.txt` |
| Install optionals | `pip install openpyxl PyOpenGL` |
| Launch app | `python -m src.main` |
| Launch (demo) | `python -m src.main --demo` |
| Run tests | `python -m pytest tests/ -v` |
| Quick verify | `bin\test_system.bat` |
| Package for handoff | `bin\demo_launcher.bat` (runs demo + zips output) |

---

## What is NOT supported

- No web deployment
- No native `.exe` installer (PyInstaller not configured)
- No Docker container
- No CI/CD pipeline (GitHub Actions not configured)
- No live-hardware serial telemetry (demo adapter only; real-hardware adapter is
  a future integration hook documented in `docs/HARDWARE_INTEGRATION.md`)
