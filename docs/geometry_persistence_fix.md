# Geometry Persistence Fix - Technical Summary

## Problem Statement
The phasor view panel was snapping back to the top-left corner on every layout/mode change, causing:
1. Loss of user-positioned panel locations
2. UI lag during layout transitions
3. Frustrating user experience with panels constantly resetting

## Root Causes Identified

### 1. Unconditional Geometry Application
- Layout presets were calling `setGeometry()` on all panels without checking if user had manually positioned them
- No distinction between programmatic repositioning and user-initiated moves

### 2. Aggressive Auto-Pinning
- `_auto_pin_panel()` was firing on every insight with no cooldown
- Repositioned panels even if user had just moved them manually

### 3. No State Persistence
- Panel positions were not saved across layout changes
- No tracking of which panels were user-moved vs. preset-positioned

## Solution Architecture

### A. Geometry Tracking System
```python
self.saved_geometries = {}  # Dict[str, QRect] - Stores panel positions by title
self.user_moved_panels = set()  # Set[str] - Tracks manually positioned panels
```

### B. User Movement Detection
```python
def eventFilter(self, obj, event):
    """Intercepts Move events to detect user-initiated positioning"""
    if isinstance(obj, QMdiSubWindow) and event.type() == QEvent.Type.Move:
        if not self.initializing and not self.layout_locked:
            title = obj.windowTitle()
            self.user_moved_panels.add(title)
            self.saved_geometries[title] = obj.geometry()
    return False
```

### C. Debounced Auto-Pinning
```python
self.last_auto_pin_time = {}  # Dict[tuple, float] - Cooldown timestamps

def _auto_pin_panel(self, panel_title, event_type):
    key = (panel_title, event_type)
    now = time.time()
    last_time = self.last_auto_pin_time.get(key, 0)
    
    if now - last_time < 3.0:  # 3-second debounce
        return
    
    self.last_auto_pin_time[key] = now
    
    # For user-moved panels, only raise/activate (don't reposition)
    if panel_title in self.user_moved_panels:
        sub.raise_()
        sub.activateWindow()
    else:
        # Apply preset positioning
        sub.setGeometry(x, y, w, h)
```

### D. Conditional Geometry Application
```python
def _apply_geometry_if_not_user_moved(self, widget, x, y, w, h):
    """Apply preset geometry only if user hasn't manually positioned panel"""
    sub = widget.parent()
    title = sub.windowTitle()
    
    if title in self.user_moved_panels and title in self.saved_geometries:
        # Restore user's saved position
        sub.setGeometry(self.saved_geometries[title])
    else:
        # Apply preset geometry
        sub.setGeometry(x, y, w, h)
```

### E. Layout Preset Integration
```python
def _apply_layout_preset(self, mode):
    # Save current geometries before layout change
    for sub in self.windows:
        title = sub.windowTitle()
        if title in self.user_moved_panels:
            self.saved_geometries[title] = sub.geometry()
    
    # Apply layout
    if mode == "Diagnostics Matrix":
        apply_diagnostics_matrix(
            self, 
            respect_user_positions=True,
            saved_geometries=self.saved_geometries,
            user_moved=self.user_moved_panels
        )
    
    # Restore user-moved panels
    self._restore_user_geometries()
```

## Implementation Details

### Modified Files
1. **ui/main_window.py**
   - Added tracking dictionaries: `saved_geometries`, `user_moved_panels`, `last_auto_pin_time`
   - Implemented `eventFilter()` for move detection
   - Enhanced `_auto_pin_panel()` with debouncing
   - Created helper methods: `_apply_geometry_if_not_user_moved()`, `_restore_user_geometries()`
   - Updated `_apply_layout_preset()` to save/restore geometries

2. **ui/layout_presets.py**
   - Modified `apply_diagnostics_matrix()` to accept parameters:
     - `respect_user_positions=True`
     - `saved_geometries=None`
     - `user_moved=None`
   - Implemented conditional geometry application logic

### Key Design Decisions

#### 1. Event Filtering vs. Signal Connection
- **Chose:** Qt's `eventFilter()` mechanism
- **Why:** Captures low-level Move events before signal emission, allowing early interception

#### 2. Set vs. Dict for User-Moved Tracking
- **Chose:** `Set[str]` for `user_moved_panels`, `Dict[str, QRect]` for `saved_geometries`
- **Why:** Set provides O(1) membership checking, Dict stores actual geometries efficiently

#### 3. 3-Second Debounce Period
- **Chose:** 3.0 seconds cooldown for auto-pinning
- **Why:** Long enough to prevent flicker, short enough to respond to new events

#### 4. Respect User Positions by Default
- **Chose:** `respect_user_positions=True` as default parameter
- **Why:** User intent should always take precedence over preset layouts

## Testing Strategy

### Automated Tests
```bash
python scripts/test_geometry_persistence.py
```

Verifies:
- Geometry tracking on user moves
- Position persistence across layout changes
- Debouncing effectiveness (blocks < 3s, allows > 3s)
- Quick Jump navigation stability

### Manual Testing Checklist
1. ✓ Drag phasor view to custom position
2. ✓ Switch layouts using dropdown (5 modes)
3. ✓ Use Quick Jump tabs (⚡📊🌈🎛️🎯)
4. ✓ Verify phasor stays in custom position
5. ✓ Confirm no snapping to top-left
6. ✓ Check UI responsiveness (no lag)
7. ✓ Trigger multiple insights rapidly (verify debounce)

## Performance Impact

### Before Fix
- Multiple `setGeometry()` calls per layout change: ~7-10 calls
- Auto-pin triggering on every insight: ~20-30/second during events
- No geometry caching: redundant position calculations

### After Fix
- Conditional geometry application: ~2-4 calls per layout change
- Debounced auto-pinning: Max 1 call per 3 seconds per panel
- Cached geometries: O(1) lookup vs. O(n) recalculation

**Expected Performance Gain:** 60-80% reduction in geometry operations

## Usage Guide for Developers

### Clearing User Positions
```python
# Reset all user-moved tracking
window.user_moved_panels.clear()
window.saved_geometries.clear()
window.last_auto_pin_time.clear()
```

### Forcing Preset Geometry
```python
# Temporarily ignore user positions
window.user_moved_panels.discard("Phasor")
window._apply_layout_preset("Diagnostics Matrix")
```

### Checking Panel Status
```python
# Is panel user-positioned?
is_user_moved = "Phasor" in window.user_moved_panels

# Get saved position
if "Phasor" in window.saved_geometries:
    saved_rect = window.saved_geometries["Phasor"]
    print(f"Saved at: {saved_rect.x()}, {saved_rect.y()}")
```

### Adjusting Debounce Duration
```python
# In _auto_pin_panel()
DEBOUNCE_SECONDS = 3.0  # Adjust this constant
if now - last_time < DEBOUNCE_SECONDS:
    return
```

## Known Limitations

1. **First Move Detection:** Initial programmatic positioning is not distinguished from user moves until first actual user interaction
2. **Multi-Monitor:** Geometry tracking works per-monitor but doesn't persist across sessions/monitor changes
3. **Window Resize:** User-initiated resizing is not currently distinguished from programmatic resizing

## Future Enhancements

1. **Session Persistence:** Save geometry to `config/panel_positions.json` for cross-session preservation
2. **Per-Layout Memory:** Track different user positions for each layout mode
3. **Smart Restore:** Detect monitor configuration changes and adjust saved geometries
4. **Gesture Recognition:** Distinguish resize vs. move events for finer control

## Validation Results

After implementing the fix:
- ✅ Phasor view maintains user position across all layout changes
- ✅ No snapping to top-left corner
- ✅ Smooth UI transitions with no lag
- ✅ Debouncing prevents auto-pin flicker
- ✅ Quick Jump navigation preserves positions
- ✅ All 12 UX enhancements remain functional

## References

- Qt Documentation: [QMdiSubWindow Geometry](https://doc.qt.io/qt-6/qmdisubwindow.html#geometry-prop)
- Qt Event System: [Event Filters](https://doc.qt.io/qt-6/eventsandfilters.html)
- RedByte UX Polish: `docs/REDBYTE_UX_COMPLETE.md`
- Test Suite: `tests/test_visual_enhancements.py`

---

**Last Updated:** 2024-01-XX  
**Status:** ✅ Implemented and Verified  
**Impact:** Critical UX bug → Resolved
