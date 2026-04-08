# Demo Walkthrough

**Duration:** 10–12 minutes
**Audience:** Capstone evaluation committee
**Goal:** Show the full analysis lifecycle — import real data, automated event detection,
compliance validation, session comparison

---

## Pre-Demo Checklist

- [ ] App is running: `python run.py`
- [ ] App opens on **Overview** page (sidebar visible on the left)
- [ ] Have a test data file ready (CSV, Excel, or JSON) — or use the bundled demo session
- [ ] No previous sessions left open from prior runs

---

## Primary Demo — Import-First Workflow

This is the recommended demo. It uses a real data file (oscilloscope capture or simulation
output) and shows every analysis step traceable back to actual measured samples.

---

### SEGMENT 1 — Import a Run File (2 minutes)

**Navigate to:** Overview page (already open at startup)

**Talking Point:**
> "The primary workflow starts with importing a captured data file — an oscilloscope CSV,
> a simulation Excel output, or a previously saved session. The app reads the file, parses
> it without inventing any missing channels, and presents a channel mapping dialog."

**Click: Import Run File**

In the Import dialog:
1. Click **Browse** and select your file (`.csv`, `.xlsx`, or `.json`)
2. The left panel shows: file format, number of rows, sample rate, parse warnings
3. The right panel shows each source column with a dropdown for its canonical name:
   - Recognised names (e.g. `freq`, `Pinv`) are pre-filled
   - Rigol channels (`CH1(V)–CH4(V)`) are left `[unmapped]` intentionally
4. Assign mappings: e.g. `CH1(V) → v_an`, `CH2(V) → i_a`
5. Click **Import**

The Replay page opens automatically.

**Talking Point:**
> "Notice that unmapped Rigol channels stay unmapped until I explicitly assign them —
> the software never fabricates a signal it didn't measure."

---

### SEGMENT 2 — Waveform Replay (2 minutes)

**You are now on:** Replay page → Waveforms tab

**Talking Point:**
> "The Waveforms tab shows the full capture timeline. I can scrub to any point —
> think of it as a DVR for the oscilloscope capture."

**Show:**
- Timeline scrubber with the full capture length
- Scrub to the fault event window — the waveforms update to that instant
- The Metrics tab: per-channel RMS, THD, peak, standard deviation
- The Spectrum tab: FFT over the selected window, harmonic peaks visible

---

### SEGMENT 3 — Automated Event Detection (2 minutes)

**Click the Events tab** in the Replay Studio

**Talking Point:**
> "Event detection runs automatically on import. Eight deterministic algorithms scan
> every channel for power-quality anomalies: voltage sags and swells, frequency
> excursions, flatlines, abrupt step changes, clipping, duplicate channels, and THD spikes."

**Point to:**
- Summary bar: "N events detected" with colored severity badges (critical / warning / info)
- Engineering stats cards: worst sag depth, max freq deviation, max THD, max flatline, confidence range
- The color-coded event rows in the table

**Click a row in the event table**

A click on any row seeks the replay scrubber to that event's start timestamp and switches back
to the Waveforms tab.

> "Clicking an event row jumps the scrubber directly to that anomaly. I can see exactly
> what the waveforms looked like during the sag, read the duration and severity from the
> table, and double-click the Note column to add an annotation."

**Double-click the Note column** on an event row to show the annotation dialog.

---

### SEGMENT 4 — Session Comparison (1 minute)

**Click the Compare tab** in the Replay Studio

**Talking Point:**
> "If I have a second session — say, a pre-fault baseline or a simulation prediction —
> I can load it here and compare channel by channel. Delta traces show the difference
> directly, and the Metrics sub-tab quantifies it: RMSE, correlation, min/max spread."

**Click Load Secondary Session** → select a second file or session

**Show:**
- Dual-color overlay: primary session in blue, secondary in green
- Delta trace panel shows the difference waveform
- Metrics tab: per-channel comparison statistics

---

### SEGMENT 5 — IEEE 2800 Compliance (2 minutes)

**Navigate to:** Compliance (click ✓ in sidebar)

**Click: Run Compliance Check**

**Talking Point:**
> "The compliance engine evaluates three IEEE 2800 interconnection requirements against
> the imported session: low-voltage ride-through, frequency stability, and voltage recovery
> after a fault clears."

**What happens:**
- Three rule rows populate with: measured value, threshold, PASS/FAIL chip
- Ride-through: minimum voltage during any sag ≥ 50% nominal
- Frequency: stayed within ±0.5 Hz of 60 Hz
- Recovery: no persisted under-voltage after fault cleared

> "This is directly tied to the standard that requires inverters to stay online during
> grid disturbances. The grading runs automatically from the captured data."

---

### SEGMENT 6 — Close (30 seconds)

**Talking Point:**
> "That's the full lifecycle from real data to engineering conclusions:
>
> 1. Import a captured file — no signal fabrication
> 2. Automated detection of 8 power-quality anomaly types
> 3. Jump-to-event replay with inline annotations
> 4. Side-by-side comparison against a baseline or simulation run
> 5. Automated IEEE 2800 compliance scoring
>
> All backed by 287 automated tests. When the full 3-phase inverter hardware
> is complete, connecting it requires only three targeted code changes — the
> analysis stack above it needs no modification."

---

## Fallback Demo — Live Demo Mode

If you don't have a data file available, use the synthetic demo session:

1. **Overview page → Start Demo Session** (labeled [Demo])
2. The app starts DemoAdapter generating synthetic 3-phase telemetry at 50 Hz
3. **Diagnostics page → Inject Voltage Sag** — watch the waveform compress and the
   insight panel flag the anomaly
4. **Replay page** — session loaded automatically; scrub the fault window
5. **Compliance page → Run Compliance Check**

**Important:** Demo mode uses software-generated waveforms, not real measurements.
Tell the audience explicitly: *"This is synthetic data for demo purposes — the import
workflow I showed first uses real oscilloscope captures."*

---

## Backup — Load a Pre-Recorded Session

If neither a live file nor a hardware connection is available:

1. Navigate to **Replay** in the sidebar
2. Click **Load Session** → open `data/demo_sessions/demo_session_baseline.json`
3. Navigate to **Events** tab — events auto-populate from the stored dataset
4. Navigate to **Compliance** → click **Run Compliance Check**

---

## Common Questions

**Q: "What hardware does this connect to?"**
A: "The software has a serial adapter for USB UART, targeting the Arduino breadboard
prototype that streams DC-bus telemetry and the full 3-phase VSI hardware that the EE team
is building. In demo mode, DemoAdapter generates synthetic 3-phase VSM telemetry."

**Q: "What is a grid-forming inverter / VSM?"**
A: "A grid-forming inverter uses a Virtual Synchronous Machine control algorithm — it
actively controls voltage and frequency to behave like a synchronous generator. This makes
it suitable for islanded operation and grid stabilization. The software monitors the VSM's
key health metrics: RMS voltage, frequency deviation, THD, and phase balance."

**Q: "Why not just use oscilloscope software?"**
A: "Oscilloscope software shows you the waveform. This tool answers the engineering
questions: Is the inverter meeting IEEE 2800 ride-through requirements? Where exactly did
the frequency excursion start? How does this run compare to the simulation prediction?
Those questions require automated detection and structured analysis, not just a trace."

**Q: "How many tests do you have?"**
A: "287 automated tests covering the signal processing pipeline, file ingestion, channel
mapping, event detection, session comparison, and compliance engine. Each of the 8 event
detectors has unit tests with injected fault signals and clean baselines to keep the false
positive rate low."

**Q: "What does IEEE 2800 require?"**
A: "Three requirements we test: low-voltage ride-through for a 50% sag (inverter stays
online), frequency staying within ±0.5 Hz of nominal, and voltage recovering to spec
within a defined window after a fault clears."

---

## What NOT to Do

- Do not navigate to **Tools** during the demo — it is a developer configuration panel
- Do not open multiple sessions before the demo — close the app and relaunch cleanly
- Do not claim the live demo mode shows real hardware data — be explicit that it is synthetic
- Do not compare numbers from demo mode to IEEE 2800 thresholds as if they are real results

---

*Last Updated: April 2026*
