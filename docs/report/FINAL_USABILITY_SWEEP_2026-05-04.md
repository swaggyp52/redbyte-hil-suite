# Final Usability Sweep Report

Date: 2026-05-04

## Scope

This sweep focused on final presentation readiness for the offline analysis workflow in `gfm_hil_suite`.

Constraints followed:

- No architectural rewrite.
- No new experimental product features.
- Any visible feature in the demo path either works clearly or is hidden.

## What Changed

### Launch and bootstrap

- Fixed `scripts/bootstrap.cmd` so a fresh checkout can create `.venv` correctly when launched through `run.bat`.
- Revalidated startup through `run.bat` on the project-local Python 3.12 environment.

### Demo navigation and session reset

- Import now lands directly in Replay instead of leaving the user on Overview.
- Overview is hidden while a dataset is active and restored on reset.
- Reset now clears both Replay and Compliance state instead of leaving stale session UI behind.
- Tools was reduced to reliable final-demo actions only.

### Replay clarity

- Limited the visible Replay tabs to `Replay`, `Metrics`, and `Compare`.
- Added `Link Axes` so the operator can keep synchronized zoom or inspect traces independently.
- Improved metrics cards and summary text so RMS, THD, frequency, window size, and derived channels read cleanly during a live walkthrough.
- Reworded empty-state plot messages so missing current/frequency data is explicit instead of implying a broken graph.
- Fixed empty-state annotation placement for short sessions like `RigolDS0.csv`, so the missing-data note stays visible inside the active time range.

### Compliance honesty

- Compliance now resets truthfully with the rest of the app.
- Fixed imported-session frame count display so real sessions no longer show `(0 frames)` in the top bar.

### Compare simplification

- Compare auto-renders when both sessions are loaded.
- Default detail view now selects a single overlapping channel instead of `All matched channels`, making the first screen legible enough for a demo.
- Compare controls were renamed to match their real behavior: `Re-align` and `Refresh Compare`.

### Validation coverage

- Expanded replay/import tests for demo-tab visibility, axis-link behavior, compare population, and locked navigation.
- Expanded the GUI-state smoke test to verify the reduced tab surface and linked-axis default.
- Refreshed tracked final screenshots to match the current shipped UI.

## Validated Results

The following checks passed on the project-local `.venv`:

- `python -m pytest tests/test_replay_display_state.py tests/test_bootability_import_ux.py -q`
- `python scripts/final_gui_state_smoke.py`
- `python scripts/final_demo_smoke.py`
- `python scripts/capture_screenshots.py`
- `run.bat` startup validation

Observed outcomes:

- `RigolDS0.csv` imports cleanly, opens Replay immediately, and shows honest current/frequency N/A messaging.
- `RigolDS1.csv` overlays successfully and preserves conservative CH4 unmapped handling.
- `InverterPower_Simulation.xlsx` and `VSGFrequency_Simulation.xlsx` both stay in honest generic `p_mech` analysis mode without fabricated frequency channels.
- Compliance renders a readable PASS/N/A result surface with the correct imported frame count.
- Compare opens on a readable single-channel overlay instead of an all-channel wall of traces.

## Remaining Limitations

- The right-side event/analysis panel remains visible in Replay because it is functional and informative, but it is still extra surface area beyond the strict left-nav demo sequence.
- The compliance cards are accurate, but their dense copy is still optimized for engineering truth more than presentation polish.
- The simulation Excel examples currently produce the same generic `p_mech` path because both source files resolve to `Pinv`; this is honest behavior, not a UI defect.
- The screenshot automation still captures an internal dataset-overview shot even though the polished demo flow should stay on Replay after import.

## Recommended Demo Path

1. Launch with `run.bat`.
2. Import `RigolDS0.csv`.
3. Show Replay first: phase voltages, line-to-line voltages, visible current/frequency N/A notes.
4. Switch to Metrics for RMS, THD, derived channels, and summary status lines.
5. Switch to Compliance and run checks.
6. Return to Replay and add `RigolDS1.csv` as overlay.
7. Open Compare and discuss the default `v_ab` overlay and delta.
8. Use Quick Export if evidence output needs to be shown.
9. Import `InverterPower_Simulation.xlsx` and show honest generic-mode analysis.
10. Import `VSGFrequency_Simulation.xlsx` and note that no false frequency channel is created.

## Screenshot Recommendations

Use these tracked images for the final deck or handoff:

- `artifacts/final_screenshots/05_replay_phase_voltages.png`
  - Best replay proof: polished voltage plots plus explicit current/frequency N/A messaging.
- `artifacts/final_screenshots/07_metrics_summary.png`
  - Best metrics slide: readable RMS, THD, frequency, and session-window summary.
- `artifacts/final_screenshots/08_compliance_table.png`
  - Best validation slide: PASS/N/A cards plus correct session frame count.
- `artifacts/final_screenshots/09_comparison_normal_vs_fault.png`
  - Best compare slide: single-channel overlay/delta view is now presentation-readable.
- `artifacts/final_screenshots/12_simulation_analysis_power.png`
  - Best proof of honest generic analysis for Excel inputs.
- `artifacts/final_screenshots/14_simulation_analysis_frequency.png`
  - Best proof that missing frequency is handled truthfully rather than fabricated.

## Final Assessment

The app now reads as a coherent offline engineering analysis tool rather than a partially exposed internal demo surface. The remaining rough edges are presentational, not correctness blockers, and the requested demo path is executable end to end on the validated local environment.