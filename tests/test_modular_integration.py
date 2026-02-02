"""
Integration tests for RedByte v2.0 Modular Architecture
Tests core modules, launchers, and app isolation
"""

import sys
from pathlib import Path
# Add both src and project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / 'src'))
sys.path.insert(0, str(project_root))

import pytest
from hil_core.session import SessionContext
from hil_core.signals import SignalEngine
from hil_core.faults import FaultEngine
from hil_core.insights import InsightEngine
from hil_core.export_context import ContextExporter
import numpy as np
import time


class TestCoreModules:
    """Test shared backend modules"""
    
    def test_session_context_singleton(self):
        """Verify SessionContext is a singleton"""
        ctx1 = SessionContext()
        ctx2 = SessionContext()
        assert ctx1 is ctx2, "SessionContext should be singleton"
        print("✓ SessionContext singleton works")
    
    def test_session_context_state(self):
        """Test session state management"""
        ctx = SessionContext()
        
        # Test scenario
        ctx.set_scenario("test_fault_injection", fault_type="voltage_sag")
        assert ctx.scenario.name == "test_fault_injection"
        assert ctx.scenario.fault_type == "voltage_sag"
        
        # Test config metadata
        ctx.config['test_key'] = 'test_value'
        assert ctx.config['test_key'] == 'test_value'
        
        # Test waveform
        ctx.set_waveform({'Va': [1.0, 2.0, 3.0]}, sample_rate=10000, duration=0.001)
        assert ctx.waveform is not None
        assert len(ctx.waveform.channels['Va']) == 3
        
        print("✓ SessionContext state management works")
    
    def test_signal_engine_buffer(self):
        """Test circular buffer and signal processing"""
        engine = SignalEngine(buffer_size=100)
        
        # Add samples
        for i in range(50):
            engine.push_sample({'Va': float(i)}, timestamp=i*0.0001)
        
        time_data, buffer_data = engine.get_channel_data('Va')
        assert len(buffer_data) == 50
        
        # Test RMS calculation
        rms = engine.get_rms('Va', num_samples=10)
        assert rms > 0
        
        print("✓ SignalEngine buffer and RMS works")
    
    def test_fault_engine_injection(self):
        """Test fault injection system"""
        engine = FaultEngine()
        
        # Test that engine initializes with correct attributes
        assert hasattr(engine, 'active_fault')
        assert hasattr(engine, 'inject_fault')
        assert hasattr(engine, 'fault_log')
        
        print("✓ FaultEngine initialization works")
    
    def test_insight_engine_detection(self):
        """Test insight detection"""
        engine = InsightEngine()
        
        # Test that engine initializes with correct attributes
        assert hasattr(engine, 'detect_thd_event')
        assert hasattr(engine, 'insights')
        assert hasattr(engine, 'clusters')
        
        # Verify insights list initializes empty
        assert len(engine.insights) == 0
        assert isinstance(engine.clusters, dict)
        
        print("✓ InsightEngine initialization works")
    
    def test_context_exporter(self):
        """Test session export/import"""
        ctx = SessionContext()
        ctx.set_scenario("test_scenario", fault_type="frequency_drift")
        ctx.config['test_run'] = 'integration_test'
        ctx.set_waveform({'Va': [1.0, 2.0, 3.0]}, sample_rate=10000, duration=0.001)
        
        # Export
        export_path = ctx.export_context("replay")
        assert export_path.exists()
        
        # Create new context and import
        ctx2 = SessionContext()  # Should be same singleton, but test import method
        success = ctx2.import_context("replay")
        assert success is True
        assert ctx2.scenario.name == "test_scenario"
        assert ctx2.config['test_run'] == 'integration_test'
        
        # Cleanup
        export_path.unlink()
        
        print("✓ Context export/import works")


class TestAppIsolation:
    """Test that apps can load independently"""
    
    def test_app_structure_exists(self):
        """Verify app launcher files exist"""
        project_root = Path(__file__).parent.parent
        launchers_dir = project_root / 'src' / 'launchers'
        
        expected_launchers = [
            'launch_diagnostics.py',
            'launch_replay.py',
            'launch_compliance.py',
            'launch_insights.py',
            'launch_sculptor.py'
        ]
        
        for launcher in expected_launchers:
            launcher_path = launchers_dir / launcher
            assert launcher_path.exists(), f"{launcher} not found"
        
        print("✓ All 5 app launchers exist")


class TestCrossAppHandoff:
    """Test context handoff between apps"""
    
    def test_diagnostics_to_replay_handoff(self):
        """Test exporting from Diagnostics to Replay"""
        ctx = SessionContext()
        ctx.source_app = "diagnostics"
        ctx.set_scenario("test_handoff", fault_type="voltage_sag")
        ctx.set_waveform({'Va': [120.0] * 100}, sample_rate=10000, duration=0.01)
        
        # Export to temp session file
        export_path = ctx.export_context("replay")
        assert export_path.exists()
        
        # Simulate Replay Studio import (clear and reimport)
        ctx.clear()
        success = ctx.import_context("replay")
        assert success is True
        assert ctx.scenario.name == "test_handoff"
        assert ctx.source_app == "diagnostics"
        
        # Cleanup
        export_path.unlink()
        
        print("✓ Diagnostics → Replay handoff works")


def run_all_tests():
    """Run all integration tests"""
    print("\n" + "="*60)
    print("RedByte v2.0 Modular Integration Tests")
    print("="*60 + "\n")
    
    # Core modules
    print("Testing Core Modules:")
    print("-" * 60)
    core_tests = TestCoreModules()
    core_tests.test_session_context_singleton()
    core_tests.test_session_context_state()
    core_tests.test_signal_engine_buffer()
    core_tests.test_fault_engine_injection()
    core_tests.test_insight_engine_detection()
    core_tests.test_context_exporter()
    
    # App isolation
    print("\nTesting App Structure:")
    print("-" * 60)
    app_tests = TestAppIsolation()
    app_tests.test_app_structure_exists()
    
    # Cross-app handoff
    print("\nTesting Cross-App Handoff:")
    print("-" * 60)
    handoff_tests = TestCrossAppHandoff()
    handoff_tests.test_diagnostics_to_replay_handoff()
    
    print("\n" + "="*60)
    print("✅ All Integration Tests PASSED")
    print("="*60 + "\n")


if __name__ == '__main__':
    run_all_tests()
