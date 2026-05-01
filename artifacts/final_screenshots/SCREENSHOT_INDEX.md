# VSM Evidence Workbench — Final Screenshot Index

Captured from the running application (PyQt6 + AppShell, `enable_3d=False`).  
Output folder: `artifacts/final_screenshots/`  
Capture date: 2026-05-01  
Total files: 14 PNGs

---

## Complete Screenshot Table

| # | Filename | Size | Resolution | What it shows | Product-story step |
|---|----------|------|-----------|---------------|-------------------|
| 01 | `01_home_overview_empty.png` | 66 KB | 2560×1351 | Home/Overview page — sidebar nav, Import Run File / Open Replay / Run Compliance / Start Demo buttons, Recent Sessions list | **Landing screen** |
| 02 | `02_import_dialog_rigol_ds0.png` | 90 KB | 1125×960 | Import dialog with RigolDS0.csv loaded — File Metadata (1 M rows, 10 GHz, 0.100 s, 3 channels), channel mapping table **before** mapping (all `__unmapped__`), raw voltage range ±2.3 V (probe not yet scaled) | **Step 1 — Import** |
| 03 | `03_import_dialog_rigol_mapped.png` | 83 KB | 1125×960 | Same dialog **after** Apply Rigol 3-Phase Mapping — CH1(V)→v\_an, CH2(V)→v\_bn, CH3(V)→v\_cn; Import Preview shows `Derived computed channels: v_ab, v_bc, v_ca`; Import button ready | **Step 2 — Map channels** |
| 04 | `04_dataset_overview_rigol_ds0.png` | 81 KB | 2560×1351 | Overview page after import — "Rigol CSV · RigolDS0.csv", VSM/GFM analysis mode badge, "3 mapped / 1 unmapped" channel summary, missing channels: freq, i\_a, i\_b, i\_c, p\_mech; Open Analysis Workspace CTA | **Step 3 — Dataset overview** |
| 05 | `05_replay_phase_voltages.png` | 173 KB | 2560×1351 | Replay tab (all four stacked plots) — Phase-to-Neutral Voltages (v\_an/v\_bn/v\_cn ~120 V RMS after ×100 probe scale), Line-to-Line Voltages (v\_ab/v\_bc/v\_ca), Phase Currents (empty — not mapped), Frequency/Auxiliary (empty). Events panel: 0 events detected for this dataset | **Step 4 — Replay waveforms** |
| 06 | `06_replay_line_to_line.png` | 118 KB | 2560×1351 | Replay tab with Phase-to-Neutral and auxiliary plots hidden — Line-to-Line Voltages (v\_ab/v\_bc/v\_ca) fills the full window. Summary bar confirms "Derived: v\_ab, v\_bc, v\_ca" | **Step 3b — Derived channels** |
| 07 | `07_metrics_summary.png` | 147 KB | 2560×1351 | Metrics tab — rolling-RMS plot + table: Source file, Analysis mode (VSM/GFM), File type (rigol\_csv), Sample count (1 000 000), Sample rate (10 MHz), v\_an RMS (~120 V after ×100 probe scale), v\_an THD (vs IEEE 519 ref 5 %), v\_bn RMS, … | **Step 5 — Compute metrics** |
| 08 | `08_compliance_table.png` | 81 KB | 2560×1351 | Compliance page — "Applicable checks: 4/4 PASS · 4 N/A". Score cards: PASS Voltage regulation, N/A Ride-through (no sag event), PASS Frequency deviation, N/A Recovery (no sag event), PASS THD, PASS Phase Imbalance, N/A Overcurrent, N/A Fault ride-through | **Step 8 — Standards compliance** |
| 09 | `09_comparison_normal_vs_fault.png` | 173 KB | 2560×1351 | Compare tab — Baseline RigolDS0 vs Comparison/Fault RigolDS1. Overlay plot shows both datasets' 3-phase sinusoids (solid vs dashed). Delta plot shows v\_ab difference. Stats bar: ΔRMS, max\|Δ\|, correlation, Baseline/Comparison RMS, ΔTHD per channel | **Step 7 — Compare sessions** ⭐ BEST VISUAL |
| 10 | `10_export_complete.png` | 38 KB | 1200×725 | Evidence Package Exported widget — 7 artifacts written to `artifacts/evidence_exports/RigolDS0_*/`: HTML Report (~70 KB), Phase Voltage PNG (~50 KB), Line-to-Line Voltage PNG (~54 KB), Metrics JSON (~3 KB), Events JSON (<1 KB), Metadata JSON (~1 KB), Preview CSV (~485 KB). Total ~662 KB / 7 artifacts | **Step 9 — Export evidence package** |
| 11 | `11_simulation_import_power.png` | 70 KB | 1125×960 | Import dialog for InverterPower\_Simulation.xlsx — Source type: Simulation Excel, 16 703 rows, 20 kHz, 0.835 s, Pinv→p\_mech, range -0.001 → 458.5 | **Step 1b — Import simulation** |
| 12 | `12_simulation_analysis_power.png` | 149 KB | 2560×1351 | Replay tab for InverterPower\_Simulation — **5 events detected** (1 critical). Events: clipping × 2, flatline × 2, step\_change × 1 ("Abrupt step in p\_mech: 254.9, 55.6 % of signal range"). p\_mech step waveform visible in Auxiliary plot | **Step 6 — Event detection** ⭐ STRONG |
| 13 | `13_simulation_import_frequency.png` | 71 KB | 1125×960 | Import dialog for VSGFrequency\_Simulation.xlsx — Same Simulation Excel structure, Pinv→p\_mech. Demonstrates multi-format ingestion pipeline (second distinct file). Signal data is structurally identical to shot 11 (same Pinv column). | **Step 1c — Import frequency sim** |
| 14 | `14_simulation_analysis_frequency.png` | 150 KB | 2560×1351 | Replay tab for VSGFrequency\_Simulation — Same 5-event profile as shot 12 (same Pinv/p\_mech source data). Events panel prominent on right. Shows multi-file ingestion capability; does NOT show distinct frequency-domain data. | **Step 6b — Frequency simulation events** |

---

## Recommended Presentation Flow

9-slide narrative for a live demo or slide deck:

| Slide | File | Story beat |
|-------|------|-----------|
| 1 | `01_home_overview_empty.png` | Landing screen — introduce the tool |
| 2 | `03_import_dialog_rigol_mapped.png` | Channel-mapping intelligence (CH1→v\_an, derived v\_ab/v\_bc/v\_ca) |
| 3 | `04_dataset_overview_rigol_ds0.png` | Dataset overview — VSM/GFM mode badge, missing channels accurately reported |
| 4 | `05_replay_phase_voltages.png` | Waveform replay — 3-phase sinusoids, live scrubber |
| 5 | `07_metrics_summary.png` | Engineering metrics — RMS / THD per channel vs IEEE 519 |
| 6 | `09_comparison_normal_vs_fault.png` | Baseline vs fault overlay — most visually compelling slide ⭐ |
| 7 | `12_simulation_analysis_power.png` | Event detection — 5 events, 1 critical, jump-to-event |
| 8 | `08_compliance_table.png` | Standards compliance — 4/4 PASS, 4 N/A (correct for missing channels) |
| 9 | `10_export_complete.png` | Evidence package export — 7 artifacts, self-contained HTML report |

---

## Best 6 for Slideshow Core Deck

Ordered by visual impact and narrative clarity:

| Slide | File | Reason |
|-------|------|--------|
| 1 | `01_home_overview_empty.png` | Clean landing screen — sets product context |
| 2 | `03_import_dialog_rigol_mapped.png` | Shows channel-mapping intelligence (CH1→v\_an auto-suggest + derive v\_ab/v\_bc/v\_ca) |
| 3 | `09_comparison_normal_vs_fault.png` | Most visually striking — sinusoidal overlay + delta; tells the "compare sessions" story |
| 4 | `12_simulation_analysis_power.png` | Event detection prominent; "5 events detected" + step\_change at 55.6 % signal range |
| 5 | `08_compliance_table.png` | Standards compliance cards: "Applicable checks: 4/4 PASS · 4 N/A" — shows correct N/A for missing fault/current data |
| 6 | `07_metrics_summary.png` | Engineering metrics table with real RMS / THD values |

---

## Best 10 for Full Appendix / Backup Slides

All 6 above plus:

| File | Adds |
|------|------|
| `04_dataset_overview_rigol_ds0.png` | Dataset overview with VSM/GFM mode badge |
| `05_replay_phase_voltages.png` | All four replay plots, scaled waveforms, events panel |
| `06_replay_line_to_line.png` | Derived line-to-line channels focus view |
| `10_export_complete.png` | Evidence package export — 7 artifacts, ~662 KB total |

---

## Notes & Caveats

- **Shots 13–14** share the same signal data as shots 11–12 (both Excel files contain the same `Pinv` column mapping to `p_mech`). `VSGFrequency_Simulation.xlsx` does NOT contain distinct frequency channel data — it has the same Pinv column as `InverterPower_Simulation.xlsx`. Screenshots 13–14 demonstrate multi-format ingestion of a second distinct file, but the signal content is identical to 11–12. Do not claim shots 13–14 show frequency-domain analysis.
- **Shot 10** was captured immediately after `quick_export()` fired from the capture script. The widget shown is a standalone `QWidget` (not a Replay tab), displaying the 7 exported artifact paths and sizes. The export folder is `artifacts/evidence_exports/RigolDS0_<timestamp>/`.
- **Shot 06** hides the three surrounding plots so that Line-to-Line Voltages fills the full window — a deliberate temporary hide/restore during capture.
- **Probe scaling**: RigolDS0.csv / RigolDS1.csv were captured via a ×100 oscilloscope probe. Raw column values are ~±2.3 V. `ImportDialog` auto-detects raw RMS < 5 V and applies `scale_factors = {v_an: 100, v_bn: 100, v_cn: 100}` at import time. All waveforms in shots 05–09 show physically correct ~120 V (phase-to-neutral) and ~208 V (line-to-line) amplitudes.
- **Waveform fidelity**: Sinusoidal shape in shots 05/06/09 is preserved because `dataset_converter` uses min/max envelope decimation (selecting both the min and max sample within each bucket), which preserves AC peaks and troughs when downsampling 1 M rows → 20 K frames.
- **Events (shots 05, 06)**: RigolDS0 produces 0 events detected — the waveform is clean 3-phase AC with no sag, step change, or anomaly. The step\_change event visible in shots 12/14 comes from the simulation data only.
