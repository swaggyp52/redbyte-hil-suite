# Presentation Walkthrough Script

**Goal**: Demonstrate the current RedByte 5-app workflow without relying on the legacy monolithic demo path.

## Scene 1: Launch the Suite

1. Launch `bin\launch_redbyte.bat`.
2. Explain: "The launcher presents five focused tools for different parts of the verification workflow."
3. Point out **Diagnostics**, **Replay Studio**, **Compliance Lab**, **Insight Studio**, and **Signal Sculptor**.

## Scene 2: Show Live Monitoring

1. Open **Diagnostics** in mock mode or with live hardware attached.
2. Show **Inverter Scope**, **PhasorView**, **Fault Injector**, and the live insight stream.
3. Explain: "This is the operator view for live capture, fault injection, and immediate anomaly detection."

## Scene 3: Show Post-Event Analysis

1. Open **Replay Studio**.
2. Load `data\demo_sessions\demo_session_baseline.json`.
3. Scrub to the sag and drift regions.
4. Explain: "Replay lets us inspect the exact event sequence after a fault instead of trying to interpret everything live."

## Scene 4: Show Validation Output

1. Open **Compliance Lab** with the same session file.
2. Run the checks or open the exported HTML report.
3. Explain: "This converts a captured session into a pass/fail summary and a portable report that can be reviewed outside the app."

## Scene 5: Close With System Value

1. Summarize: "The software contributes the monitoring, handoff, and validation layer around the HIL plant."
2. State clearly: "Mock mode makes the workflow safe and repeatable for demos, and the same workflow can run against real telemetry when the inverter hardware is connected."
