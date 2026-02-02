"""
Deep QA Tests for RedByte HIL Suite
- Context corruption / graceful failure
- Theme regression (each launcher uses correct theme)
- Cross-context round-trip (export -> import -> re-export -> import)
- Insight serialization round-trip
"""
import sys
import os
import json
import math
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))


# ------------------------------------------------------------------ #
# Context corruption tests
# ------------------------------------------------------------------ #

class TestContextCorruption:
    """Verify graceful failure when context files are malformed."""

    def test_import_nonexistent_file(self):
        """import_context returns False for missing file."""
        from hil_core.session import SessionContext
        session = SessionContext()
        assert session.import_context("nonexistent_app_xyz") is False

    def test_import_empty_json(self, tmp_path):
        """import_context handles empty JSON object."""
        from hil_core.session import SessionContext
        session = SessionContext()

        bad_file = session.temp_dir / "redbyte_session_empty_test.json"
        bad_file.parent.mkdir(parents=True, exist_ok=True)
        bad_file.write_text("{}")

        result = session.import_context("empty_test")
        # Should not crash - either returns True with empty data or False
        assert isinstance(result, bool)

    def test_import_invalid_json(self, tmp_path):
        """import_context handles completely invalid JSON."""
        from hil_core.session import SessionContext
        session = SessionContext()

        bad_file = session.temp_dir / "redbyte_session_broken_test.json"
        bad_file.parent.mkdir(parents=True, exist_ok=True)
        bad_file.write_text("NOT VALID JSON {{{")

        result = session.import_context("broken_test")
        assert result is False

    def test_import_partial_context(self):
        """import_context handles JSON with missing keys."""
        from hil_core.session import SessionContext
        session = SessionContext()

        partial = {
            "session_id": "test_partial",
            "source_app": "diagnostics",
            # Missing: waveform, scenario, insights, tags
        }

        partial_file = session.temp_dir / "redbyte_session_partial_test.json"
        partial_file.parent.mkdir(parents=True, exist_ok=True)
        with open(partial_file, 'w') as f:
            json.dump(partial, f)

        result = session.import_context("partial_test")
        assert isinstance(result, bool)


# ------------------------------------------------------------------ #
# Theme regression tests
# ------------------------------------------------------------------ #

class TestThemeRegression:
    """Verify each launcher applies its correct theme."""

    def test_diagnostics_theme(self, qapp):
        from launchers.launch_diagnostics import DiagnosticsWindow
        window = DiagnosticsWindow()
        ss = window.styleSheet()
        # Diagnostics uses emerald green accent
        assert "#10b981" in ss or "10b981" in ss.lower()
        window.close()

    def test_replay_theme(self, qapp):
        from launchers.launch_replay import ReplayWindow
        window = ReplayWindow()
        ss = window.styleSheet()
        # Replay uses cyan accent
        assert "#06b6d4" in ss or "06b6d4" in ss.lower()
        window.close()

    def test_compliance_theme(self, qapp):
        from launchers.launch_compliance import ComplianceWindow
        window = ComplianceWindow()
        ss = window.styleSheet()
        # Compliance uses purple accent
        assert "#8b5cf6" in ss or "8b5cf6" in ss.lower()
        window.close()

    def test_insights_theme(self, qapp):
        from launchers.launch_insights import InsightStudioWindow
        window = InsightStudioWindow()
        ss = window.styleSheet()
        # Insights uses amber accent
        assert "#f59e0b" in ss or "f59e0b" in ss.lower()
        window.close()

    def test_sculptor_theme(self, qapp):
        from launchers.launch_sculptor import SculptorWindow
        window = SculptorWindow()
        ss = window.styleSheet()
        # Sculptor uses orange accent
        assert "#f97316" in ss or "f97316" in ss.lower()
        window.close()


# ------------------------------------------------------------------ #
# Cross-context round-trip
# ------------------------------------------------------------------ #

class TestContextRoundTrip:
    """Verify export -> import preserves data integrity."""

    def test_session_export_import_roundtrip(self):
        """Export a session and re-import it, verify data survives."""
        from hil_core.session import SessionContext

        session = SessionContext()
        session.clear()

        # Set up test data
        channels = {
            "v_an": [120.0 * math.sin(i * 0.1) for i in range(100)],
            "v_bn": [120.0 * math.sin(i * 0.1 - 2.094) for i in range(100)],
            "v_cn": [120.0 * math.sin(i * 0.1 + 2.094) for i in range(100)],
        }
        session.set_waveform(channels, sample_rate=1000, duration=0.1)
        session.set_scenario("Test Scenario", fault_type="sag", parameters={"mag": 0.5})
        session.add_insight("thd", "warning", "THD exceeded 8%", 0.05, {"thd_value": 8.5})
        session.add_tag(0.03, "Fault Start", "#ef4444", "Test tag")

        # Export
        export_path = session.export_context("roundtrip_test")
        assert export_path.exists()

        # Clear and re-import
        session.clear()
        assert session.waveform is None
        assert len(session.insights) == 0

        result = session.import_context("roundtrip_test")
        assert result is True

        # Verify data survived
        assert session.waveform is not None
        assert len(session.waveform.channels) == 3
        assert session.waveform.sample_rate == 1000
        assert session.scenario is not None
        assert session.scenario.name == "Test Scenario"
        assert len(session.insights) >= 1
        assert len(session.tags) >= 1
        assert session.tags[0]["label"] == "Fault Start"

    def test_context_exporter_replay(self):
        """ContextExporter.export_for_replay produces valid file."""
        from hil_core.export_context import ContextExporter

        channels = {"v_an": [1.0, 2.0, 3.0], "v_bn": [4.0, 5.0, 6.0]}
        path = ContextExporter.export_for_replay(
            waveform_channels=channels,
            sample_rate=100,
            scenario_name="Replay Test",
            insights=[{"type": "thd", "severity": "info", "message": "test", "timestamp": 0}],
            tags=[{"timestamp": 0, "label": "start", "color": "#fff", "notes": ""}]
        )
        assert path.exists()

        with open(path, 'r') as f:
            data = json.load(f)
        assert "waveform" in data
        assert "insights" in data
        assert "tags" in data

    def test_context_exporter_compliance(self):
        """ContextExporter.export_for_compliance produces valid file."""
        from hil_core.export_context import ContextExporter

        channels = {"v_an": [1.0, 2.0], "i_a": [0.5, 0.6]}
        path = ContextExporter.export_for_compliance(
            waveform_channels=channels,
            sample_rate=100,
            validation_results={"freq_check": "pass", "voltage_check": "pass"},
            scenario_name="Compliance Test"
        )
        assert path.exists()

        with open(path, 'r') as f:
            data = json.load(f)
        assert "waveform" in data

    def test_context_exporter_insights(self):
        """ContextExporter.export_for_insights produces valid file."""
        from hil_core.export_context import ContextExporter

        insights = [
            {"type": "thd", "severity": "critical", "message": "THD 12%", "timestamp": 1.0},
            {"type": "frequency", "severity": "warning", "message": "Freq drift", "timestamp": 2.0}
        ]
        path = ContextExporter.export_for_insights(insights=insights)
        assert path.exists()

        with open(path, 'r') as f:
            data = json.load(f)
        assert len(data.get("insights", [])) == 2


# ------------------------------------------------------------------ #
# Insight serialization round-trip
# ------------------------------------------------------------------ #

class TestInsightSerialization:
    """Verify Insight dataclass serializes/deserializes correctly."""

    def test_insight_to_dict(self):
        from hil_core.insights import Insight

        insight = Insight(
            timestamp=1.5,
            event_type="thd",
            severity="critical",
            message="THD exceeded 10%",
            metrics={"thd": 10.5},
            phase="A"
        )

        d = insight.to_dict()
        assert d["timestamp"] == 1.5
        assert d["type"] == "thd"  # Note: 'type' not 'event_type'
        assert d["severity"] == "critical"
        assert d["message"] == "THD exceeded 10%"
        assert d["metrics"]["thd"] == 10.5
        assert d["phase"] == "A"

    def test_insight_dict_roundtrip(self):
        """Create Insight -> to_dict -> recreate Insight."""
        from hil_core.insights import Insight

        original = Insight(
            timestamp=2.0,
            event_type="frequency",
            severity="warning",
            message="Frequency undershoot",
            metrics={"frequency": 58.2, "deviation": -1.8},
            phase=None
        )

        d = original.to_dict()

        # Recreate from dict (same pattern launchers use)
        restored = Insight(
            timestamp=d.get("timestamp", 0),
            event_type=d.get("type", "unknown"),
            severity=d.get("severity", "info"),
            message=d.get("message", ""),
            metrics=d.get("metrics", {}),
            phase=d.get("phase")
        )

        assert restored.timestamp == original.timestamp
        assert restored.event_type == original.event_type
        assert restored.severity == original.severity
        assert restored.message == original.message
        assert restored.metrics == original.metrics
        assert restored.phase == original.phase
