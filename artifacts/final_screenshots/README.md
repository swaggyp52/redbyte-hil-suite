# Final Screenshots — Handoff Note

**Project:** RedByte GFM HIL Suite  
**Captured:** 2026-05-01  
**Author:** Connor Angiel (Software Lead, Gannon University Senior Design)  
**Capture script:** `gfm_hil_suite/scripts/capture_screenshots.py`

---

## What these screenshots prove

- The full import → analyze → compare → export workflow runs end-to-end on real Rigol oscilloscope data.
- Channel mapping (CH1→v\_an, derived v\_ab/v\_bc/v\_ca) works automatically with ×100 probe scale detection.
- Waveform replay faithfully renders 3-phase AC sinusoids from a 1 M-row, 10 MSa/s CSV.
- Standards compliance (IEEE 519 THD, voltage regulation, frequency deviation) produces correct PASS/N/A decisions for the available channels.
- The event detector identifies 5 distinct anomalies (2 clipping, 2 flatline, 1 step change) in simulation data.
- The comparison engine overlays two independent datasets and computes per-channel ΔRMS and ΔTHD.
- The export pipeline writes 7 self-contained artifacts (HTML report, 2 PNGs, 3 JSONs, preview CSV) without any user file-picker interaction.

## What these screenshots do NOT prove

- Live hardware path — all shots use imported files (Demo mode). Live serial path (`--port COM5`) is implemented but not shown here.
- Full 3-phase current data — RigolDS0/DS1 contain only voltage channels. Current plots appear empty (correctly labeled as unmapped, not zeroed).
- Frequency data from the simulation files — `VSGFrequency_Simulation.xlsx` maps `Pinv → p_mech`, not a frequency channel. Shots 13–14 show the same signal structure as 11–12.
- 3D plots — `enable_3d=False` was set at launch to avoid headless OpenGL issues during capture.

---

## Quick-reference: Best 6 for slide deck

| # | File | Use for |
|---|------|---------|
| 1 | `01_home_overview_empty.png` | Opening / product intro |
| 2 | `03_import_dialog_rigol_mapped.png` | Channel mapping intelligence |
| 3 | `09_comparison_normal_vs_fault.png` | Visual centerpiece — normal vs fault |
| 4 | `12_simulation_analysis_power.png` | Event detection demo |
| 5 | `08_compliance_table.png` | Standards compliance |
| 6 | `07_metrics_summary.png` | Engineering metrics |

Full 9-slide recommended order and all 14 shots documented in `SCREENSHOT_INDEX.md`.

---

## Export package location

The evidence export captured in shot 10 lives at:

```
gfm_hil_suite/artifacts/evidence_exports/RigolDS0_20260501_105432/
├── report_RigolDS0_20260501_105432.html   (~70 KB, self-contained HTML)
├── waveform_phase.png                      (~50 KB)
├── waveform_line.png                       (~54 KB)
├── metrics.json                            (~3 KB)
├── events.json                             (<1 KB, empty for clean dataset)
├── metadata.json                           (~1 KB)
└── preview.csv                             (~485 KB)
```

Total ~662 KB / 7 artifacts.

---

## Capture environment

- OS: Windows 11
- Python: 3.12, PyQt6, pyqtgraph, numpy, scipy, matplotlib
- Display: 2560×1440 primary monitor (screenshots at native resolution)
- Import dialogs captured at 1125×960 (dialog natural size)
- Export widget captured at 1200×725
- Rigol data: `RigolDS0.csv` / `RigolDS1.csv` from OneDrive (`SeniorDesign/RigolData/`)
- Probe attenuation: ×100 (auto-detected by import pipeline; raw ~±2.3 V → displayed ~120 V RMS)

---

## Staging notes

- Run `python scripts/capture_screenshots.py` to regenerate all 14 shots.
- Requires the Rigol CSV files at `../SeniorDesign/RigolData/RigolDS0.csv` and `RigolDS1.csv`.
- Requires `InverterPower_Simulation.xlsx` and `VSGFrequency_Simulation.xlsx` in the same folder.
- The script is headless-safe (no real display required if running via virtual framebuffer).
- All 14 PNGs will be overwritten in-place; the `SCREENSHOT_INDEX.md` does not auto-update.
