def apply_diagnostics_matrix(window, respect_user_positions=True, saved_geometries=None, user_moved=None):
    """
    Diagnostics Matrix layout preset - High-density cockpit-style interface
    
    Layout:
    ┌─────────────────────┬──────────┬──────────┐
    │                     │ Insights │  Phasor  │
    │      3D System      │  Panel   │ Diagram  │
    │                     ├──────────┴──────────┤
    │                     │    Dashboard        │
    ├─────────────────────┼─────────────────────┤
    │   Inverter Scope    │  Fault Injector     │
    │                     │  + Replay Studio    │
    └─────────────────────┴─────────────────────┘
    
    Args:
        window: MainWindow instance
        respect_user_positions: If True, don't reposition manually moved panels
        saved_geometries: Dict of saved panel geometries
        user_moved: Set of panel titles that were manually moved
    """
    saved_geometries = saved_geometries or {}
    user_moved = user_moved or set()
    
    w_base = 370
    h_base = 260
    
    # Helper to apply geometry conditionally
    def apply_if_not_moved(widget, x, y, w, h):
        sub = widget.parent()
        if not sub:
            return
        title = sub.windowTitle()
        
        if respect_user_positions and title in user_moved and title in saved_geometries:
            # Restore user's saved position
            sub.setGeometry(saved_geometries[title])
        else:
            # Apply preset geometry
            sub.setGeometry(x, y, w, h)
    
    # Left column - Primary 3D visualization (largest panel for situational awareness)
    apply_if_not_moved(window.view_3d, 0, 0, w_base * 2, h_base * 2)
    
    # Right top - Insights panel (critical alerts and intelligence)
    apply_if_not_moved(window.insights, w_base * 2, 0, w_base, h_base)
    
    # Right top - Phasor diagram (phase relationships)
    apply_if_not_moved(window.phasor_view, w_base * 2 + w_base, 0, w_base, h_base)
    
    # Right middle - Validation dashboard (compliance and metrics)
    apply_if_not_moved(window.dashboard, w_base * 2, h_base, w_base * 2, h_base)
    
    # Bottom left - Live scope (waveform monitoring)
    apply_if_not_moved(window.scope, 0, h_base * 2, w_base * 2, h_base * 1.5)
    
    # Bottom right top - Fault injector (control interface)
    apply_if_not_moved(window.injector, w_base * 2, h_base * 2, w_base * 2, h_base * 0.7)
    
    # Bottom right bottom - Replay studio (playback and analysis)
    apply_if_not_moved(window.replay_studio, w_base * 2, h_base * 2 + h_base * 0.7, w_base * 2, h_base * 0.8)
