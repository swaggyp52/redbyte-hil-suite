# Project Overview — VSM Evidence Workbench

**Senior Design Capstone Project**
**Academic Year:** 2025-2026
**Team:** Cyber Engineering + Electrical Engineering collaboration
**Software Deliverable:** `redbyte-hil-suite/` — the **VSM Evidence Workbench**

---

## What this software is

A **local desktop engineering analysis tool** for Virtual Synchronous Machine
(VSM) / Grid-Forming (GFM) inverter test data. It takes exported datasets
from lab benches, simulation tools, or HIL rigs and lets an engineer:

1. **Import** CSV, Excel, or JSON exports.
2. **Normalize** them into a consistent *Data Capsule* format.
3. **Replay** runs with waveforms, derived metrics (RMS / THD / frequency),
   and auto-detected disturbance markers.
4. **Compare** a run against a baseline on a time-aligned grid.
5. **Evaluate** the run against a labeled standards-inspired profile
   (Project Demo thresholds, IEEE 2800-inspired subset, IEEE 519 THD reference).
6. **Export** a polished evidence package: HTML + PNG + CSV + JSON artifacts.

## What this software is **not**

- **Not** a certified standards-compliance test suite. Every rule is clearly
  labeled as an *inspired subset* with a source tag on each check; the
  evidence output carries the same honesty framing.
- **Not** a completed live-hardware telemetry / cloud-monitoring platform.
  A demo adapter and an optional input-adapter interface exist as a
  walk-through path and a future integration hook; the production workflow
  is import-based.

## The engineering problem

Grid-forming inverters must ride through extreme fault events — voltage sags,
frequency excursions, phase imbalance, harmonic distortion — while staying
stable. Characterizing this behavior from raw scope/CSV captures is manual,
error-prone, and hard to make reproducible. Most exported data is
heterogeneous (different column names, time units, sample rates). Evidence
for a design review needs to be consistent, traceable, and reviewable.

## The software contribution

The Workbench is the **Cyber Engineering contribution** to the capstone. It
closes the gap between a raw lab export and a reviewable engineering
artifact, giving the team a repeatable pipeline:

```
lab/sim CSV -- Import Wizard -- Data Capsule -- Replay Studio -- Evidence Package
                                     |              |
                                Event Detector  Comparison Engine
                                     |              |
                                Run Summary    Standards Profiles
                                     |
                                 HTML + CSV + JSON report
```

Every output number in the report has a measured value, a threshold, a rule
text, and a source tag. Nothing in the evidence package is opaque.

## Team structure

- **Cyber Engineering:** software design, DSP, standards-inspired evaluation
  engine, UI, evidence export, test suite.
- **Electrical Engineering:** inverter hardware, VSM control, HIL model,
  dataset generation.

## Where to go next

| Goal | Read |
|------|------|
| Run the app in under a minute | [`QUICK_START_GUIDE.md`](QUICK_START_GUIDE.md) |
| Understand the module layout | [`architecture.md`](architecture.md) |
| Follow the demo | [`demo_script.md`](demo_script.md) · [`presentation_walkthrough.md`](presentation_walkthrough.md) |
| Review the final-paper outline | [`final_report_outline.md`](final_report_outline.md) |
| Understand the honesty framing | Root [`README.md`](../README.md) — "What this project is **not**" |
