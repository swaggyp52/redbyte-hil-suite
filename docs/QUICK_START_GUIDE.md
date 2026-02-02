# RedByte UX Quick Start Guide

## 🚀 Launch the Application

### Standard Launch
```bash
cd gfm_hil_suite
python src/main.py
```

### Demo Mode Launch
```bash
bin/demo_launcher.bat  # Windows
bin/demo_launcher.sh   # Linux/Mac
```

**What you'll see:**
1. Animated rotor splash screen (2 seconds)
2. Main window with cyber-industrial theme
3. Diagnostics Matrix layout (default)
4. Neon green toolbar with Quick Jump tabs

---

## 🎨 Explore the New Visual Theme

### Color System
- **Background:** Deep navy/graphite gradients
- **Accents:** Neon green (#10b981), blue (#3b82f6), magenta (#8b5cf6)
- **Text:** Off-white (#e8eef5) on dark backgrounds

### Typography
- **Font:** JetBrains Mono (monospace)
- **Size:** 9pt (compact, information-dense)
- **Headers:** Bold 700 weight with green accents

### Interactive Elements
- **Buttons:** Pill-shaped with glassmorphic transparency
- **Hover:** Neon green glow on interactive elements
- **Selected:** Bright green background with white text

---

## ⚡ Navigate with Quick Jump Tabs

Located in toolbar after "Layout" dropdown:

### ⚡ Diagnostics
**Purpose:** High-density cockpit view  
**Layout:**
```
[3D System (large)]  [Insights] [Phasor]
[3D System (cont.)]  [Dashboard        ]
[Scope            ]  [Injector + Replay]
```
**Use for:** Live monitoring, fault diagnosis

### 📊 Timeline
**Purpose:** Event history and replay  
**Layout:** Replay Studio + Insights + Dashboard  
**Use for:** Session playback, event analysis

### 🌈 Spectral
**Purpose:** FFT spectrum analysis  
**Layout:** Replay Studio (Spectrum tab) + Scope + Phasor  
**Use for:** Harmonic analysis, THD investigation

### 🎛️ Grid
**Purpose:** All panels in balanced arrangement  
**Layout:** 8 panels tiled evenly  
**Use for:** Full system overview

### 🎯 Minimal
**Purpose:** Essential monitoring only  
**Layout:** Scope + Phasor (large views)  
**Use for:** Clean presentations, focused monitoring

**How to use:**
1. Click any Quick Jump button
2. System instantly switches layout
3. Overlay confirms: "⚡ Jumped to [Mode] View"

---

## 📍 Experience Auto-Pinning

**What is it:** System automatically positions relevant panels when insights detected

### Auto-Pin Triggers

**Unbalance/Phase Issues → Phasor View (top-left)**
- When: "Phase Unbalance" insight detected
- Why: Phasor shows angular deviations visually
- Action: Phasor floats to prominent position

**Harmonic/THD Events → Spectrum Analysis (top-left)**
- When: "Harmonic Bloom" or high THD
- Why: Spectrum tab shows frequency content
- Action: Replay Studio opens on Spectrum tab

**Frequency Events → Scope + Insights (split)**
- When: "Frequency Undershoot" detected
- Why: Scope shows real-time freq, Insights shows history
- Action: Both panels positioned for comparison

**Recovery Events → Dashboard (bottom-right)**
- When: "Recovery Delay" insight
- Why: Dashboard shows compliance metrics
- Action: Dashboard positioned for validation review

**How to see it:**
1. Inject fault (Fault Injector panel)
2. Wait for insight detection (~1-2 seconds)
3. Relevant panel auto-pins with overlay message
4. Close panel or switch layout when done

---

## 🎯 Use Enhanced Phasor View

### Event Markers (⭐)
**What:** Star symbols mark significant events on phasor diagram

**When added:**
- Tag clicks in Replay Studio
- Peak THD moments (>5%)
- Manual event triggers

**How to see:**
1. Open Phasor View
2. Let system run for ~10 seconds
3. High THD events automatically marked
4. Last 10 events persistent

### Angular Deviation Bands
**What:** Semi-transparent blue arcs showing ±15° tolerance zones

**Purpose:** Visual feedback on phase alignment quality  
**Positions:** 0°, 120°, 240° (ideal 3-phase)

**How to toggle:**
```python
# Programmatically (for custom scripts)
phasor_view.update_deviation_bands(show=True, tolerance_deg=15)
```

**Interpretation:**
- Phasors inside bands: Good alignment ✅
- Phasors outside bands: Phase error ⚠️

---

## 📊 Explore Scope Energy Ribbons

### Energy Ribbons
**What:** RMS bands overlaid on live waveforms

**Features:**
- Color-coded by phase (yellow, green, magenta)
- Opacity based on THD (higher THD = more opaque)
- 20px wide semi-transparent lines

**How to see:**
1. Open Inverter Scope (Voltage mode)
2. Let system acquire data (~3 seconds)
3. RMS bands appear behind waveforms
4. Watch opacity increase during faults

### Mini-FFT Sparkline
**What:** FFT analysis tooltip on mouse hover

**How to use:**
1. Hover mouse over scope waveform
2. Mini-FFT label appears below plot
3. Shows: `⚡ FFT @ t=X.XXXs: Peak XXHz (XXV)`
4. Move cursor to analyze different time windows

**Window size:** 64 samples centered on cursor  
**Update:** Real-time as you move mouse

---

## 🌳 Navigate Insights Event Clusters

### Tree Structure
```
⚡ Harmonic Bloom Events (3)
  └─ t=12.34s — THD spiked to 8.2%
  └─ t=15.67s — 5th harmonic dominant
  └─ t=18.90s — Recovered to 2.1%

⚖️ Phase Unbalance Events (2)
  └─ t=21.45s — 18° deviation detected
  └─ t=24.78s — Corrected to 3° nominal

📊 Frequency Undershoot Events (1)
  └─ t=27.89s — Dropped to 58.7Hz
```

### Controls
- **Expand All:** Show all individual events
- **Collapse All:** Show only category headers
- **Clear:** Reset all insights and counters

### Color Coding
- **Orange (⚡):** Harmonic events
- **Red (⚖️):** Unbalance/phase issues
- **Purple (📊):** Frequency events
- **Pink (📉):** Undershoot/overshoot
- **Green (🔄):** Recovery events
- **Dark Red (💥):** Critical faults

### Summary Bar
**Format:** `Total Events: 12 | Critical: 3`  
**Critical Highlight:** Red background glow when critical count > 0

---

## 📸 Capture Annotated Scenes

### Manual Capture
1. Click **📸 Capture Scene** button in toolbar
2. All visible panels captured with annotations
3. Saved to `snapshots/` folder

### Auto-Capture
**Triggers automatically on:**
- Fault injections
- Insight detections (high priority)
- System status changes (NOMINAL → CRITICAL)

### Annotation Overlay
**Top bar of each snapshot shows:**
```
📸 FAULT: voltage_sag | t=12.34s | THD=5.2% | 
Freq=59.98Hz | Rotor=87° | Insights=3
```

### Metadata JSON
**Saved alongside images:**
```json
{
  "timestamp": "20260201_143022",
  "event_type": "fault",
  "event_name": "voltage_sag",
  "annotations": {
    "timestamp": 12.34,
    "thd": 5.2,
    "frequency": 59.98,
    "rotor_angle": 87.0,
    "insight_count": 3,
    "system_status": "DEGRADED"
  }
}
```

**Use case:** Professional reports, post-demo documentation

---

## 💡 Hover for Tooltips

**Coverage:** 55+ tooltips across all UI elements

### Where to find tooltips:
- ✅ All toolbar buttons
- ✅ Quick Jump tabs
- ✅ Layout dropdown
- ✅ Scope controls (Pause, Clear, Mode)
- ✅ Phasor controls (Scale, Trail)
- ✅ Fault injector buttons
- ✅ Insights panel controls
- ✅ Dashboard actions

### Example tooltips:
```
Tile Windows: "Arrange all panels in a tiled grid layout"
Demo Mode: "Enable automated demo mode with scripted fault injections"
⚡ Diagnostics: "Switch to Diagnostics Matrix layout - high-density cockpit view"
Inject Sag: "Inject voltage sag event (0.5s duration, 30% depth)"
```

**Pro tip:** Hover over any control before clicking to understand its purpose

---

## 📋 Validation Dashboard Enhancements

### Waveform Thumbnails
**What:** 120x40px mini-waveforms in validation table

**Features:**
- Real-time snapshot of signal during event
- Neon green trace with blue border
- Auto-normalized to widget height

**How to see:**
1. Open Validation Dashboard
2. Run scenario validation (Fault Injector → Run Scenario)
3. Results appear with inline waveform snapshots

### Event Timeline
**What:** Color-coded timeline bar showing event sequence

**Colors:**
- Red bars: Injected faults
- Green bars: Detected insights

**Interpretation:** Visual correlation between faults and system response

---

## 🎭 Demo Mode Features

### Enable Demo Mode
**Toolbar:** Check "Demo Mode" button  
**Effect:** Enables scripted fault injections

### Scriptable Events
Edit `demo_script.json` to define:
```json
{
  "events": [
    {"time": 5.0, "type": "inject_sag", "params": {...}},
    {"time": 10.0, "type": "inject_drift", "params": {...}},
    ...
  ]
}
```

### Auto-Completion
**When demo finishes:**
1. Auto-generates HTML report
2. Opens report in browser
3. Shows "DEMO COMPLETE" overlay
4. Packages snapshots to `demo_output.zip`

---

## 🎨 Customize Layout Presets

### Current Presets
1. **Diagnostics Matrix** - Cockpit view
2. **Full View** - All panels tiled
3. **Engineer View** - Scope + Phasor + Injector + Sculptor
4. **Analyst View** - Replay + Analysis + Dashboard
5. **3D Ops View** - 3D System + Phasor + Injector

### Switch Layouts
**Method 1:** Use Layout dropdown in toolbar  
**Method 2:** Use Quick Jump tabs  
**Method 3:** Drag panels manually (layout saved automatically)

### Layout Memory
**Auto-saved to:** `config/last_layout.json`  
**Restored on:** Application restart

---

## 🔧 Troubleshooting

### Stylesheet Not Visible
**Issue:** UI appears unstyled  
**Fix:** Stylesheet applied after window shown (automatic)

### Layout Resets on Preset Change
**Issue:** Panels jump around unexpectedly  
**Fix:** Layout locking prevents this (automatic)

### Animations Laggy
**Issue:** Low frame rate on animations  
**Check:** GPU acceleration enabled (pyqtgraph OpenGL)

### Tooltips Not Appearing
**Issue:** Hover doesn't show tooltips  
**Fix:** Ensure `apply_all_tooltips(window)` called in MainWindow.__init__

---

## 📚 Additional Resources

- **Full Implementation:** [docs/redbyte_ux_polish.md](docs/redbyte_ux_polish.md)
- **Before/After:** [docs/before_after_comparison.md](docs/before_after_comparison.md)
- **Stability Fixes:** [docs/ui_stability_fixes.md](docs/ui_stability_fixes.md)

---

## 🎯 Quick Reference

| Feature | Location | Shortcut |
|---------|----------|----------|
| Quick Jump | Toolbar | Click tab buttons |
| Capture Scene | Toolbar | 📸 button |
| Layout Presets | Toolbar dropdown | Select from list |
| Auto-Pinning | Automatic | On insight detection |
| Event Markers | Phasor View | Auto on high THD |
| Mini-FFT | Scope | Hover over waveform |
| Event Clusters | Insights Panel | Tree view |
| Waveform Thumbnails | Dashboard | Scorecard tab |
| Tooltips | All controls | Hover cursor |
| Animated Splash | Startup | Auto 2-second display |

---

**🎉 Enjoy your premium RedByte-grade HIL Verifier Suite!**
