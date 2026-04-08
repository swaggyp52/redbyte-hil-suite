# RedByte GFM HIL Suite

Grid-Forming Inverter Hardware-in-the-Loop diagnostics and validation platform.

---

## Quick Start

**Windows — double-click to install everything:**
```
install.cmd
```

**Then launch:**
```
run.bat
```

**Or from terminal (any OS):**
```bash
pip install -r requirements.txt
python run.py
```

Launches in demo mode with mock telemetry — no hardware required.

---

## Launch Options

| Command | Mode |
|---|---|
| `python run.py` | Demo mode, windowed |
| `python run.py --fullscreen` | Demo mode, fullscreen |
| `python run.py --live` | Live hardware mode |
| `python run.py --no-3d` | Disable 3D (if OpenGL unavailable) |

---

## Setup (first time)

**Windows (one double-click):**
```
install.cmd
```

**Any OS (terminal):**
```bash
pip install -r requirements.txt
```

For dev/testing (optional):
```bash
pip install -r requirements-dev.txt
```

Requires Python 3.12. See `docs/FRESH_MACHINE_SETUP.md` for detailed steps.

---

## Capabilities

- **Import & analyze** Rigol oscilloscope captures (CSV), simulation output (Excel), or saved sessions (JSON)
- **Automated event detection** — 8 deterministic detectors: voltage sag/swell, frequency excursion, flatline, step change, clipping, duplicate channels, THD spike
- **Engineering summary cards** — worst sag depth, max freq deviation, max THD, max flatline duration per session
- **Jump-to-event replay** — click any detected event to seek the waveform scrubber to that timestamp
- **Inline annotations** — double-click any event row to add a note
- **Session comparison** — dual-load overlay with delta traces and per-channel statistics
- **IEEE 2800 compliance scorecard** — automated ride-through, frequency stability, and recovery checks
- **Live demo mode** — synthetic 3-phase VSM telemetry for presentations without hardware

---

## Demo Walkthrough

**Import-first (recommended — uses real data):**
1. App opens on **Overview** — click **Import Run File**
2. Select a CSV/Excel/JSON file; assign channel mappings in the dialog
3. **Replay → Waveforms** — scrub the full capture timeline
4. **Replay → Events** — automated event detection; click any row to jump to that moment
5. **Replay → Compare** — load a second session for side-by-side comparison
6. **Compliance** — run IEEE 2800 checks against the imported data

**Demo mode (no file needed):**
1. **Overview → Start Demo Session** (labeled [Demo])
2. **Diagnostics → Inject Voltage Sag** — anomaly appears in insights panel
3. **Replay → Waveforms** — scrub the recorded fault window
4. **Compliance → Run Compliance Check**

Full script: `docs/DEMO_WALKTHROUGH.md`

---

## Project Layout

```
gfm_hil_suite/
├── run.py              ← entry point
├── run.bat             ← double-click launcher (Windows)
├── install.cmd         ← one-click full setup (Windows)
├── Makefile            ← make install / run / test (Unix/Git Bash)
├── requirements.txt    ← runtime deps (pip install -r requirements.txt)
├── requirements-dev.txt← dev/test deps (pytest, openpyxl, black, mypy)
├── src/                ← backend: signal processing, compliance, recorder, I/O
│   └── main.py
├── ui/                 ← PyQt6 shell and widgets
│   ├── app_shell.py    ← unified window shell
│   ├── pages/          ← Overview, Diagnostics, Replay, Compliance, Console, Tools
│   └── style.py        ← global stylesheet
├── data/
│   ├── sessions/       ← recorded sessions (auto-created)
│   └── demo_sessions/  ← bundled demo sessions
├── exports/            ← HTML reports, CSV exports (auto-created)
├── docs/               ← reference docs
└── tests/              ← pytest suite (352 passing)
```

---

## Tests

```bash
# Run all tests (display server not required)
pytest tests/ --ignore=tests/test_ui_integration.py -q
```

352 tests passing across signal processing, file ingestion, channel mapping,
event detection, session comparison, compliance, and live telemetry subsystems.
3 tests intentionally skipped (openpyxl not installed — Excel import tests bypass automatically).

---

## Reference Docs

| Doc | Contents |
|-----|---------|
| `docs/PROJECT_OVERVIEW.md` | What this is, capabilities, architecture summary |
| `docs/architecture.md` | Module layout, data flow diagrams, key invariants |
| `docs/DEMO_WALKTHROUGH.md` | 10-minute capstone demo script |
| `docs/INGESTION_PIPELINE.md` | Import pipeline, data format assumptions, adding new hardware |
| `docs/HARDWARE_INTEGRATION.md` | Serial protocol, firmware requirements, troubleshooting |
| `docs/FRESH_MACHINE_SETUP.md` | First-time install steps |
