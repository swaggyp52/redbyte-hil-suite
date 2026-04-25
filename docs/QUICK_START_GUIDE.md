# VSM Evidence Workbench — Quick Start Guide

**What this is:** A local desktop engineering analysis tool for VSM / Grid-Forming
inverter test data. Import a CSV/Excel lab export → replay → compare →
standards-evidence evaluation → export HTML + JSON + CSV artifacts.

---

## Prerequisites

| Requirement | Minimum | Notes |
|-------------|---------|-------|
| Python | 3.10+ | [python.org](https://python.org) |
| OS | Windows 10/11 | Linux/Mac work but batch files are Windows |
| RAM | 4 GB | 8 GB recommended for large captures |
| Display | 1280×720 | 1920×1080 recommended |

---

## Install

```bat
REM Clone or unzip the repository, then:
cd redbyte-hil-suite

REM Create a virtual environment (recommended)
python -m venv venv
venv\Scripts\activate

REM Install core dependencies
pip install -r requirements.txt
```

### Optional dependencies

```bat
REM Excel import (.xlsx / .xls files in the Import Wizard)
pip install openpyxl

REM 3D System View panel
pip install PyOpenGL

REM Or install everything at once:
pip install -r requirements.txt openpyxl PyOpenGL
```

---

## Launch

### Primary launch (full MDI workbench)

```bat
REM From the repo root with venv active:
python -m src.main

REM Or use the batch file:
bin\start.bat
```

### Demo mode (synthetic data, no import needed)

```bat
bin\demo.bat
REM or:
python -m src.main --demo
```

### Launcher menu (choose a focused sub-app)

```bat
bin\launch_redbyte.bat
```

---

## Verify the install

```bat
bin\test_system.bat
REM Checks imports, optional deps, and runs fast unit tests.
```

Full test suite:

```bat
bin\test.bat
REM or:
python -m pytest tests/ -v
```

Expected: **94+ passed, 1 skipped** (Excel test skips if openpyxl is absent).

---

## The core workflow (in ~3 minutes)

1. Launch → `python -m src.main`
2. **Replay Studio → Import External File…** — drop a lab CSV. Wizard auto-maps columns.
3. Replay tab: waveform, event markers, spectrum, run summary.
4. Load Overlay for a second run → view comparison metrics.
5. Switch profile → `ieee_2800_inspired` → run standards evaluation.
6. **Export Evidence Report** → opens `exports/<run>/evidence_report.html`.

---

## Output locations

| Artifact | Default location |
|----------|-----------------|
| Evidence package | `exports/<session_id>/` |
| Session capsule | `data/sessions/<name>.json` |
| Scene snapshots | `snapshots/` |

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `ModuleNotFoundError: PyQt6` | `pip install PyQt6` |
| 3D view shows placeholder | `pip install PyOpenGL` |
| Excel import greyed out | `pip install openpyxl` |
| `venv not found` error | Run `python -m venv venv` first |
| Window doesn't appear | Check display scaling; try `QT_SCALE_FACTOR=1` |
