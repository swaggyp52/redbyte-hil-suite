# Demo Release Notes (2026-04-08)

## Baseline
- Commit: `ed08ec9`
- Message: `style(app): final visual polish and professional finish for analysis workflow`
- Status: frozen demo baseline

## What this baseline demonstrates
- Imports real telemetry/session data and normalizes to a unified session model.
- Visualizes waveform and metrics timelines for engineering review.
- Detects and summarizes anomalous events with severity + filters.
- Compares two runs with alignment, overlay, delta, and metric chips.
- Runs IEEE 2800-style compliance checks and exports reports.

## Recommended demo file order
1. `RigolDS0.csv` (cleaner baseline run)
2. `RigolDS1.csv` (contrast run for compare workflow)
3. `InverterPower_Simulation.xlsx` (simulation import and replay)
4. `VSGFrequency_Simulation.xlsx` (frequency-focused validation)

## Suggested 2-3 minute story
1. Import a real file and show quick session context.
2. Open replay: scrub waveform, toggle channels, show crosshair readout.
3. Show Events + Insights side rail (summary + cluster clarity).
4. Add overlay and run Compare (alignment + delta + metrics).
5. Open Compliance and run checks.
6. Export report and show deliverable readiness.

## Validation snapshot
- Automated tests: `418 passed` (excluding UI integration test file as configured)
- Working tree: clean at freeze point

## Freeze policy
- No broad redesign prompts after this point.
- Only micro-fixes allowed:
  - one awkward spacing issue
  - one confusing label
  - one broken control state
  - one report/export defect

## Micro-pass prompt (if needed)
Use this exact prompt for any final touch-ups:

```text
Continue from current repo state. This is a micro-pass only.
Do not redesign architecture or add new features.
Only fix concrete issues I personally observed while clicking through demo flows.

Allowed scope:
- tiny spacing/alignment cleanup
- one wording/label clarification
- one empty-state copy fix
- one control-state bug
- one graph readability tweak
- one export/report polish fix

Rules:
- minimum diff only
- preserve truthful analysis behavior
- no new panels or workflows
- run relevant tests after edits
- commit with a narrow message describing the specific micro-fix
```
