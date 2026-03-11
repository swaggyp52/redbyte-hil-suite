# Demo Launch Instructions

> Legacy monolithic demo guide. For the current capstone demo path, start with `bin\launch_redbyte.bat` and use [docs/presentation/demo_script.md](docs/presentation/demo_script.md).

## Quick Launch Options (Legacy Demo)

### Option 1: Windowed Mode (Recommended for Testing)
**Best for testing simulation controls**
```batch
run_demo_windowed.bat
```
- Runs in normal window (not fullscreen)
- Easy to close with X button
- Shows console for debugging
- Simulation controls fully accessible

### Option 2: No-Console Mode
**Clean demo launch without console window**
```batch
run_demo_nocon.bat
```
- No console window
- Uses `pythonw.exe`
- Clean presentation
- Close with Alt+F4

### Option 3: PowerShell Direct
**For manual control**
```powershell
cd C:\Users\conno\redbyte_gfm\gfm_hil_suite
$env:PYTHONPATH = "."
.\.venv\Scripts\python.exe src\main.py --demo
```

### Option 4: Without Demo Mode
**Normal window without fullscreen**
```powershell
cd C:\Users\conno\redbyte_gfm\gfm_hil_suite
$env:PYTHONPATH = "."
.\.venv\Scripts\python.exe src\main.py
```

## Simulation Controls

The simulation control buttons are at the top toolbar:

- **▶️ RUN** - Start 20 Hz telemetry stream
- **⏸ PAUSE** - Stop telemetry (triggers red stale warning after 2 seconds)
- **🔁 RESUME** - Restart telemetry flow
- **⏹ STOP** - Clean shutdown

## Exiting Fullscreen Demo Mode

When demo launches in fullscreen:
- Press **ESC** key to exit fullscreen
- Or use **Alt+F4** to close application

## Troubleshooting

### Buttons Don't Respond
- Make sure you clicked inside the main window area first (to give it focus)
- Check that the demo finished loading (wait for splash screen to close)
- Try windowed mode: `run_demo_windowed.bat`

### Can't Close Window
- Press **ESC** to exit fullscreen
- Use **Alt+F4** to force close
- Or use Task Manager to end Python process

### Console Window Blocks View
- Use `run_demo_nocon.bat` instead
- Or use `pythonw.exe` instead of `python.exe`

## What to Test

1. **Run Button**: Click ▶️ RUN
   - Status changes to "Running" (green)
   - Frame rate appears: "📡 ~20 Hz"
   - Plots start updating with waveforms

2. **Pause Button**: Click ⏸ PAUSE
   - Status changes to "Paused" (amber)
   - After 2 seconds: Red "⚠️ STALE DATA" warning appears
   - Frame rate stops updating

3. **Resume Button**: Click 🔁 RESUME  
   - Red warning disappears
   - Status returns to "Running" (green)
   - Data flows again

4. **Stop Button**: Click ⏹ STOP
   - Status changes to "Stopped" (gray)
   - Cleans up gracefully

## Recent Fixes

✅ Added ESC key handler to exit fullscreen demo mode  
✅ Fixed TypeError in overlay messages (removed invalid `duration` parameter)  
✅ Created windowed launch option for easier testing  
✅ Verified simulation controller signal connections working  

Current validation snapshot is maintained in `docs/REPO_HEALTH_REPORT.md`.
