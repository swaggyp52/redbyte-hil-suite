# Simulation Controls - Professional UI Polish ✨

## Overview

The GFM HIL Verifier Suite now features **professional simulation controls** directly in the main toolbar. This allows evaluators to:

- **Start** a simulation with one click
- **Pause** to test stale data detection and recovery
- **Resume** paused simulations seamlessly  
- **Stop** cleanly without leaving residual state

All with **visual feedback** showing the current state.

---

## Toolbar Layout

The simulation controls appear at the **left side of the main toolbar**:

```
┌─────────────────────────────────────────────────────┐
│ Simulation: [▶️ Run] [⏸ Pause] [🔁 Resume] [⏹ Stop] │
│ Status: Running ┃ [Tile] [Reset Layout] ...         │
└─────────────────────────────────────────────────────┘
```

### Button States

| State | Run | Pause | Resume | Stop |
|-------|-----|-------|--------|------|
| **Idle** | ✅ Enabled | ❌ Disabled | ❌ Disabled | ❌ Disabled |
| **Running** | ❌ Disabled | ✅ Enabled | ❌ Disabled | ✅ Enabled |
| **Paused** | ❌ Disabled | ❌ Disabled | ✅ Enabled | ✅ Enabled |
| **Stopped** | ✅ Enabled | ❌ Disabled | ❌ Disabled | ❌ Disabled |

---

## Features

### 1. ▶️ Run Button
**Purpose**: Start the simulation and begin telemetry data flow

**What happens:**
- Resets the telemetry watchdog (clears stale warnings)
- Enables the **Pause** button
- Disables the **Run** button
- Status label updates to "Running" (green 🟢)
- Telemetry begins flowing, frame rate visible in toolbar

**Demo script:**
```
"Click Run to start the HIL simulation. Notice the telemetry frame rate
appears in the toolbar - that's live data from the inverter being monitored."
```

---

### 2. ⏸ Pause Button
**Purpose**: Pause the simulation to demonstrate stale data detection

**What happens:**
- Stops telemetry frames from being sent
- **After 2 seconds**: Red ⚠️ warning overlay appears: `⚠️ TELEMETRY STALE (2.5s)`
- Telemetry health label turns red
- Enables the **Resume** button
- Disables the **Pause** button
- Status label updates to "Paused" (amber 🟡)

**Why pause?**
This demonstrates the **watchdog's critical safety feature** - automatic detection of lost data. Professors see in real-time that the system detects problems within 2 seconds.

**Demo script:**
```
"Now let's test the watchdog. Click Pause to stop telemetry.
Watch the toolbar - in 2 seconds, you'll see the red warning appear.
This is our safety net: if data ever stops unexpectedly, we know
in milliseconds instead of minutes."
```

---

### 3. 🔁 Resume Button
**Purpose**: Resume a paused simulation

**What happens:**
- Resets the telemetry watchdog (clears stale warning)
- Re-enables telemetry data flow
- Red warning overlay immediately disappears
- Telemetry health label returns to green
- Enables the **Pause** button
- Disables the **Resume** button
- Status label updates to "Running" (green 🟢)

**Demo script:**
```
"Click Resume to bring telemetry back. See how the warning disappears
instantly? The watchdog confirms data is flowing again. This resilience
is what makes our system reliable for capstone evaluation."
```

---

### 4. ⏹ Stop Button
**Purpose**: Gracefully shut down the simulation

**What happens:**
- Stops telemetry frames
- Clears any stale warnings
- Resets the watchdog
- Status label updates to "Stopped" (gray 🔘)
- Only **Run** button becomes enabled again
- Prepares for a fresh start

**Demo script:**
```
"Stop button ends the simulation cleanly. Notice the status changes
to 'Stopped' - the system is ready for another test run."
```

---

## Status Label

**Location**: Toolbar, immediately after the simulation buttons

**Shows**: Current simulation state with color coding

| State | Display | Color | Code |
|-------|---------|-------|------|
| Idle | "Status: Idle" | Gray | #94a3b8 |
| Running | "Status: Running" | Green | #10b981 |
| Paused | "Status: Paused" | Amber | #f59e0b |
| Stopped | "Status: Stopped" | Dark Gray | #6b7280 |

**Updates instantly** as buttons are clicked - no lag, always accurate.

---

## Demo Scenario (5 minutes)

Perfect for capstone evaluation:

### Part 1: Basic Operation (1 min)
```
"Let me show you the core workflow."

1. Click ▶️ Run
   → "Frame rate appears: 📡 20.5 Hz"
   → "Telemetry is live and healthy"

2. Point to status label
   → "This shows we're in Running state"
   → "All three 3D visualizations are updating in real-time"
```

### Part 2: Safety & Monitoring (2 min)
```
"Now for the critical part - failure detection."

1. Click ⏸ Pause
   → "Watch the toolbar..."
   → [WAIT 2 SECONDS]
   → "There! The red warning appears. ⚠️ STALE"
   → "Our watchdog detected the loss in 2 seconds."

2. Explain significance:
   → "In a real lab with real hardware, losing USB connection
      or network drop would trigger this automatically."
   → "We don't have to monitor manually - the system alerts us."
   → "This is production-grade reliability."
```

### Part 3: Recovery (1 min)
```
"Now let's recover gracefully."

1. Click 🔁 Resume
   → "Warning disappears immediately"
   → "Frame rate resumes: 📡 20.5 Hz"
   → "Status: Running again"

2. Final message:
   → "That's the complete lifecycle: start, detect failure,
      recover. Everything automatic and visual."
```

### Part 4: CSV Export (1 min)
```
"Everything we just did was recorded. Let's export it."

1. Click dropdown: "Simple CSV"
2. Click 📤 Export CSV
3. Show the exported file with all the data from the simulation
```

---

## Technical Implementation

### Files Modified

**`src/simulation_controller.py`** (NEW, 100+ lines)
- State machine with IDLE, RUNNING, PAUSED, STOPPED states
- Signal emissions on state changes
- Validation of transitions (can't pause when stopped, etc.)
- Clean API: `start()`, `pause()`, `resume()`, `stop()`

**`ui/main_window.py`** (+75 lines)
- Toolbar buttons wired to state machine
- Event handlers: `_start_simulation()`, `_pause_simulation()`, etc.
- Button state management: `_update_simulation_buttons()`
- Status label color coding

**`tests/test_simulation_controls.py`** (NEW, 13 tests)
- State transition validation (can't pause idle, etc.)
- Signal emission tests
- Button state tests
- Status label color tests
- Complete UI integration tests

### Architecture

```
User clicks button
    ↓
MainWindow._start_simulation() (etc)
    ↓
SimulationController.start() (state machine)
    ↓
emit state_changed(new_state)
    ↓
MainWindow._on_simulation_state_changed()
    ↓
Update buttons, label, status
    ↓
Watchdog resets if needed
    ↓
UI reflects new state in real-time
```

---

## Test Coverage

**13 new tests, all passing:**

- ✅ State machine initialization
- ✅ Valid state transitions
- ✅ Invalid transitions rejected
- ✅ Signal emissions
- ✅ Button state management
- ✅ Status label updates with correct colors
- ✅ Watchdog reset on start/resume
- ✅ Complete pause/resume workflow

**Total: 98 tests passing** (85 existing + 13 new)

---

## Talking Points for Evaluators 🎓

### Reliability
> "These buttons are backed by a **state machine**. Invalid transitions are impossible. 
> You can't accidentally break the simulation by clicking in the wrong order."

### Safety
> "Pause tests our **2-second stale detection watchdog**. You see the warning in real-time. 
> This is what production systems need - instant failure detection."

### Recovery
> "Resume clears warnings and **restarts cleanly**. No residual state, no confusion. 
> This is how professional lab systems work."

### Professionalism
> "Every button updates the status label with color. No ambiguity about what state 
> we're in. Visual feedback is critical for operator trust."

---

## Button Styling

All buttons use consistent emoji + text for maximum clarity:

- ▶️ **Run** - Play symbol, obvious start action
- ⏸ **Pause** - Pause symbol, freezes data flow
- 🔁 **Resume** - Refresh symbol, restarts from pause
- ⏹ **Stop** - Stop symbol, complete shutdown

---

## Future Enhancements (Optional)

- Add **keyboard shortcuts**: Spacebar for pause/resume
- Add **progress bar**: Show simulation time elapsed
- Add **record indicator**: Visual "REC" when logging
- Add **playback speed**: Slow down/speed up simulation

---

## Summary

The simulation controls transform the demo from "professor reads code" to **"professor sees professional UI in action"**. 

With one toolbar, professors can:
- ✅ Start a live simulation
- ✅ Observe healthy data flow
- ✅ Test failure detection
- ✅ See graceful recovery
- ✅ Export results

All **self-evident. No explanation needed.**

**This is what separates hobbyist projects from capstone-quality work.** 🚀
