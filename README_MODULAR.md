# VSM Evidence Workbench — Launcher Menu

The Workbench normally runs as one PyQt6 MDI desktop app
(`python -m src.main`). An alternative entry point exposes each sub-surface
as its own focused window via a launcher menu:

```bash
python src/redbyte_launcher.py
# or on Windows:
bin\launch_redbyte.bat
```

This is useful when you want to open a single tool (say, Replay Studio)
without loading the full MDI shell.

## Available launchers

| Launcher | Purpose | Source |
|----------|---------|--------|
| **Replay Studio** | Import external CSV/Excel, replay sessions, compare runs, export evidence packages. **This is the primary production workflow.** | `src/launchers/launch_replay.py` |
| **Compliance Checker** | Run a session against a standards-inspired profile and view the per-rule scorecard. | `src/launchers/launch_compliance.py` |
| **Diagnostics** | Waveform scope + fault injector + insights panel, fed by the demo adapter. Useful for UI walkthroughs; **not** a live-hardware monitor. | `src/launchers/launch_diagnostics.py` |
| **Insights** | Event-log browser for auto-detected disturbances. | `src/launchers/launch_insights.py` |
| **Signal Sculptor** | Parametric waveform generator that feeds the demo adapter so other panels have something to render. | `src/launchers/launch_sculptor.py` |

## Positioning

The launcher menu is a **UI convenience**, not a different product. All five
entry points are views onto the same underlying modules (`src/importer.py`,
`src/analysis.py`, `src/compliance_checker.py`, `src/report_generator.py`).
The authoritative product description is in the root [`README.md`](README.md).

Anything involving a *live* hardware stream (Diagnostics, Insights) runs off
the bundled demo adapter. A real-hardware input adapter is a future-work
integration hook, not a finished capability.
