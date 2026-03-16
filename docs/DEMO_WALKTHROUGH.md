# Demo Walkthrough

**Duration**: 8–10 minutes
**Audience**: Capstone evaluation committee
**Goal**: Show the full HIL monitoring lifecycle — live waveforms, fault detection, replay, and IEEE compliance

---

## Pre-Demo Checklist

- [ ] App is running: `python run.py`
- [ ] App opens on **Overview** page (sidebar visible on the left)
- [ ] Session bar at top shows `■ READY`
- [ ] No previous sessions left open from prior runs

---

## Demo Flow

### SEGMENT 1 — Overview & Launch (1 minute)

**Navigate to:** Overview page (already open at startup)

**Talking Point:**
> "This is the RedByte GFM HIL Suite — a Hardware-in-the-Loop diagnostics platform
> for grid-forming inverters using a Virtual Synchronous Machine control model.
> The sidebar on the left gives us six functional areas. Let me start a session."

**Click: Start Demo Session**

The app:
- Starts the DemoAdapter (50 Hz synthetic 3-phase telemetry)
- Begins recording the session automatically
- Navigates to the **Console** page

---

### SEGMENT 2 — Console Overview (2 minutes)

**You are now on:** Console page

**Talking Point:**
> "The Console page is the single-screen overview. Top bar shows live metrics:
> frequency, RMS voltage, THD, and output power — all updating in real time.
> Below that: three-phase waveforms on the left, phasor diagram in the centre,
> and an AI-driven insights panel on the right."

**Point to:**
- Header bar: `FREQ 60.02 Hz`, `RMS 120.3 V`, `THD 1.2%`, `P 0.99 kW`
- Status badge (top right): `✓ STABLE` (green)
- InverterScope (left): V_abc and I_abc waveforms animating at 25 Hz
- PhasorView (centre): three phasor vectors rotating
- InsightsPanel (right): empty or showing baseline info

---

### SEGMENT 3 — Fault Injection & Anomaly Detection (3 minutes)

**Navigate to:** Diagnostics (click ⚡ in sidebar)

**Talking Point:**
> "The Diagnostics page gives us direct controls. I'll inject a voltage sag now
> to simulate an under-voltage event — the kind that triggers IEEE 2800 ride-through
> requirements."

**Click: Inject Voltage Sag** (in the FaultInjector panel, bottom-right)

**What happens (watch in real time):**
- InverterScope: V_abc compresses from ±170 V to ±100 V (60% sag)
- PhasorView: phasor vectors shorten
- Health card badge switches from `✓ STABLE` → `✕ FAULT ACTIVE` (red)
- RMS metric turns red
- After ~3 seconds: InsightsPanel shows `⚡ Voltage Sag` event cluster

**Talking Point:**
> "The InsightEngine detected the anomaly and classified it automatically —
> no manual threshold tuning. That cluster will be used for compliance scoring.
> Let me click Console to see the full picture now."

**Navigate to:** Console (click 📐 in sidebar)

**Show:** Header badge `✕ FAULT ACTIVE`, red RMS chip, InsightsPanel cluster

---

### SEGMENT 4 — Replay (1 minute)

**Navigate to:** Replay (click ⏵ in sidebar)

**Talking Point:**
> "Every session is auto-recorded as a Data Capsule — JSON that includes raw frames,
> computed insights, and event markers. The Replay page loads the current session
> automatically. We can scrub back to see exactly when the sag occurred."

**Show:**
- Timeline scrubber with the sag event marker visible
- Scrub to t ≈ 7 s — waveforms replay the compression
- Scrub back to beginning — normal waveforms

---

### SEGMENT 5 — IEEE 2800 Compliance (2 minutes)

**Navigate to:** Compliance (click ✓ in sidebar)

**Click: Run Compliance Check**

**What happens:**
- Three IEEE 2800 rules are evaluated against the recorded session:
  - **Ride-through 50% sag** — checks minimum voltage during sag event
  - **Frequency ±0.5 Hz** — checks freq stayed between 59.5–60.5 Hz
  - **Voltage recovery** — checks no under-voltage persisted after fault cleared

**Show:**
- All three rows populate with measured values and PASS/FAIL chips
- Ride-through rule: depends on sag depth — likely FAIL at 60% sag (by design)
- Frequency rule: PASS
- Recovery rule: PASS

**Talking Point:**
> "This is directly tied to IEEE 2800, the standard for interconnection of
> grid-forming inverters. The compliance engine runs automatically on the
> captured session data — no manual data entry."

**Click: Export HTML Report** (or Export CSV)

**Show:** Browser opens with the generated compliance report.

---

### SEGMENT 6 — Close (30 seconds)

**Click: Stop (■)** in the session bar

**Talking Point:**
> "That's the full lifecycle:
>
> 1. Live 3-phase monitoring at 25 Hz
> 2. AI-driven anomaly detection with 3-second debounce
> 3. Full session recording and replay
> 4. Automated IEEE 2800 compliance scoring
> 5. Export to HTML and CSV
>
> All backed by 125+ automated tests and running entirely in software —
> ready to connect to real inverter hardware when the power stage is complete."

---

## Backup: Load a Pre-recorded Session

If the live demo has issues, load the bundled baseline session:

1. Navigate to **Replay** in the sidebar
2. Click **Load Session** → open `data/demo_sessions/demo_session_baseline.json`
3. Navigate to **Compliance** → click **Run Compliance Check**
4. All rules populate from the pre-recorded data

---

## Common Questions

**Q: "What hardware does this connect to?"**
A: "The software has a serial adapter for USB UART (the Arduino breadboard prototype)
and an OpalRT TCP adapter stub for full bench hardware. In demo mode, DemoAdapter
generates synthetic 3-phase VSM telemetry at 50 Hz."

**Q: "What is a VSM / grid-forming inverter?"**
A: "A grid-forming inverter behaves like a virtual synchronous machine — it controls
voltage and frequency actively, unlike grid-following inverters. This makes it suitable
for islanded or weak-grid operation. The software monitors the VSM's health metrics."

**Q: "How many tests do you have?"**
A: "125 automated tests covering the DSP pipeline, session recorder, compliance engine,
and all UI widgets. CI runs on every push across Ubuntu and Windows."

**Q: "What does IEEE 2800 require?"**
A: "Three key requirements we test: ride-through for a 50% voltage sag for at least
160 ms, frequency staying within ±0.5 Hz, and voltage recovering within spec
after a fault clears."

---

## What NOT to Do

- Do not open multiple sessions before the demo — close the app and relaunch
- Do not use `src/redbyte_launcher.py` — that is old architecture, not used
- Do not navigate to Tools page during the demo — it is a dev-only configuration panel
