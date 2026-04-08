# Quick Start Guide

Boot and try the RedByte GFM HIL Suite in under 5 minutes.

---

## 1. Install

**Windows — one click:**
```
install.cmd
```

**Terminal (any OS):**
```bash
cd gfm_hil_suite
pip install -r requirements.txt
```

Always launch from the repo root (`gfm_hil_suite/`).
If your machine has multiple Python installs, use:
```powershell
.\.venv\Scripts\python.exe run.py
```

Requires Python 3.12. All dependencies (including Excel support via `openpyxl`) are
included in `requirements.txt`. For dev/test tools: `pip install -r requirements-dev.txt`.

---

## 2. Launch

```bash
python run.py
```

Or on Windows, double-click **`run.bat`**.

The app opens on **Overview** (import-first) — no hardware required.

---

## 3. What you'll see

The **Overview** page is the landing screen. Four action cards:

| Card | What it does |
|------|-------------|
| **Import Run File** | Load a real data file and start analysis |
| Open Replay | Browse timeline, events, metrics of a loaded session |
| Run Compliance | Run IEEE 2800 ride-through / frequency / recovery checks |
| Start Demo Session | Launch live diagnostics with synthetic mock telemetry |

---

## 4. Import a real file (recommended path)

1. Click **Import Run File** on the Overview page
   — or drag any supported file directly onto the window.

2. Select your file:
   - `RigolDS0.csv` / `RigolDS1.csv` — oscilloscope captures
   - `*.xlsx` — simulation Excel output (VSG frequency, inverter power, etc.)
   - `*.json` — previously saved Data Capsule sessions

3. The import dialog shows channel metadata and a **Range (min → max)** column.
   Dead or constant channels are highlighted amber.
   Assign canonical signal names if needed, then click **Import**.

4. You land on **Replay → Waveforms**. From here:
   - **Waveforms tab** — scrub the full capture timeline
   - **Events tab** — automated detectors fire; click any row to jump to that moment
   - **Compare tab** — load a second session for side-by-side delta overlay
   - **Spectrum tab** — FFT view of any channel

---

## 5. Unsupported files

If you drop or open a file that isn't analyzable data (PDF, Markdown, firmware, etc.),
the app explains what's wrong and what file types are expected — it will not crash or hang.

---

## 6. Live hardware mode

Connect the Arduino breadboard prototype on COM5, then:
```bash
python run.py --live --port COM5
```

Click **Run** in the session bar to start recording. The overview health indicator
goes green when the serial connection is established.

---

## 7. Test the suite

```bash
pytest tests/ --ignore=tests/test_ui_integration.py -q
```

408 tests pass. 3 are skipped (require pandas — `pip install pandas` to enable).

---

## Other launch flags

| Flag | Effect |
|------|--------|
| `--fullscreen` | Full-screen window |
| `--demo` | Demo telemetry mode (synthetic data) |
| `--live` | Hardware mode (auto-detect port) |
| `--live --port COM5` | Hardware mode on explicit port |
| `--no-3d` | Disable OpenGL (use if display errors occur) |

---

See `docs/DEMO_WALKTHROUGH.md` for the full 10-minute capstone demo script.
