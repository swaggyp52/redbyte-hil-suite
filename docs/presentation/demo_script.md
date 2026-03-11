# Live Demo Script

## Setup

1. Launch `bin\launch_redbyte.bat`.
2. Keep `data\demo_sessions\demo_session_baseline.json` ready for Replay and Compliance.
3. Use mock mode if live hardware is unavailable.

## Step 1: Suite Overview

- *Action*: Show the launcher with the five RedByte app cards.
- *Talk*: "We split the software into focused tools for diagnostics, replay, compliance, insights, and signal shaping instead of one overloaded UI."

## Step 2: Live Diagnostics

- *Action*: Open **Diagnostics** from the launcher, or run `bin\diagnostics.bat --mock`.
- *Action*: Point out the live scope, phasor view, fault injector, and insights panel.
- *Talk*: "Diagnostics is the operator view. It ingests telemetry, shows the electrical state in real time, and flags anomalies as they appear."

## Step 3: Post-Event Review

- *Action*: Open **Replay Studio** and load `data\demo_sessions\demo_session_baseline.json`.
- *Action*: Scrub to the sag, drift, and recovery regions.
- *Talk*: "Replay lets us inspect the exact sequence of events after a disturbance instead of relying on live observation alone."

## Step 4: Compliance Output

- *Action*: Open **Compliance Lab** with the same session file.
- *Action*: Run the checks or show the exported HTML report in a browser.
- *Talk*: "The same captured session can be scored automatically and exported into a portable report for review."

## Closing Line

- *Talk*: "The software contribution is the workflow around the HIL plant: observe, capture, replay, validate, and present from the same data."
