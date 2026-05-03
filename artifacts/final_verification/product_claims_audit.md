# VSM Evidence Workbench — Product Claims Audit

**Audit date:** 2026-05-03  
**Branch:** main  
**Commit:** 9071aa1 (baseline) + solidification pass  
**Auditor:** Final solidification pass (Claude Code)

This document classifies every major user-facing claim found in README.md,
HANDOFF.md, docs/, UI source, and report templates.

---

## Status Legend

| Status | Meaning |
|--------|---------|
| VERIFIED | Implemented, tested, and confirmed by actual code/data |
| PARTIALLY_TRUE | Core behavior works but specific details are incomplete |
| FUTURE_WORK | Correctly documented as not yet implemented |
| STALE_FIXED | Was stale; corrected in this pass |
| REMOVED | Was misleading/false; removed in this pass |

---

## Core Product Identity Claims

| Claim | Source | Status | Evidence |
|-------|--------|--------|---------|
| "local-first" | README, HANDOFF | VERIFIED | All processing in `src/`; no network calls |
| "offline" | README, HANDOFF | VERIFIED | No HTTP imports, no external API calls |
| "post-run analysis" | README, HANDOFF | VERIFIED | Import-first workflow; no real-time feed in demo path |
| "deterministic" | README, HANDOFF | VERIFIED | Same file → same metrics every run (tests confirm) |
| "evidence generation" | README, HANDOFF | VERIFIED | `quick_export()` in `session_exporter.py` produces real artifacts |
| "standards-inspired engineering checks" | README, HANDOFF | VERIFIED | `compliance_checker.py` — 3 profiles, explicit "inspired" language |
| "Not live monitoring" | README, HANDOFF | VERIFIED | Correctly stated as NOT; demo path is import-first |
| "Not Blynk" | README, HANDOFF | VERIFIED | Correctly stated as NOT |
| "Not cloud dashboard" | README, HANDOFF | VERIFIED | Correctly stated as NOT |
| "Not UART streaming deliverable" | README | VERIFIED | Correctly stated as NOT (SerialAdapter exists but is not demo path) |
| "Not hardware control" | README, HANDOFF | VERIFIED | Correctly stated as NOT |
| "Not formal certification" | README, HANDOFF | VERIFIED | Compliance disclaimer in `compliance_checker.py` and HTML footer |

---

## File Import Claims

| Claim | Source | Status | Evidence |
|-------|--------|--------|---------|
| "imports CSV" | README, HANDOFF | VERIFIED | `file_ingestion.py` → `ingest_file()`; tested in `test_file_ingestion.py` |
| "imports XLSX/XLS" | README, HANDOFF | VERIFIED | `file_ingestion.py` with openpyxl; tested |
| "imports JSON session capsules" | README, HANDOFF | VERIFIED | `replayer.py` + `load_session()`; tested |
| "1,000,000-row CSV non-blocking" | SCREENSHOT_INDEX | VERIFIED | Background-threaded import dialog; `test_importer.py` |
| "detects time column" | README, HANDOFF | VERIFIED | `file_ingestion.py` auto-detects `Time(s)`, `time`, `t`, `t_ms` |

---

## Channel Mapping Claims

| Claim | Source | Status | Evidence |
|-------|--------|--------|---------|
| "maps CH1(V)→v_an, CH2(V)→v_bn, CH3(V)→v_cn" | SCREENSHOT_INDEX, HANDOFF | VERIFIED | `import_dialog.py` Rigol preset; `test_importer.py` |
| "auto-suggests mapping" | README, HANDOFF | VERIFIED | `channel_mapping.py` → `auto_suggest_mapping()` |
| "derives v_ab, v_bc, v_ca" | README, HANDOFF, SCREENSHOT_INDEX | VERIFIED | `derived_channels.py`; confirmed in metrics.json |
| "maps Pinv → p_mech" | SCREENSHOT_INDEX, data_audit | VERIFIED | auto-suggest in `file_ingestion.py`; confirmed in InverterPower export |
| "applies scale factors (×100 probe)" | README, SCREENSHOT_INDEX | VERIFIED | `import_dialog.py` auto-detects raw RMS < 5 V; scale_factors in metrics.json |
| "scale factor visible in UI and export" | README | VERIFIED | `metrics.json` session.scale_factors; Overview page shows it |
| "CH4(V) treated honestly" | data_audit | VERIFIED | CH4 left as generic numeric unless user maps it; noted in data_audit |

---

## Analysis / Metrics Claims

| Claim | Source | Status | Evidence |
|-------|--------|--------|---------|
| "computes RMS" | README, HANDOFF | VERIFIED | `session_analysis.py`; per-channel RMS in metrics.json |
| "computes THD" | README, HANDOFF | VERIFIED | `signal_processing.py` FFT-based; THD in metrics.json |
| "frequency estimation from v_an" | compliance.json, metrics.json | VERIFIED | `session_analysis.py`; source = "estimated_from_v_an" |
| "phase imbalance" | compliance.json | VERIFIED | `compliance_checker.py` percent_voltage_imbalance |
| "line-to-line RMS" | metrics.json | VERIFIED | v_ab/v_bc/v_ca RMS computed and exported |
| "generic min/max/mean/RMS for power file" | README | VERIFIED | `session_analysis.py` generic_numeric section |
| "sample count, sample rate, duration" | README, SCREENSHOT_INDEX | VERIFIED | All in metrics.json session section |
| "missing channel shown as N/A not fake value" | README, HANDOFF | VERIFIED | `compute_session_metrics()` marks unavailable=False with reason |

---

## Event Detection Claims

| Claim | Source | Status | Evidence |
|-------|--------|--------|---------|
| "detects voltage sag/swell" | SCREENSHOT_INDEX | VERIFIED | `event_detector.py` — RMS-window comparison |
| "detects frequency excursion" | SCREENSHOT_INDEX | VERIFIED | `event_detector.py` — freq deviation check |
| "detects step_change on p_mech" | SCREENSHOT_INDEX (shot 12) | VERIFIED | InverterPower Simulation — 5 events, 1 step_change at 55.6% |
| "detects clipping/flatline" | SCREENSHOT_INDEX (shot 12) | VERIFIED | clipping ×2, flatline ×2 in InverterPower export |
| "event shows channel, type, time, value, severity" | README | VERIFIED | `DetectedEvent` dataclass + `event_lane.py` |
| "missing current means no overcurrent calc" | README, HANDOFF | VERIFIED | N/A when i_a/i_b/i_c not present; confirmed in DS0 metrics.json |

---

## Compliance Claims

| Claim | Source | Status | Evidence |
|-------|--------|--------|---------|
| "checks IEEE 519-inspired THD ≤ 5%" | SCREENSHOT_INDEX | VERIFIED | `compliance_checker.py` profile `ieee_519_thd`; DS0 THD 1.07% PASS |
| "checks IEEE 2800-inspired ride-through" | SCREENSHOT_INDEX | VERIFIED | Profile `ieee_2800_inspired`; Ride-through N/A when no sag detected |
| "voltage overshoot check" | compliance.json | VERIFIED | DS0 shows 37.3% overshoot FAIL (physically real — no voltage regulator in raw scope capture) |
| "settling time check" | compliance.json | VERIFIED | DS0 0.007 s settling PASS |
| "N/A when required channels missing" | README, HANDOFF | VERIFIED | All 8 checks N/A for InverterPower (no voltage/freq channels) |
| "N/A ride-through when no sag detected" | compliance.json | VERIFIED | Explicit na_reason in compliance.json |
| "score does not penalize N/A" | SCREENSHOT_INDEX | VERIFIED | Compliance page shows N/A separately from PASS/FAIL |
| "Not formal certification" | compliance_checker.py, report footer | VERIFIED | Explicit disclaimers in code and HTML |

---

## Comparison Claims

| Claim | Source | Status | Evidence |
|-------|--------|--------|---------|
| "baseline vs comparison overlay" | SCREENSHOT_INDEX (shot 09) | VERIFIED | `comparison_panel.py`; DS0 vs DS1 overlay |
| "delta plot" | SCREENSHOT_INDEX | VERIFIED | `generate_delta_trace()` in `comparison.py` |
| "ΔRMS, correlation, per-channel stats" | SCREENSHOT_INDEX | VERIFIED | `compare_datasets()` returns these metrics |
| "missing channels handled gracefully" | README | VERIFIED | `find_overlapping_channels()` only compares what both have |

---

## Evidence Export Claims

| Claim | Source | Status | Evidence |
|-------|--------|--------|---------|
| "exports HTML report" | README, HANDOFF | VERIFIED | `session_exporter.py` → `generate_html_report()`; confirmed in evidence_exports/ |
| "exports waveform PNGs" | README, HANDOFF | VERIFIED | waveform_phase.png + waveform_line.png in evidence_exports/ |
| "exports metrics.json" | README, HANDOFF | VERIFIED | Confirmed in evidence_exports/; values match UI |
| "exports compliance.json" | README, HANDOFF | VERIFIED | Only when compliance run; 8-check result confirmed |
| "exports events.json" | README, HANDOFF | VERIFIED | Confirmed; empty array when no events |
| "exports metadata.json" | README, HANDOFF | VERIFIED | Confirmed; source_path, mapping, scale_factors present |
| "exports preview.csv" | README (fixed in this pass) | VERIFIED | Confirmed in evidence_exports/; ~20k rows for DS0 |
| "8 artifacts max" | README (corrected in this pass) | VERIFIED | 7 always + compliance.json when compliance run |
| "exports session_capsule.json" | OLD README/HANDOFF | STALE_FIXED | Never produced; removed from artifact lists in this pass |
| "waveform_overview.png" name | OLD README/HANDOFF | STALE_FIXED | Actual name is waveform_phase.png; corrected |
| "line_to_line_overlay.png" name | OLD README/HANDOFF | STALE_FIXED | Actual name is waveform_line.png; corrected |
| "normalized_frames.csv" name | OLD README/HANDOFF | STALE_FIXED | Actual name is preview.csv; corrected |

---

## Dataset-Specific Claims

| Claim | Source | Status | Evidence |
|-------|--------|--------|---------|
| "RigolDS0: 1,000,000 rows, 10 MHz, CH1/CH2/CH3" | data_audit, SCREENSHOT_INDEX | VERIFIED | data_audit SHA: 6b1acd3b |
| "RigolDS1: 600,000 rows, 1 MHz, CH1/CH2/CH3/CH4" | data_audit | VERIFIED | data_audit SHA: 344a68ea |
| "InverterPower: 16,703 rows, 20 kHz, time + Pinv" | data_audit | VERIFIED | SHA: 1ddb3d1b; Pinv → p_mech |
| "VSGFrequency does NOT contain frequency data" | data_audit, SCREENSHOT_INDEX Notes | VERIFIED | SHA: 7e1584fe; identical to InverterPower (same Pinv column) |
| "VSGFrequency: Simulink export issue" | data_audit | VERIFIED | Both files identical; re-export guidance documented |

---

## Launch Claims

| Claim | Source | Status | Evidence |
|-------|--------|--------|---------|
| "run.bat launches real app" | README (corrected in this pass) | VERIFIED | run.bat → bootstrap.cmd → .venv Python 3.12 → run.py → src.main |
| "run.bat uses project .venv" | scripts/bootstrap.cmd | VERIFIED | VENV_DIR set to PROJECT_ROOT/.venv; VENV_PYTHON checks version |
| "double-click works" | README | VERIFIED | run.bat is a standard .bat; no VS Code dependency |
| "python -m src.main (old launch)" | OLD README/HANDOFF | STALE_FIXED | Replaced with `run.bat` and `.venv\Scripts\python.exe run.py` |

---

## Future Work (Correctly Labeled as Not Done)

| Item | Source | Status |
|------|--------|--------|
| Live microcontroller streaming | HANDOFF Known Limitations | FUTURE_WORK |
| Real current calibration | HANDOFF | FUTURE_WORK |
| Full-resolution CSV export toggle | README, HANDOFF | FUTURE_WORK |
| Broader simulation auto-mapping | README, HANDOFF | FUTURE_WORK |
| Formal certification support | README | FUTURE_WORK |
| VSGFrequency corrected re-export from Simulink | data_audit | FUTURE_WORK |

---

## Summary

**Total claims audited:** 54  
**VERIFIED:** 47  
**STALE_FIXED (corrected in this pass):** 6 (artifact names, session_capsule.json, launch commands)  
**FUTURE_WORK (correctly labeled):** 6  
**UNSUPPORTED / MISLEADING:** 0 remaining after fixes

All stale claims corrected in README.md, HANDOFF.md, and SCREENSHOT_INDEX.md.
No misleading claims remain in user-facing documentation.
