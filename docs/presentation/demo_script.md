# Live Demo Script

**Setup:**

1. Launch `gfm_hil_suite`.
2. Enable "Demo Mode" (View -> Demo Mode).
3. Arrange windows: Monitor (Left), Session (Right).

**Step 1: Live Monitoring**

- *Action*: Point to the oscillating signal traces.
- *Talk*: "Here we see the live telemetry from the VSM. The 'noise' you see is simulated harmonic distortion."
- *Action*: Click "Pause", zoom in on a waveform.
- *Talk*: "We can pause and inspect transients instantly."

**Step 2: Recording**

- *Action*: Click "Start Recording" in Session Manager.
- *Action*: Wait 5 seconds. Click "Stop".
- *Talk*: "The system buffers data and writes a 'Data Capsule' JSON file, preserving all metadata."

**Step 3: Post-Mortem Analysis**

- *Action*: Open "Analysis & Comparison" App.
- *Action*: Load `data/demo_sessions/session_baseline.json` as Reference.
- *Action*: Load `data/demo_sessions/session_sag.json` as Test.
- *Action*: Click "Compare".
- *Talk*: "Here we compare a nominal run against a fault scenario. The system calculates the RMSE instantly, validating our control response."
