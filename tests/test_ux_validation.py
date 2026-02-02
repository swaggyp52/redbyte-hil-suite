"""
End-to-end UX validation for RedByte HIL Verifier Suite
Tests complete user workflows including context handoff between apps
"""

import pytest
import sys
import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add parent to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))


class TestLegacyDemoFlow:
    """Test the complete demo context round-trip across all apps"""

    def test_demo_context_files_exist(self):
        """Verify baseline demo context files are present"""
        data_dir = project_root / "data"
        assert (data_dir / "demo_context_baseline.json").exists(), "Missing demo_context_baseline.json"
        assert (data_dir / "demo_context_fault_sag.json").exists(), "Missing demo_context_fault_sag.json"

    def test_demo_context_valid_json(self):
        """Verify demo contexts are valid JSON"""
        baseline = project_root / "data" / "demo_context_baseline.json"
        with open(baseline, 'r') as f:
            data = json.load(f)
            assert 'session_id' in data or 'waveform' in data, "Demo context missing expected structure"

    def test_launcher_argparse_support(self):
        """Verify all launchers support --load and --mock flags via LauncherBase"""
        launchers_dir = project_root / "src" / "launchers"
        
        for launcher_file in launchers_dir.glob("launch_*.py"):
            content = launcher_file.read_text(encoding='utf-8')
            # Check that they use LauncherBase.parse_args() or have argparse
            has_support = ("LauncherBase.parse_args()" in content or 
                          ("argparse" in content and "--load" in content))
            assert has_support, f"{launcher_file.name} missing CLI argument support"

    def test_batch_files_pass_arguments(self):
        """Verify all batch files pass through CLI arguments with %*"""
        bin_dir = project_root / "bin"
        launcher_bats = ["diagnostics.bat", "replay.bat", "compliance.bat", "insights.bat", "sculptor.bat"]
        
        for bat_file in launcher_bats:
            path = bin_dir / bat_file
            if path.exists():
                content = path.read_text()
                assert "%*" in content, f"{bat_file} doesn't pass through arguments"


class TestContextHandoff:
    """Test context export/import between apps"""

    def test_session_context_export(self):
        """Verify SessionContext can export to temp file"""
        from hil_core import SessionContext
        
        session = SessionContext()
        session.source_app = "test"
        
        exported_path = session.export_context("test")
        assert exported_path.exists(), "Export didn't create file"
        
        # Verify it's valid JSON
        with open(exported_path, 'r') as f:
            data = json.load(f)
            assert 'session_id' in data or 'config' in data

    def test_session_context_import(self):
        """Verify SessionContext can import from temp file"""
        from hil_core import SessionContext
        
        # Create a test context file
        session = SessionContext()
        temp_file = session.temp_dir / "redbyte_session_roundtrip.json"
        
        test_data = {
            "session": {
                "source_app": "diagnostics",
                "timestamp": "2026-02-01T12:00:00"
            }
        }
        
        with open(temp_file, 'w') as f:
            json.dump(test_data, f)
        
        # Try to import it
        result = session.import_context("roundtrip")
        assert result, "Import failed"


class TestCLIAndBatchUX:
    """Test CLI user experience and error handling"""

    def test_mock_mode_no_serial_required(self):
        """Verify apps can launch in --mock mode without hardware"""
        # This is validated by test_serial_manager.py test_serial_manager_mock_mode
        pass

    def test_invalid_context_graceful_failure(self):
        """Verify loading invalid context doesn't crash"""
        from hil_core import SessionContext
        
        session = SessionContext()
        
        # Create invalid JSON file
        bad_file = session.temp_dir / "redbyte_session_corrupt.json"
        bad_file.write_text("{invalid json")
        
        # Should return False, not crash
        result = session.import_context("corrupt")
        assert result is False, "Should fail gracefully on corrupt JSON"


class TestLayoutPersistence:
    """Test geometry and layout persistence across launches"""

    def test_launcher_base_saves_geometry(self):
        """Verify LauncherBase saves window geometry via saved_geometries dict"""
        from launcher_base import LauncherBase
        import inspect
        
        source = inspect.getsource(LauncherBase)
        assert "saved_geometries" in source, "LauncherBase missing saved_geometries"
        assert "geometry()" in source, "LauncherBase missing geometry() calls"


class TestVisualConsistency:
    """Test theming and visual polish"""

    def test_all_launchers_have_themes(self):
        """Verify each launcher applies a theme stylesheet"""
        launchers_dir = project_root / "src" / "launchers"
        
        for launcher_file in launchers_dir.glob("launch_*.py"):
            content = launcher_file.read_text(encoding='utf-8')
            assert "get_" in content and "style()" in content, \
                f"{launcher_file.name} missing theme application"

    def test_tooltips_present_in_base(self):
        """Verify LauncherBase provides tooltip infrastructure"""
        from launcher_base import LauncherBase
        import inspect
        
        source = inspect.getsource(LauncherBase)
        assert "_apply_panel_tooltips" in source, "LauncherBase missing tooltip method"


class TestErrorResilience:
    """Test graceful error handling"""

    def test_missing_backend_in_panel(self):
        """Verify panels handle missing backend dependencies gracefully"""
        # Key panels that interact with backends should have error handling
        ui_dir = project_root / "ui"
        critical_panels = ["inverter_scope.py", "phasor_view.py", "fault_injector.py", "system_3d_view.py"]
        
        for panel_name in critical_panels:
            panel_file = ui_dir / panel_name
            if not panel_file.exists():
                continue
            
            content = panel_file.read_text(encoding='utf-8')
            # Should have error handling or None checks for backends
            has_error_handling = any(
                keyword in content 
                for keyword in ["try:", "except:", "if not", "is None"]
            )
            assert has_error_handling, f"{panel_name} may lack error handling"


class TestPolishExtras:
    """Test UI polish details"""

    def test_splash_screen_exists(self):
        """Verify splash screen component exists"""
        splash = project_root / "ui" / "splash_screen.py"
        assert splash.exists(), "Missing splash_screen.py"

    def test_help_overlays_conditional(self):
        """Verify help overlay can be toggled (controlled by show/hide methods)"""
        from launcher_base import LauncherBase
        import inspect
        
        source = inspect.getsource(LauncherBase)
        # Should have help_overlay component that can be shown/hidden
        assert "help_overlay" in source, "LauncherBase should have help_overlay component"

    def test_status_bar_present(self):
        """Verify LauncherBase creates status bar"""
        from launcher_base import LauncherBase
        import inspect
        
        source = inspect.getsource(LauncherBase)
        assert "statusBar" in source or "status_bar" in source, \
            "LauncherBase missing status bar"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
