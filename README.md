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
python -m playwright install chromium
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
python -m playwright install chromium
```

Requires Python 3.12. See `docs/FRESH_MACHINE_SETUP.md` for detailed steps.

---

## Demo Walkthrough

1. App opens on **Overview** — click **Start Demo Session**
2. **Console** — single-screen view: live waveforms, phasor diagram, metrics header
3. Navigate to **Diagnostics** — click **Inject Voltage Sag** — anomaly appears in insights panel
4. Click **Replay** in the sidebar — session loads automatically, scrub the timeline
5. Click **Compliance** — run IEEE 2800 checks, see the scorecard fill in
6. Export HTML report or CSV from the compliance page

Full script: `docs/DEMO_WALKTHROUGH.md`

---

## Project Layout

```
gfm_hil_suite/
├── run.py              ← entry point
├── run.bat             ← double-click launcher (Windows)
├── install.cmd         ← one-click full setup (Windows)
├── Makefile            ← make install / run / test (Unix/Git Bash)
├── requirements.txt    ← pip install -r requirements.txt
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
└── tests/              ← pytest suite
```
