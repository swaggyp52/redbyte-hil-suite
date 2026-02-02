"""
RedByte Tooltip Manager - Comprehensive hover tooltips for all widgets
"""

# Tooltip definitions for all UI elements
TOOLTIPS = {
    # Main Window
    "tile_windows": "Arrange all panels in a tiled grid layout",
    "reset_layout": "Reset to default professional grid arrangement",
    "demo_mode": "Enable automated demo mode with scripted fault injections",
    "presentation_mode": "Hide controls and maximize visualization panels",
    "capture_scene": "Capture snapshots of all visible panels with timestamp",
    
    # Quick Jump Tabs
    "jump_diagnostics": "Switch to Diagnostics Matrix layout - high-density cockpit view",
    "jump_timeline": "Focus on replay timeline and event history",
    "jump_spectral": "View FFT spectrum analysis and harmonic content",
    "jump_grid": "Show all panels in balanced grid arrangement",
    "jump_minimal": "Minimal view - scope and phasor only",
    
    # Layout Presets
    "diagnostics_matrix": "High-density cockpit with 3D system, phasor, insights, scope, and dashboard",
    "engineer_view": "Engineering focus - scope, phasor, fault injector, and signal sculptor",
    "analyst_view": "Analysis focus - replay studio, analysis app, and validation dashboard",
    "3d_ops_view": "Operations view - 3D system, phasor diagram, and fault injector",
    "full_view": "Show all panels in tiled arrangement",
    
    # Inverter Scope
    "scope_pause": "Pause live data acquisition (buffers remain active)",
    "scope_clear": "Clear all buffered waveform data",
    "scope_mode_voltage": "Display 3-phase voltage waveforms (V_an, V_bn, V_cn)",
    "scope_mode_current": "Display 3-phase current waveforms (I_a, I_b, I_c)",
    "scope_mode_spectrum": "Display FFT spectrum of V_an with harmonic peaks",
    
    # Phasor View
    "phasor_scale": "Adjust phasor diagram voltage range",
    "phasor_trail": "Enable/disable ghost trails showing phasor history",
    
    # Fault Injector
    "inject_sag": "Inject voltage sag event (0.5s duration, 30% depth)",
    "inject_swell": "Inject voltage swell event (0.5s duration, 110% magnitude)",
    "inject_phase_jump": "Inject sudden phase angle shift (30° discontinuity)",
    "inject_unbalance": "Create phase unbalance (reduce one phase by 20%)",
    "inject_frequency_drift": "Simulate gradual frequency drift (±2 Hz over 2s)",
    "fault_duration": "Duration of injected fault event in seconds",
    "fault_magnitude": "Severity/magnitude of fault (percent or absolute)",
    
    # Replay Studio
    "replay_load": "Load recorded session from JSON file",
    "replay_play": "Start playback of recorded session",
    "replay_pause": "Pause playback",
    "replay_speed": "Adjust playback speed (1x = real-time)",
    "replay_tag": "Add annotation tag at current playback position",
    "replay_export": "Export session with tags to JSON file",
    
    # Insights Panel
    "insights_expand": "Expand all event clusters to show individual events",
    "insights_collapse": "Collapse all event clusters to category level",
    "insights_clear": "Clear all accumulated insights and reset counters",
    
    # Validation Dashboard
    "validation_clear": "Clear validation scorecard results",
    "compliance_tab": "View IEEE 2800 compliance check results",
    
    # 3D System View
    "view_3d_rotate": "Click and drag to rotate 3D system view",
    "view_3d_zoom": "Scroll to zoom in/out on system components",
    "view_3d_reset": "Reset camera to default view angle",
    
    # Signal Sculptor
    "sculptor_harmonic": "Inject specific harmonic frequency component",
    "sculptor_noise": "Add white noise to signal (SNR control)",
    "sculptor_offset": "Apply DC offset to all phases",
    
    # Analysis App
    "analysis_compute": "Compute RMS, THD, and frequency statistics",
    "analysis_export": "Export analysis results to CSV file",
    
    # Session Manager
    "session_new": "Create new recording session",
    "session_save": "Save current session with tags and metadata",
    "session_load": "Load existing session from file",
    
    # Status Bar Metrics
    "status_rms": "Root Mean Square voltage - indicates signal magnitude",
    "status_thd": "Total Harmonic Distortion - measure of waveform quality (% of fundamental)",
    "status_freq": "Grid frequency measurement (nominal 50/60 Hz)",
    "status_phase": "Phase angle difference between A-B phases",
}

def get_tooltip(key):
    """Get tooltip text for a given widget key"""
    return TOOLTIPS.get(key, "")

def apply_tooltips_to_main_window(window):
    """Apply all tooltips to main window widgets"""
    # Toolbar actions
    for action in window.toolbar.actions():
        text = action.text()
        if "Tile" in text:
            action.setToolTip(get_tooltip("tile_windows"))
        elif "Reset" in text:
            action.setToolTip(get_tooltip("reset_layout"))
        elif "Demo" in text:
            action.setToolTip(get_tooltip("demo_mode"))
        elif "Presentation" in text:
            action.setToolTip(get_tooltip("presentation_mode"))
        elif "Capture" in text:
            action.setToolTip(get_tooltip("capture_scene"))
    
    # Quick Jump actions
    if hasattr(window, 'jump_diagnostics'):
        window.jump_diagnostics.setToolTip(get_tooltip("jump_diagnostics"))
        window.jump_timeline.setToolTip(get_tooltip("jump_timeline"))
        window.jump_spectral.setToolTip(get_tooltip("jump_spectral"))
        window.jump_grid.setToolTip(get_tooltip("jump_grid"))
        window.jump_minimal.setToolTip(get_tooltip("jump_minimal"))
    
    # Layout combo
    if hasattr(window, 'layout_combo'):
        window.layout_combo.setToolTip("Select layout preset - each optimized for different workflows")

def apply_tooltips_to_scope(scope):
    """Apply tooltips to inverter scope widgets"""
    scope.btn_pause.setToolTip(get_tooltip("scope_pause"))
    scope.btn_clear.setToolTip(get_tooltip("scope_clear"))
    scope.combo_mode.setToolTip("Switch between voltage, current, and spectrum views")

def apply_tooltips_to_phasor(phasor):
    """Apply tooltips to phasor view widgets"""
    phasor.slider.setToolTip(get_tooltip("phasor_scale"))
    phasor.chk_trail.setToolTip(get_tooltip("phasor_trail"))

def apply_tooltips_to_injector(injector):
    """Apply tooltips to fault injector widgets"""
    # Will be applied to specific buttons when they are created
    pass

def apply_tooltips_to_insights(insights):
    """Apply tooltips to insights panel widgets"""
    if hasattr(insights, 'btn_expand_all'):
        insights.btn_expand_all.setToolTip(get_tooltip("insights_expand"))
        insights.btn_collapse_all.setToolTip(get_tooltip("insights_collapse"))
        insights.btn_clear.setToolTip(get_tooltip("insights_clear"))

def apply_tooltips_to_dashboard(dashboard):
    """Apply tooltips to validation dashboard widgets"""
    dashboard.btn_clear.setToolTip(get_tooltip("validation_clear"))

def apply_all_tooltips(window):
    """Apply comprehensive tooltips to entire application"""
    apply_tooltips_to_main_window(window)
    apply_tooltips_to_scope(window.scope)
    apply_tooltips_to_phasor(window.phasor_view)
    apply_tooltips_to_injector(window.injector)
    apply_tooltips_to_insights(window.insights)
    apply_tooltips_to_dashboard(window.dashboard)
