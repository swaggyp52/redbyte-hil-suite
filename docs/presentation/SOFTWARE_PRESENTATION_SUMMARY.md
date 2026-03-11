# Software Presentation Summary

## Software Maturity Summary

- The software is structured as five focused desktop apps instead of one crowded interface, which makes each workflow easier to demonstrate, maintain, and extend.
- The demo path is reproducible: Python 3.12 is the single supported runtime, setup is documented for clean machines, and `scripts\preflight_check.py` fails fast when the environment is wrong.
- Validation is automated, not anecdotal: the canonical Python 3.12 environment passes 123 tests including workflow, serialization, launcher smoke, and browser-level report rendering.
- The suite supports both mock mode and hardware-attached mode, so the team can demonstrate safely without energizing hardware while keeping the same operator workflow.
- Diagnostics, Replay, Compliance, and Insights share portable session context, which gives the project a clear end-to-end story instead of isolated screenshots.
- HTML report export and browser validation provide visible evidence that results can be reviewed outside the app, not just observed live during the demo.
- Compliance logic is suitable for prototype validation and demonstration, but it is not being presented as final certification-grade IEEE implementation.

## Software Contribution Summary

This platform provides the software layer that makes the HIL project usable and explainable. It turns raw inverter telemetry into operator-facing monitoring, event capture, replay, automated rule checking, and presentation-ready reporting. In practical terms, the software is what lets the team demonstrate system behavior safely, review faults after the fact, and communicate results to judges, teammates, and lab staff.

## Demo Script Notes

1. Start with the RedByte launcher and explain that the suite is split into specialized tools instead of one overloaded window.
2. Open Diagnostics and point out live waveforms, phasors, fault injection, and insight detection as the real-time operator view.
3. Open Replay Studio with the baseline demo session and scrub to the sag and drift regions to show post-event analysis.
4. Open Compliance Lab with the same session and show that the same data becomes a pass/fail summary and exportable HTML report.
5. Close by saying the software contribution is the workflow around the HIL plant: observe, capture, replay, validate, and present.

## Judge Question Prep

**How did you test this?**  
We used automated tests at multiple levels: unit tests for signal and insight handling, workflow tests across Diagnostics to Replay to Compliance, launcher smoke tests, and a Playwright browser test that opens the exported HTML report.

**What makes this reliable?**  
We narrowed the repo to one supported runtime, added fail-fast environment checks, validated the launcher paths, and kept the core demo workflow covered by automated tests instead of relying only on manual runs.

**What is simulated vs real?**  
Mock mode simulates telemetry so we can demonstrate the workflow safely and repeatably. The same software path can also ingest real telemetry from the hardware side when the inverter and UART bridge are connected.

**Why only Python 3.12?**  
Because release credibility matters more than broad but ambiguous compatibility. Python 3.12 is the environment we validated end to end, including dependencies and browser-based report checks.

**What remains for future work?**  
The main next step is deeper standards-grade compliance logic with formal oracle datasets. Beyond that, richer GUI interaction regression coverage and more advanced report storytelling would further harden the platform.