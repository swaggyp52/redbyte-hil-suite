"""
OpenGL capability detection for RedByte HIL Suite
Provides safe checks before attempting to use PyOpenGL/3D features
"""
import logging

logger = logging.getLogger(__name__)

def check_opengl_available():
    """
    Check if OpenGL is available and functional.
    
    Returns:
        tuple: (bool, str) - (is_available, error_message)
    """
    # Step 1: Check if PyOpenGL is installed
    try:
        import OpenGL
    except ImportError:
        return False, "PyOpenGL not installed. Run: pip install PyOpenGL PyOpenGL_accelerate"
    
    # Step 2: Check if pyqtgraph.opengl can import
    try:
        import pyqtgraph.opengl as gl
    except ImportError as e:
        return False, f"pyqtgraph OpenGL module failed to import: {e}"
    
    # Step 3: Try to check OpenGL version (requires context)
    try:
        from OpenGL import GL
        # Note: This may fail if no context exists yet, which is OK at startup
        logger.debug("OpenGL module imported successfully")
        return True, ""
    except Exception as e:
        logger.warning(f"OpenGL available but may have issues: {e}")
        # Still return True - let the actual widget creation fail gracefully
        return True, ""

def check_opengl_context():
    """
    Check if an OpenGL context can be created (more thorough test).
    Only call this after QApplication is created.
    
    Returns:
        tuple: (bool, str) - (is_functional, error_message)
    """
    try:
        from OpenGL import GL
        import pyqtgraph.opengl as gl
        from PyQt6.QtWidgets import QWidget
        
        # Try to create a minimal GLViewWidget
        test_widget = gl.GLViewWidget()
        test_widget.hide()  # Don't actually show it
        
        # Try to get GL version
        try:
            version = GL.glGetString(GL.GL_VERSION)
            if version:
                logger.info(f"OpenGL context functional. Version: {version}")
                test_widget.deleteLater()
                return True, ""
        except:
            pass
        
        test_widget.deleteLater()
        return True, ""  # If we got this far, basic functionality works
        
    except Exception as e:
        error_msg = f"OpenGL context creation failed: {e}"
        logger.error(error_msg)
        return False, error_msg

def get_opengl_fallback_message():
    """
    Get user-friendly message for when OpenGL isn't available.
    
    Returns:
        str: HTML-formatted message to display in UI
    """
    return """
    <div style='padding: 20px; background: rgba(220, 38, 38, 0.1); border: 2px solid #dc2626; border-radius: 8px;'>
        <h3 style='color: #dc2626; margin-top: 0;'>⚠️ 3D View Unavailable</h3>
        <p style='color: #e5e7eb;'><b>OpenGL is not available on this system.</b></p>
        <p style='color: #9ca3af;'>This can happen because:</p>
        <ul style='color: #9ca3af;'>
            <li>PyOpenGL is not installed</li>
            <li>GPU drivers are outdated or missing</li>
            <li>Running in a virtual machine without GPU passthrough</li>
            <li>Remote desktop session with no GPU acceleration</li>
        </ul>
        <p style='color: #e5e7eb;'><b>Quick Fix:</b></p>
        <pre style='background: #1e293b; padding: 10px; border-radius: 4px; color: #34d399;'>pip install PyOpenGL PyOpenGL_accelerate</pre>
        <p style='color: #9ca3af; font-size: 11px; margin-bottom: 0;'>
            The app will continue to work without 3D visualization.
            All other features (waveforms, phasors, diagnostics) remain functional.
        </p>
    </div>
    """
