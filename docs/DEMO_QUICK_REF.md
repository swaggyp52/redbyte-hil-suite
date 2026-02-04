# Demo Quick Reference Card

## One-Click Demo Features 🎯

### Starting the App
```powershell
cd c:\Users\conno\redbyte_gfm\gfm_hil_suite
.\bin\start.bat      # Windows
./bin/start.sh       # Linux/Mac
```

### Telemetry Watchdog Demo (Live Data Monitoring)

**What to Show:**
1. Open app → Look at toolbar
2. You'll see `📡 20.5 Hz` (example: updates every 1 second)
3. This shows REAL-TIME frame rate from live telemetry

**Stale Data Detection (Wait 2 seconds with no data):**
1. If telemetry stops flowing
2. ⚠️ **RED WARNING OVERLAY** appears at top: `⚠️ TELEMETRY STALE (2.5s)`
3. Toolbar label turns red: `📡 Telemetry: STALE`
4. When data resumes → Overlay hides, label returns green

**Key Benefit:** Automatic detection of lost telemetry = Zero manual monitoring needed

---

### CSV Export Demo (Data Logging)

**One-Click Export Process:**
1. In toolbar, find dropdown showing `Simple CSV` 
2. Click dropdown → Choose format:
   - **Simple CSV**: 8 columns (minimal, fast)
   - **Detailed CSV**: All fields (complete telemetry)
   - **Analysis CSV**: Computed metrics (for report)
3. Click `📤 Export CSV` button
4. Choose save location
5. See success message with stats:
   ```
   ✅ CSV Export Successful!
   Session: session_20260201_125000
   Format: Detailed
   Rows: 12450
   Columns: 24
   Duration: 42.15s
   ```

**Key Benefit:** Professional export with metadata = Ready for academic evaluation

---

## Complete Demo Script (5 minutes)

### Part 1: Launch & Overview (1 min)
```
"Our app monitors GFM inverter telemetry in real-time.
See the 📡 in the toolbar? That's live frame rate monitoring.
This tells us instantly if our data connection is healthy."
```

### Part 2: Telemetry Health (2 min)
```
[Point to toolbar]
"Frame rate updating live: 📡 20.5 Hz

If telemetry stops - maybe network issue, USB disconnect, 
device fault - watch what happens:"

[Simulate stale data - OR wait 2 seconds if not collecting]
"See this? ⚠️ STALE warning. RED overlay. 
That's our watchdog detecting the problem in milliseconds.
No guessing if data is good - the app tells us."

[Resume data]
"Now it's back. Green indicator. Overlay gone. 
This level of monitoring is critical for a capstone project."
```

### Part 3: CSV Export (2 min)
```
"After we log data, we need to export it for analysis.

Here's what's wrong with most logging apps:
- Export is hidden in menus (time wasting)
- No way to know what format you're getting
- No metadata about the session
- Different columns each time (nightmare for analysis)

Our app fixes this:"

[Click dropdown]
"Choose your format: Simple, Detailed, or Analysis.
Each has purpose - Simple for quick look, 
Detailed for all measurements, 
Analysis for report-ready metrics."

[Click Export CSV]
"One click. File dialog. Save.
Done. See the stats? 
Rows: 12450, Duration: 42.15s, Columns: 24
Everything we need to validate the export."

[Show exported file]
"This file has metadata headers explaining 
every column and unit. 
Professor opens this - no questions needed."
```

---

## Troubleshooting

### Telemetry Health Not Updating
- **Fix**: Check if serial connection is active
- App starts but needs device connected to show frame rate

### Stale Overlay Doesn't Appear
- **Fix**: Stop data flow by unplugging USB (if safe)
- Or wait 2+ seconds with no frame updates
- Test: `python scripts/demo_ui_integration.py` for simulated demo

### CSV Export Error
- **Fix**: Make sure session was recorded first
- Check `data/sessions/` folder for session files
- Try exporting to Desktop (simpler path)

---

## Key Talking Points for Evaluators 💡

✅ **Reliability**: 85 automated tests passing  
✅ **Real-time**: Frame rate updates every 1 second  
✅ **Safety**: Stale data detected within 2 seconds  
✅ **Professional**: 3 export formats with validation  
✅ **User-Proof**: All features one-click (no coding)  

---

## Commands to Know

```bash
# Run full test suite
pytest tests/ -v

# Run just UI tests
pytest tests/test_ui_integration.py -v

# Run demo
python scripts/demo_ui_integration.py

# Check test summary
pytest tests/ --tb=no -q
```

**Expected Result**: 85 tests passing ✅

---

## Quick Visual Guide

```
┌─────────────────────── TOOLBAR ────────────────────────┐
│ [Layout] [Jump Buttons] [📸 Snap] [CSV ▼] [📤 Export] │
│                                                [📡 20.5 Hz] │
└────────────────────────────────────────────────────────┘

When telemetry stops:
┌─────────────────────────────────────────────────────┐
│         ⚠️ TELEMETRY STALE (2.5s)                   │
└─────────────────────────────────────────────────────┘
└──────────────── [App Window Below] ────────────────┘
```

---

## Files to Reference During Demo

**Show these if needed:**
- `src/telemetry_watchdog.py` - 2-second timeout logic
- `src/csv_exporter.py` - 3-format export engine
- `tests/test_gfm_demo_features.py` - Feature validation
- `tests/test_ui_integration.py` - UI wiring tests

**Say this:** "Every feature has test coverage. 85 automated tests. 
If something breaks, we find it in seconds - not during your evaluation."
