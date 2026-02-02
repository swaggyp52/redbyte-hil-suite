# UI Stability Fixes - Root Cause Analysis & Resolution

## 🔥 Issues Identified

### 1. **Infinite Layout Reinitialization Loop**
**Root Cause:** `LayoutManager.on_frame()` was automatically switching to "3D Ops View" whenever rotor angle data arrived, triggering `_apply_layout_preset()` repeatedly.

**Symptom:** UI constantly resetting, dropdowns ineffective

**Fix:**
```python
# src/layout_manager.py
def on_frame(self, frame):
    # Disabled automatic layout switching to prevent UI resets
    pass
```

---

### 2. **Recursive Signal Triggers**
**Root Cause:** `layout_combo.currentTextChanged` signal fired even during programmatic `setCurrentText()` calls, causing recursive `_apply_layout_preset()` execution.

**Symptom:** Dropdown selections triggering infinite layout reloads

**Fix:**
```python
# ui/main_window.py
self.layout_combo.blockSignals(True)
self.layout_combo.setCurrentText(mode)
self.layout_combo.blockSignals(False)
```

---

### 3. **Missing Layout Lock Guards**
**Root Cause:** No mechanism to prevent concurrent or recursive layout changes during initialization or demo mode toggle.

**Symptom:** Multiple layout applications stacking up, causing UI flicker

**Fix:**
```python
# ui/main_window.py
self.layout_locked = False  # Added in __init__

def _apply_layout_preset(self, mode):
    if self.layout_locked:
        logger.debug(f"Layout change blocked (locked): {mode}")
        return
    logger.info(f"Applying layout: {mode}")
    # ... rest of function
```

---

### 4. **Stylesheet Applied Before Window Shown**
**Root Cause:** `app.setStyleSheet()` called before `window.show()`, causing Qt to discard or reset styles during window initialization.

**Symptom:** Visual changes not visible, app looks unstyled

**Fix:**
```python
# src/main.py
window.show()

# Apply stylesheet AFTER window is shown to prevent style resets
app.setStyleSheet(get_global_stylesheet())
```

---

### 5. **Double Demo Mode Initialization**
**Root Cause:** `enable_demo_mode()` could be called multiple times due to signal/slot connections and programmatic toggles.

**Symptom:** Demo assets regenerated mid-session, sessions reloaded

**Fix:**
```python
def enable_demo_mode(self):
    if self.demo_enabled:
        logger.debug("Demo mode already enabled, skipping")
        return
    logger.info("Enabling demo mode...")
    self.demo_enabled = True
```

---

## ✅ Implementation Summary

### Files Modified
1. **ui/main_window.py**
   - Added `layout_locked` flag
   - Added `initializing` flag
   - Signal blocking in `_load_last_layout()`
   - Layout lock guard in `_apply_layout_preset()`
   - Demo mode guard in `enable_demo_mode()`
   - Debug logging throughout

2. **src/layout_manager.py**
   - Disabled automatic layout switching in `on_frame()`

3. **src/main.py**
   - Moved `app.setStyleSheet()` to after `window.show()`
   - Signal blocking when programmatically setting demo checkbox

---

## 🧪 Verification

Run the stability test:
```bash
python tests/test_ui_stability.py
```

All 6 tests should pass:
- ✓ Layout lock guards
- ✓ Signal blocking
- ✓ Initializing flag
- ✓ Auto-switch disabled
- ✓ Stylesheet order
- ✓ Demo mode guard

---

## 🎯 Expected Behavior After Fix

### Before
- Clicking layout dropdown → UI resets every frame
- Demo mode toggle → initializes twice
- No visual style changes visible
- Constant flicker/reload

### After
- Layout dropdown selections persist
- Demo mode initializes once
- Global stylesheet visible immediately
- Smooth, stable UI with no resets

---

## 📊 Debug Mode

If issues persist, check logs for:
```
INFO - Applying layout: Diagnostics Matrix
DEBUG - Layout change blocked (locked): Full View
DEBUG - Demo mode already enabled, skipping
```

These indicate the guards are working correctly.

---

## 🚀 Next Steps

1. Launch app: `python -m src.main --demo`
2. Test layout dropdown switching
3. Toggle demo mode on/off
4. Verify no UI resets occur
5. Confirm dark theme is visible

If problems persist, check for:
- Orphaned `QTimer` callbacks calling layout methods
- Focus events triggering resets
- External signal connections to `_apply_layout_preset`
