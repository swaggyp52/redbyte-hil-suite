# RedByte Suite Quick Start Guide

## 🚀 Launch Options

### Option 1: Main Launcher (Recommended)
```bash
bin\launch_redbyte.bat
```

This opens the **RedByte Suite Selector** with visual cards for all 5 apps:
- 🟩 RedByte Diagnostics
- 🔵 RedByte Replay Studio
- 🟪 RedByte Compliance Lab
- 🟨 RedByte Insight Studio
- 🟧 RedByte Signal Sculptor

Click any card to launch that specific app.

### Option 2: Direct App Launch
```bash
# Quick launch specific apps
bin\diagnostics.bat     # Diagnostics
bin\replay.bat          # Replay Studio

# Or use Python directly
python src\launchers\launch_diagnostics.py
python src\launchers\launch_replay.py
python src\launchers\launch_compliance.py
python src\launchers\launch_insights.py
python src\launchers\launch_sculptor.py
```

### Option 3: Legacy Demo
```bash
bin\start.bat
# or
python src\main.py
```

Launches the original monolithic demo with all panels.

---

## 📋 Typical Workflows

### Workflow 1: Live Monitoring → Timeline Review

1. **Launch Diagnostics** (🟩)
   ```bash
   bin\diagnostics.bat
   ```

2. **Start Monitoring**
   - Click **▶️ Start** in toolbar
   - Watch live waveforms in Scope
   - Observe phasor diagram updating
   - 3D system visualization rotating

3. **Inject Fault**
   - Open **💉 Fault Injector** panel
   - Select fault type (e.g., "Voltage Sag")
   - Set magnitude: 30%
   - Set duration: 2.0 seconds
   - Click **Apply Fault**

4. **Monitor Insights**
   - Watch **💡 Insights** panel
   - Critical events appear automatically
   - THD warnings, frequency drift, etc.

5. **Export to Replay**
   - Click **🔵 Open in Replay Studio** in toolbar
   - Replay Studio launches with captured session
   - All waveforms and insights preserved

6. **Review Timeline**
   - Use timeline slider to scrub through capture
   - Click **▶️ Play** to replay events
   - Press **🏷️ Add Tag** at interesting moments
   - Export tags with **💾 Export Tags**

---

### Workflow 2: Compliance Testing

1. **Launch Diagnostics** (🟩)
   - Capture test scenario with faults

2. **Export to Compliance Lab**
   - Click **🟪 Send to Compliance Lab**
   - Compliance Lab opens automatically

3. **Run Validation**
   - Click **▶️ Run Tests** in toolbar
   - View pass/fail scorecard
   - Inspect waveform thumbnails
   - Generate HTML report with **📄 Export Report**

---

### Workflow 3: Deep Insight Analysis

1. **Launch Diagnostics** (🟩)
   - Run multiple fault scenarios
   - Accumulate insights

2. **Export to Insight Studio**
   - Navigate to **Replay Studio** first (🔵)
   - Click **🟨 Open in Insight Studio**

3. **Analyze Patterns**
   - Explore insight clusters by type
   - View temporal heatmap
   - Identify recurring patterns
   - Export analysis with **📊 Export CSV**

---

## 🎨 Visual Identity Guide

Each app has a unique color theme for instant recognition:

| Icon | App                     | Color  | Use Case                  |
| ---- | ----------------------- | ------ | ------------------------- |
| 🟩   | RedByte Diagnostics     | Green  | Live monitoring           |
| 🔵   | RedByte Replay Studio   | Cyan   | Post-test review          |
| 🟪   | RedByte Compliance Lab  | Purple | Standards validation      |
| 🟨   | RedByte Insight Studio  | Amber  | Pattern analysis          |
| 🟧   | RedByte Signal Sculptor | Orange | Waveform editing          |

---

## 🔧 Troubleshooting

### "Failed to launch RedByte Suite"
**Solution:** Ensure Python and PyQt6 are installed
```bash
python --version          # Should show Python 3.9+
pip install PyQt6 numpy scipy pyqtgraph
```

### "No session data found" in Replay Studio
**Solution:** Export from Diagnostics first
1. Launch Diagnostics
2. Capture some data (click ▶️ Start)
3. Click "🔵 Open in Replay Studio" toolbar button

### Panel is missing or hidden
**Solution:** Use View menu or Quick Jump tabs
- **View → Reset Layout** restores default positions
- **Quick Jump tabs** (⚡📊🌈🎛️🎯) switch views instantly

### UI is laggy or panels snap to corners
**Solution:** Geometry persistence system active
- User-moved panels remember their position
- Auto-pinning has 3-second debounce
- If issues persist, restart the app

---

## ⌨️ Keyboard Shortcuts

### Diagnostics
- `Ctrl+P` - Pause monitoring
- `Ctrl+S` - Save session
- `Ctrl+Shift+C` - Capture snapshot
- `F11` - Toggle fullscreen

### Replay Studio
- `Space` - Play/Pause
- `Left/Right Arrow` - Seek -1s/+1s
- `Home/End` - Jump to start/end
- `T` - Add tag at current position

### All Apps
- `Ctrl+Q` - Quit application
- `Alt+F4` - Close window
- `F1` - Help/Documentation

---

## 📊 Testing Checklist

### ✅ App Launch Tests

- [ ] Main launcher opens with 5 app cards
- [ ] Diagnostics launches with green theme
- [ ] Replay Studio launches with cyan theme
- [ ] Compliance Lab launches with purple theme
- [ ] Insight Studio launches with amber theme
- [ ] Signal Sculptor launches with orange theme
- [ ] Legacy demo still works via `start.bat`

### ✅ Context Handoff Tests

- [ ] **Diagnostics → Replay:**
  - Capture session in Diagnostics
  - Click "Open in Replay Studio"
  - Replay opens with waveforms loaded
  - Insights appear in Event Log panel

- [ ] **Diagnostics → Compliance:**
  - Capture session in Diagnostics
  - Click "Send to Compliance Lab"
  - Compliance opens with validation data

- [ ] **Replay → Insights:**
  - Load session in Replay
  - Add timeline tags
  - Click "Open in Insight Studio"
  - Insights loaded with timestamps

### ✅ Visual Theme Tests

- [ ] Each app shows correct accent color
- [ ] Buttons use app-specific border colors
- [ ] Group boxes have themed titles
- [ ] Hover effects show brighter accent
- [ ] Cyber-industrial background gradients present

### ✅ Panel Stability Tests

- [ ] Drag panels to custom positions
- [ ] Switch between apps
- [ ] Return to original app
- [ ] Panels stay in user-positioned locations
- [ ] No snapping to top-left corner

### ✅ Core Functionality Tests

- [ ] **Diagnostics:** Live waveforms update at 20 Hz
- [ ] **Diagnostics:** Fault injection triggers insights
- [ ] **Replay:** Timeline scrubbing works smoothly
- [ ] **Replay:** Tags can be added and exported
- [ ] **Compliance:** Validation scorecard displays
- [ ] **Insights:** Event clusters organized by type
- [ ] **Sculptor:** Filter preview updates in real-time

---

## 🆘 Getting Help

### Documentation
- [Modular Architecture](MODULAR_ARCHITECTURE.md) - Full technical specs
- [UX Complete Guide](REDBYTE_UX_COMPLETE.md) - Visual enhancements
- [API Reference](api_reference.md) - Core module documentation

### Common Issues

**Q: How do I switch between apps?**  
A: Each app runs independently. Launch multiple apps simultaneously or use context export buttons to handoff sessions.

**Q: Where are session files stored?**  
A: `temp/redbyte_session_*.json` - one file per target app

**Q: Can I run multiple apps at once?**  
A: Yes! All apps are independent processes sharing the same backend via SessionContext.

**Q: How do I customize an app?**  
A: Edit `src/launchers/launch_*.py` to change panels, layouts, or functionality. Modify `ui/app_themes.py` for visual styling.

**Q: Is the legacy demo still available?**  
A: Yes! Use `bin\start.bat` or click "🔧 Legacy Demo" in the main launcher.

---

## 🎯 Next Steps

### For New Users
1. Launch main selector: `bin\launch_redbyte.bat`
2. Try Diagnostics first (🟩) - easiest to understand
3. Experiment with fault injection
4. Export to Replay Studio to see timeline playback
5. Explore other apps as needed

### For Developers
1. Read [MODULAR_ARCHITECTURE.md](MODULAR_ARCHITECTURE.md)
2. Explore `src/hil_core/` modules
3. Review launcher implementations in `src/launchers/`
4. Customize themes in `ui/app_themes.py`
5. Add new panels or features per app

### For Power Users
1. Master keyboard shortcuts
2. Use Quick Jump tabs (⚡📊🌈🎛️🎯) in Diagnostics
3. Set up custom layouts per app
4. Create automated test sequences
5. Export session data for external analysis

---

## 📈 Performance Tips

- **Reduce update rate** if UI lags:
  ```python
  # In launcher file
  self.timer.start(100)  # 10 Hz instead of 20 Hz
  ```

- **Limit buffer size** for lower memory:
  ```python
  self.signal_engine = SignalEngine(buffer_size=5000)  # 5k instead of 10k
  ```

- **Close unused panels** in layout:
  ```python
  sub_panel.hide()  # Hide instead of closing to preserve state
  ```

---

**Last Updated:** 2026-02-01  
**Version:** 2.0  
**Status:** ✅ Ready for Production Use

**Have fun exploring the RedByte Suite! 🔴🚀**
