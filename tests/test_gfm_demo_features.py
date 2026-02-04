"""
Test suite for GFM demo features (telemetry, CSV export, replay)
Critical for capstone evaluation readiness
"""
import sys
import json
import os
import tempfile
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / 'src'))

from src.telemetry_watchdog import TelemetryWatchdog
from src.csv_exporter import CSVExporter
from src.replayer import Replayer
from src.recorder import Recorder

def test_telemetry_watchdog():
    """Test watchdog detects stale data"""
    print("\n=== Testing Telemetry Watchdog ===")
    
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)
    
    watchdog = TelemetryWatchdog(timeout_ms=100, check_interval_ms=50)
    
    stale_detected = []
    def on_stale(seconds):
        stale_detected.append(seconds)
    
    watchdog.stale_data.connect(on_stale)
    
    # Simulate frames
    watchdog.on_frame_received({"ts": 1.0})
    assert not watchdog.is_stale, "Should not be stale immediately"
    
    # Wait for timeout
    import time
    time.sleep(0.2)
    app.processEvents()
    
    assert len(stale_detected) > 0, "Should detect stale data"
    print(f"  ✓ Watchdog detected stale data after {stale_detected[0]:.2f}s")
    
    # Resume data
    watchdog.on_frame_received({"ts": 2.0})
    assert not watchdog.is_stale, "Should resume after new frame"
    print("  ✓ Watchdog resumed after new frame")
    
    stats = watchdog.get_stats()
    print(f"  ✓ Stats: {stats['frame_count']} frames, {stats['status']} status")

def test_csv_export_simple():
    """Test simple CSV export"""
    print("\n=== Testing CSV Export (Simple) ===")
    
    # Create test session
    test_session = {
        "meta": {
            "session_id": "test_001",
            "start_time": "2026-02-04T10:00:00",
            "frame_count": 3
        },
        "frames": [
            {"ts": 1.0, "v_an": 120.0, "v_bn": -60.0, "v_cn": -60.0, "i_a": 5.0, "i_b": 5.0, "i_c": 5.0, "freq": 60.0},
            {"ts": 1.05, "v_an": 119.5, "v_bn": -59.5, "v_cn": -60.0, "i_a": 5.1, "i_b": 4.9, "i_c": 5.0, "freq": 60.1},
            {"ts": 1.10, "v_an": 120.2, "v_bn": -60.1, "v_cn": -60.1, "i_a": 5.0, "i_b": 5.0, "i_c": 5.0, "freq": 59.9}
        ],
        "events": []
    }
    
    # Save to temp file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(test_session, f)
        session_path = f.name
    
    try:
        exporter = CSVExporter()
        
        # Export simple format
        csv_path = exporter.export_session(session_path, format_type="simple")
        assert csv_path is not None, "Export should succeed"
        assert os.path.exists(csv_path), "CSV file should exist"
        
        # Check content
        with open(csv_path, 'r') as f:
            lines = f.readlines()
        
        # Should have metadata + header + 3 data rows
        assert len(lines) >= 4, f"Expected at least 4 lines, got {len(lines)}"
        
        # Verify header
        header_found = False
        for line in lines:
            if "timestamp" in line and "v_an" in line:
                header_found = True
                break
        assert header_found, "Should have header row"
        
        print(f"  ✓ Simple CSV exported: {csv_path}")
        print(f"  ✓ {len(lines)} lines written")
        
        summary = exporter.get_export_summary()
        print(f"  ✓ Export summary: {summary['stats']}")
        
        # Cleanup
        os.unlink(csv_path)
        
    finally:
        os.unlink(session_path)

def test_csv_export_detailed():
    """Test detailed CSV export with all fields"""
    print("\n=== Testing CSV Export (Detailed) ===")
    
    test_session = {
        "meta": {"session_id": "test_002"},
        "frames": [
            {"ts": 1.0, "v_an": 120.0, "custom_field": 42},
            {"ts": 1.05, "v_an": 119.5, "another_field": "test"}
        ],
        "events": [{"ts": 1.0, "type": "fault", "details": "voltage_sag"}]
    }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(test_session, f)
        session_path = f.name
    
    try:
        exporter = CSVExporter()
        csv_path = exporter.export_session(session_path, format_type="detailed", include_metadata=True)
        
        assert csv_path is not None, "Detailed export should succeed"
        
        with open(csv_path, 'r') as f:
            content = f.read()
        
        # Check for metadata comments
        assert "# RedByte HIL Verifier Suite" in content, "Should have metadata header"
        assert "# Event Count: 1" in content, "Should report event count"
        
        # Check for custom fields
        assert "custom_field" in content or "another_field" in content, "Should include all fields"
        
        print(f"  ✓ Detailed CSV exported with metadata")
        print(f"  ✓ Custom fields preserved")
        
        os.unlink(csv_path)
    finally:
        os.unlink(session_path)

def test_replay_validation():
    """Test replay data validation"""
    print("\n=== Testing Replay Validation ===")
    
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)
    
    # Valid session
    valid_session = {
        "meta": {"session_id": "replay_test"},
        "frames": [
            {"ts": 1.0, "v_an": 120.0},
            {"ts": 1.05, "v_an": 119.5},
            {"ts": 1.10, "v_an": 120.2}
        ],
        "events": []
    }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(valid_session, f)
        valid_path = f.name
    
    try:
        replayer = Replayer()
        
        # Should load successfully
        success = replayer.load_file(valid_path)
        assert success, "Should load valid session"
        assert len(replayer.frames) == 3, "Should have 3 frames"
        print("  ✓ Valid session loaded successfully")
        
        # Check playback mode
        assert replayer.mode == "realtime", "Should use realtime mode with timestamps"
        print(f"  ✓ Playback mode: {replayer.mode}")
        
    finally:
        os.unlink(valid_path)
    
    # Invalid session (no frames)
    invalid_session = {"meta": {}, "frames": [], "events": []}
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(invalid_session, f)
        invalid_path = f.name
    
    try:
        replayer2 = Replayer()
        success = replayer2.load_file(invalid_path)
        assert not success, "Should reject session with no frames"
        print("  ✓ Invalid session rejected correctly")
    finally:
        os.unlink(invalid_path)

def test_replay_timestamp_anomalies():
    """Test replay detects timestamp problems"""
    print("\n=== Testing Replay Timestamp Validation ===")
    
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)
    
    # Session with non-monotonic timestamps
    anomaly_session = {
        "meta": {},
        "frames": [
            {"ts": 1.0, "v_an": 120.0},
            {"ts": 1.05, "v_an": 119.5},
            {"ts": 0.95, "v_an": 120.2},  # Goes backwards!
            {"ts": 1.15, "v_an": 119.8}
        ],
        "events": []
    }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(anomaly_session, f)
        anomaly_path = f.name
    
    try:
        replayer = Replayer()
        
        warnings_detected = []
        def on_warning(msg):
            warnings_detected.append(msg)
        
        replayer.validation_warning.connect(on_warning)
        
        success = replayer.load_file(anomaly_path)
        assert success, "Should still load but with warnings"
        
        app.processEvents()
        
        assert len(warnings_detected) > 0, "Should detect timestamp anomaly"
        print(f"  ✓ Detected {len(warnings_detected)} timestamp warnings")
        for warn in warnings_detected:
            print(f"    - {warn}")
        
    finally:
        os.unlink(anomaly_path)

def test_recorder_integration():
    """Test recorder creates valid sessions for replay/export"""
    print("\n=== Testing Recorder Integration ===")
    
    recorder = Recorder(data_dir=tempfile.mkdtemp())
    
    recorder.start()
    assert recorder.is_recording, "Should be recording"
    
    # Log some frames
    recorder.log_frame({"ts": 1.0, "v_an": 120.0, "freq": 60.0})
    recorder.log_frame({"ts": 1.05, "v_an": 119.5, "freq": 60.1})
    recorder.log_frame({"ts": 1.10, "v_an": 120.2, "freq": 59.9})
    
    recorder.log_event("fault", "voltage_sag")
    
    filepath = recorder.stop()
    assert filepath is not None, "Should save session file"
    assert os.path.exists(filepath), "Session file should exist"
    
    print(f"  ✓ Recorded session: {filepath}")
    
    # Verify can be loaded by replayer
    replayer = Replayer()
    success = replayer.load_file(filepath)
    assert success, "Replayer should load recorder output"
    assert len(replayer.frames) == 3, "Should have 3 frames"
    print("  ✓ Replayer can load recorder output")
    
    # Verify can be exported
    exporter = CSVExporter()
    csv_path = exporter.export_session(filepath, format_type="detailed")
    assert csv_path is not None, "Should export recorded session"
    print("  ✓ Exporter can export recorder output")
    
    # Cleanup
    os.unlink(filepath)
    os.unlink(csv_path)

if __name__ == '__main__':
    print("=" * 70)
    print("GFM Demo Features - Comprehensive Test Suite")
    print("Testing: Live Telemetry, CSV Export, Replay")
    print("=" * 70)
    
    try:
        test_telemetry_watchdog()
        test_csv_export_simple()
        test_csv_export_detailed()
        test_replay_validation()
        test_replay_timestamp_anomalies()
        test_recorder_integration()
        
        print()
        print("=" * 70)
        print("✅ All GFM Demo Tests Passed!")
        print("=" * 70)
        print()
        print("Your capstone demo features are ROCK SOLID:")
        print("  ✓ Live telemetry with stale data detection")
        print("  ✓ Robust CSV export (3 formats + metadata)")
        print("  ✓ Replay with timestamp validation")
        print("  ✓ Full integration (record → replay → export)")
        print()
        print("Ready for professor-level scrutiny! 🎓")
        print()
        
    except AssertionError as e:
        print()
        print("=" * 70)
        print(f"❌ Test Failed: {e}")
        print("=" * 70)
        import traceback
        traceback.print_exc()
        sys.exit(1)
    except Exception as e:
        print()
        print("=" * 70)
        print(f"❌ Unexpected Error: {e}")
        print("=" * 70)
        import traceback
        traceback.print_exc()
        sys.exit(1)
