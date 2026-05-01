# VSM Evidence Workbench — Final Screenshot Index

Captured from the running application (PyQt6 + AppShell, `enable_3d=False`).  
Output folder: `artifacts/final_screenshots/`  
Capture date: 2026-04  
Total files: 14 PNGs

---

## Complete Screenshot Table

| # | Filename | Size | Resolution | What it shows | Product-story step |
|---|----------|------|-----------|---------------|-------------------|
| 01 | `01_home_overview_empty.png` | 66 KB | 2560×1351 | Home/Overview page — sidebar nav, Import Run File / Open Replay / Run Compliance / Start Demo buttons, Recent Sessions list | **Landing screen** |
| 02 | `02_import_dialog_rigol_ds0.png` | 90 KB | 1125×960 | Import dialog with RigolDS0.csv loaded — File Metadata (1 M rows, 10 GHz, 0.100 s, 3 channels), channel mapping table **before** mapping (all `__unmapped__`) | **Step 1 — Import** |
| 03 | `03_import_dialog_rigol_mapped.png` | 83 KB | 1125×960 | Same dialog **after** Apply Rigol 3-Phase Mapping — CH1(V)→v\_an, CH2(V)→v\_bn, CH3(V)→v\_cn; Import Preview shows `Derived computed channels: v_ab, v_bc, v_ca`; Import button ready | **Step 2 — Map channels** |
| 04 | `04_dataset_overview_rigol_ds0.png` | 81 KB | 2560×1351 | Overview page after import — "Rigol CSV · RigolDS0.csv", VSM/GFM analysis mode badge, canonical/derived/missing channel summary, Open Analysis Workspace CTA, Recent Sessions list | **Step 3 — Dataset overview** |
| 05 | `05_replay_phase_voltages.png` | 129 KB | 2560×1351 | Replay tab (all four stacked plots) — Phase-to-Neutral Voltages (v\_an/v\_bn/v\_cn), Line-to-Line Voltages (v\_ab/v\_bc/v\_ca), Phase Currents (empty — not mapped), Frequency/Auxiliary. Events panel: "step\_change Events (1) — t=0.05s" | **Step 4 — Replay waveforms** |
| 06 | `06_replay_line_to_line.png` | 88 KB | 2560×1351 | Replay tab with Phase-to-Neutral and auxiliary plots hidden — Line-to-Line Voltages (v\_ab/v\_bc/v\_ca) fills the full window. Summary bar confirms "Derived: v\_ab, v\_bc, v\_ca" | **Step 3b — Derived channels** |
| 07 | `07_metrics_summary.png` | 122 KB | 2560×1351 | Metrics tab — rolling-RMS plot + table: Source file, Analysis mode (VSM/GFM), File type (rigol\_csv), Sample count (1 000 000), Sample rate (10 MHz), v\_an RMS (1.2025 V), v\_an THD (1.003 % vs IEEE 519 ref 5 %), v\_bn RMS (1.2173 V) … | **Step 5 — Compute metrics** |
| 08 | `08_compliance_table.png` | 80 KB | 2560×1351 | Compliance page — "Applicable checks: 4/4 PASS · 4 N/A". Score cards: PASS Voltage regulation, N/A Ride-through (no sag event), PASS Frequency deviation, N/A Recovery (no sag event), PASS THD, PASS Phase Imbalance, N/A Overcurrent, N/A Fault ride-through | **Step 8 — Standards compliance** |
| 09 | `09_comparison_normal_vs_fault.png` | 180 KB | 2560×1351 | Compare tab — Baseline RigolDS0 vs Comparison/Fault RigolDS1. Overlay plot shows both datasets' 3-phase sinusoids (solid vs dashed). Delta plot shows v\_ab difference. Stats bar: ΔRMS, max\|Δ\|, correlation, Baseline/Comparison RMS, ΔTHD per channel | **Step 7 — Compare sessions** ⭐ BEST VISUAL |
| 10 | `10_export_complete.png` | 145 KB | 2560×1351 | Replay tab with both RigolDS0 and RigolDS1 loaded as overlay — legend shows 6 channels (v\_an/v\_bn/v\_cn for each). Top bar: "t = 0.4184s  y = -8.072". All four stacked plots visible with dual-session legends | **Step 7b — Multi-session overlay** |
| 11 | `11_simulation_import_power.png` | 70 KB | 1125×960 | Import dialog for InverterPower\_Simulation.xlsx — Source type: Simulation Excel, 16 703 rows, 20 kHz, 0.835 s, Pinv→p\_mech, range -0.001 → 458.5 | **Step 1b — Import simulation** |
| 12 | `12_simulation_analysis_power.png` | 159 KB | 2560×1351 | Replay tab for InverterPower\_Simulation — **5 events detected** (1 critical). Events: clipping × 2, flatline × 2, step\_change × 1 ("Abrupt step in p\_mech: 254.9, 55.6 % of signal range"). p\_mech step waveform visible in Auxiliary plot | **Step 6 — Event detection** ⭐ STRONG |
| 13 | `13_simulation_import_frequency.png` | 71 KB | 1125×960 | Import dialog for VSGFrequency\_Simulation.xlsx — Same Simulation Excel structure, Pinv→p\_mech. Demonstrates multi-format ingestion pipeline (second distinct file) | **Step 1c — Import frequency sim** |
| 14 | `14_simulation_analysis_frequency.png` | 163 KB | 2560×1351 | Replay tab for VSGFrequency\_Simulation — Same 5-event profile (VSGFrequency data shares structure with InverterPower). Events panel prominent on right | **Step 6b — Frequency simulation events** |

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
| `05_replay_phase_voltages.png` | All four replay plots + event panel populated |
| `06_replay_line_to_line.png` | Derived line-to-line channels focus view |
| `11_simulation_import_power.png` | Shows Simulation Excel format ingestion |

---

## Notes & Caveats

- **Shots 13–14** share the same signal data as shots 11–12 (both Excel files contain the same `Pinv` column mapping to `p_mech`). This is by design — the VSGFrequency_Simulation.xlsx file does NOT contain distinct frequency channel data; it has the same Pinv column as InverterPower_Simulation.xlsx. Screenshots 13–14 demonstrate multi-format ingestion of a second distinct file, but users should note the signal content is identical to 11–12.
- **Shot 10** was originally intended as an "export complete" shot. The Export PNG button triggered a `QFileDialog` that was auto-dismissed; the resulting screenshot shows the dual-session Replay view which is useful for demonstrating the overlay loading feature.
- **Shot 06** hides the three surrounding plots so that Line-to-Line Voltages fills the full window — a deliberate temporary hide/restore during capture.
- Waveform lines in shots 05/06 display sinusoidal shape because the dataset_converter uses min/max envelope decimation (preserving peaks and troughs) for AC voltage channels. The comparison view (shot 09) uses full-resolution arrays which also shows the sinusoidal shape clearly.
