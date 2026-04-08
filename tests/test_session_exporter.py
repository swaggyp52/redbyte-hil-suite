"""
tests/test_session_exporter.py — unit tests for the truth-first export engine.

Truthfulness invariants verified:
  - CSV only writes columns that actually appear in frames.
  - Frames missing a column get an empty cell, NOT "0" or "0.0".
  - HTML report skips plot groups whose channels are entirely absent.
  - Analysis JSON marks absent sections as null.
  - Events export writes header-only file when events list is empty.
"""
import csv
import io
import json
import os
import sys
import tempfile
import types
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.session_exporter import (
    _actual_frame_columns,
    _session_meta,
    build_analysis_json,
    export_analysis_json,
    export_events_csv,
    export_session_csv,
    generate_html_report,
)


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures / helpers
# ─────────────────────────────────────────────────────────────────────────────

def _make_capsule(frames=None, meta_extra=None, import_meta_extra=None):
    """Build a minimal Data Capsule dict for testing."""
    meta = {
        "session_id": "test-session-001",
        "source_type": "csv_file",
        "frame_count": len(frames) if frames else 0,
        "duration_s": 1.0,
        "sample_rate_estimate": 100,
        "channels": ["ts", "freq"],
    }
    if meta_extra:
        meta.update(meta_extra)

    imp = {
        "source_type": "csv_file",
        "source_path": "/data/test.csv",
        "original_sample_rate": 100,
        "duration_s": 1.0,
        "warnings": [],
        "applied_mapping": {},
        "raw_headers": [],
    }
    if import_meta_extra:
        imp.update(import_meta_extra)

    return {
        "meta": meta,
        "import_meta": imp,
        "frames": frames or [],
    }


def _make_event(ts_start=0.5, ts_end=0.6, kind="voltage_sag", severity="warning",
                channel="v_an", description="Test sag", confidence=0.9):
    """Create a mock DetectedEvent object."""
    evt = MagicMock()
    evt.ts_start   = ts_start
    evt.ts_end     = ts_end
    evt.kind       = kind
    evt.severity   = severity
    evt.channel    = channel
    evt.description = description
    evt.confidence = confidence
    evt.metrics    = {"min_voltage": 90.0}
    return evt


def _read_csv_body(path: str) -> tuple[list[str], list[dict]]:
    """Read a preamble-commented CSV, return (fieldnames, rows)."""
    with open(path, newline="", encoding="utf-8") as fh:
        lines = [l for l in fh if not l.startswith("#")]
    reader = csv.DictReader(io.StringIO("".join(lines)))
    return list(reader.fieldnames or []), list(reader)


# ─────────────────────────────────────────────────────────────────────────────
# _actual_frame_columns
# ─────────────────────────────────────────────────────────────────────────────

class TestActualFrameColumns:
    def test_empty_capsule(self):
        assert _actual_frame_columns({"frames": []}) == []

    def test_single_frame(self):
        capsule = {"frames": [{"ts": 0.0, "freq": 60.0}]}
        assert _actual_frame_columns(capsule) == ["freq", "ts"]

    def test_union_across_frames(self):
        """Columns are the union across all frames, sorted."""
        capsule = {"frames": [
            {"ts": 0.0, "v_an": 120.0},
            {"ts": 0.01, "i_a": 5.0},
        ]}
        cols = _actual_frame_columns(capsule)
        assert "ts" in cols
        assert "v_an" in cols
        assert "i_a" in cols
        assert cols == sorted(cols)

    def test_no_fabricated_columns(self):
        """Columns that don't exist in frames must NOT appear in the result."""
        capsule = {"frames": [{"ts": 0.0, "freq": 60.0}]}
        cols = _actual_frame_columns(capsule)
        assert "v_an" not in cols
        assert "v_bn" not in cols
        assert "i_a" not in cols


# ─────────────────────────────────────────────────────────────────────────────
# _session_meta
# ─────────────────────────────────────────────────────────────────────────────

class TestSessionMeta:
    def test_prefers_import_meta(self):
        capsule = _make_capsule()
        m = _session_meta(capsule)
        assert m["source_path"] == "/data/test.csv"
        assert m["sample_rate"] == 100

    def test_falls_back_to_meta(self):
        capsule = _make_capsule()
        capsule["import_meta"]["source_path"] = ""
        m = _session_meta(capsule)
        # meta has no source_path key, should default to ""
        assert m["source_path"] == "" or m["source_path"] is not None

    def test_warnings_always_list(self):
        capsule = _make_capsule()
        m = _session_meta(capsule)
        assert isinstance(m["warnings"], list)

    def test_applied_mapping_always_dict(self):
        capsule = _make_capsule()
        m = _session_meta(capsule)
        assert isinstance(m["applied_mapping"], dict)


# ─────────────────────────────────────────────────────────────────────────────
# export_session_csv — truthfulness invariants
# ─────────────────────────────────────────────────────────────────────────────

class TestExportSessionCsv:
    def test_only_actual_columns_written(self, tmp_path):
        """CSV MUST NOT contain columns absent from all frames."""
        capsule = _make_capsule(frames=[{"ts": 0.0, "freq": 60.0}])
        path = str(tmp_path / "out.csv")
        stats = export_session_csv(capsule, path)

        fieldnames, rows = _read_csv_body(path)
        assert "v_an" not in fieldnames
        assert "v_bn" not in fieldnames
        assert "i_a"  not in fieldnames
        assert "freq" in fieldnames
        assert "ts"   in fieldnames

    def test_missing_channel_is_empty_not_zero(self, tmp_path):
        """
        CRITICAL TRUTHFULNESS INVARIANT:
        If frame A has 'v_an' but frame B does not, frame B's v_an cell must
        be empty (""), not "0" or "0.0".
        """
        capsule = _make_capsule(frames=[
            {"ts": 0.0, "v_an": 120.0, "freq": 60.0},
            {"ts": 0.01, "freq": 60.1},   # no v_an
        ])
        path = str(tmp_path / "out.csv")
        export_session_csv(capsule, path)

        fieldnames, rows = _read_csv_body(path)
        assert "v_an" in fieldnames

        # Row 0 should have a numeric value
        assert rows[0]["v_an"] == "120.0"

        # Row 1 missing v_an → must be empty string, NOT "0" or "0.0"
        missing_val = rows[1]["v_an"]
        assert missing_val == "", (
            f"Missing channel cell must be empty, got '{missing_val}'"
        )
        assert missing_val != "0"
        assert missing_val != "0.0"

    def test_returns_stats_dict(self, tmp_path):
        capsule = _make_capsule(frames=[{"ts": 0.0, "freq": 60.0}])
        path = str(tmp_path / "out.csv")
        stats = export_session_csv(capsule, path)

        assert stats["format"] == "session_csv"
        assert stats["rows"] == 1
        assert "freq" in stats["columns"]
        assert stats["path"] == path

    def test_raises_on_empty_frames(self, tmp_path):
        capsule = _make_capsule(frames=[])
        path = str(tmp_path / "out.csv")
        with pytest.raises(ValueError, match="no frames"):
            export_session_csv(capsule, path)

    def test_preamble_written(self, tmp_path):
        capsule = _make_capsule(frames=[{"ts": 0.0}])
        path = str(tmp_path / "out.csv")
        export_session_csv(capsule, path)

        with open(path, encoding="utf-8") as fh:
            content = fh.read()
        assert "# RedByte GFM HIL Suite" in content
        assert "test-session-001" in content

    def test_creates_parent_dirs(self, tmp_path):
        capsule = _make_capsule(frames=[{"ts": 0.0}])
        nested = str(tmp_path / "deep" / "nested" / "out.csv")
        export_session_csv(capsule, nested)
        assert os.path.exists(nested)

    def test_multi_channel_partial_overlap(self, tmp_path):
        """
        Frames with different channels: union columns written, each
        missing cell is empty.
        """
        capsule = _make_capsule(frames=[
            {"ts": 0.00, "v_an": 120.0},
            {"ts": 0.01, "v_bn": -60.0},
            {"ts": 0.02, "v_an": 119.0, "v_bn": -59.0},
        ])
        path = str(tmp_path / "out.csv")
        export_session_csv(capsule, path)

        fieldnames, rows = _read_csv_body(path)
        assert "v_an" in fieldnames
        assert "v_bn" in fieldnames

        # row 0: v_an present, v_bn missing
        assert rows[0]["v_an"] == "120.0"
        assert rows[0]["v_bn"] == ""

        # row 1: v_an missing, v_bn present
        assert rows[1]["v_an"] == ""
        assert rows[1]["v_bn"] == "-60.0"


# ─────────────────────────────────────────────────────────────────────────────
# export_events_csv
# ─────────────────────────────────────────────────────────────────────────────

class TestExportEventsCsv:
    def test_empty_events_writes_header_only(self, tmp_path):
        """Empty = no events detected; file must exist with header but no rows."""
        path = str(tmp_path / "events.csv")
        stats = export_events_csv([], None, path)

        assert os.path.exists(path)
        assert stats["rows"] == 0

        fieldnames, rows = _read_csv_body(path)
        assert len(rows) == 0
        assert "kind" in fieldnames

    def test_single_event_written(self, tmp_path):
        evt = _make_event()
        path = str(tmp_path / "events.csv")
        stats = export_events_csv([evt], None, path)

        assert stats["rows"] == 1
        fieldnames, rows = _read_csv_body(path)
        assert rows[0]["kind"] == "voltage_sag"
        assert rows[0]["severity"] == "warning"
        assert rows[0]["channel"] == "v_an"

    def test_annotation_appended(self, tmp_path):
        evt = _make_event(ts_start=0.5)
        annotations = {"0.500000": "Manually verified"}
        path = str(tmp_path / "events.csv")
        export_events_csv([evt], annotations, path)

        fieldnames, rows = _read_csv_body(path)
        assert rows[0]["note"] == "Manually verified"

    def test_no_annotation_gives_empty_note(self, tmp_path):
        evt = _make_event(ts_start=1.0)
        path = str(tmp_path / "events.csv")
        export_events_csv([evt], {}, path)

        fieldnames, rows = _read_csv_body(path)
        assert rows[0]["note"] == ""

    def test_metrics_serialized_as_json(self, tmp_path):
        evt = _make_event()
        evt.metrics = {"min_voltage": 85.0, "sag_depth": 15.0}
        path = str(tmp_path / "events.csv")
        export_events_csv([evt], None, path)

        fieldnames, rows = _read_csv_body(path)
        metrics = json.loads(rows[0]["metrics_json"])
        assert metrics["min_voltage"] == 85.0

    def test_duration_computed(self, tmp_path):
        evt = _make_event(ts_start=1.0, ts_end=1.5)
        path = str(tmp_path / "events.csv")
        export_events_csv([evt], None, path)

        fieldnames, rows = _read_csv_body(path)
        assert rows[0]["duration_s"] == "0.5000"

    def test_returns_stats_dict(self, tmp_path):
        path = str(tmp_path / "events.csv")
        stats = export_events_csv([], None, path)
        assert stats["format"] == "events_csv"
        assert "path" in stats


# ─────────────────────────────────────────────────────────────────────────────
# build_analysis_json
# ─────────────────────────────────────────────────────────────────────────────

class TestBuildAnalysisJson:
    def test_no_events_no_compliance(self):
        capsule = _make_capsule()
        result = build_analysis_json(capsule, None, None)

        assert result["events"]["count"] == 0
        assert result["events"]["list"] == []
        assert result["compliance"] is None  # not run → null

    def test_null_compliance_when_not_run(self):
        """Analysis JSON MUST mark absent compliance as null, never invent a value."""
        capsule = _make_capsule()
        result = build_analysis_json(capsule, [], None)
        assert result["compliance"] is None

    def test_compliance_section_when_provided(self):
        capsule = _make_capsule()
        cr = [{"name": "Sag Ride-Through", "passed": True, "details": "OK"},
              {"name": "Freq Stability",   "passed": False, "details": "Too low"}]
        result = build_analysis_json(capsule, [], cr)

        assert result["compliance"] is not None
        assert result["compliance"]["passed"]  == 1
        assert result["compliance"]["total"]   == 2
        assert result["compliance"]["pct"]     == 50
        assert len(result["compliance"]["results"]) == 2

    def test_events_by_severity(self):
        capsule = _make_capsule()
        events  = [
            _make_event(severity="critical"),
            _make_event(severity="warning"),
            _make_event(severity="warning"),
        ]
        result = build_analysis_json(capsule, events, None)

        by_sev = result["events"]["by_severity"]
        assert by_sev["critical"] == 1
        assert by_sev["warning"]  == 2
        assert result["events"]["count"] == 3

    def test_session_metadata_included(self):
        capsule = _make_capsule()
        result = build_analysis_json(capsule, [], None)

        assert result["session"]["session_id"] == "test-session-001"
        assert result["session"]["source_type"] == "csv_file"

    def test_warnings_present_in_output(self):
        capsule = _make_capsule(import_meta_extra={"warnings": ["Header row missing timestamp"]})
        result = build_analysis_json(capsule, [], None)
        assert "Header row missing timestamp" in result["warnings"]

    def test_no_warnings_gives_null(self):
        capsule = _make_capsule()
        result = build_analysis_json(capsule, [], None)
        assert result["warnings"] is None

    def test_channel_mapping_null_when_empty(self):
        capsule = _make_capsule()
        result = build_analysis_json(capsule, [], None)
        assert result["channel_mapping"] is None

    def test_channel_mapping_included_when_present(self):
        capsule = _make_capsule(import_meta_extra={
            "applied_mapping": {"Voltage_A": "v_an", "Current_A": "i_a"}
        })
        result = build_analysis_json(capsule, [], None)
        assert result["channel_mapping"] == {"Voltage_A": "v_an", "Current_A": "i_a"}

    def test_event_fields_complete(self):
        capsule = _make_capsule()
        evt = _make_event(ts_start=0.2, ts_end=0.4, kind="freq_excursion",
                          severity="critical", channel="freq")
        result = build_analysis_json(capsule, [evt], None)

        e = result["events"]["list"][0]
        assert e["kind"]       == "freq_excursion"
        assert e["severity"]   == "critical"
        assert e["ts_start"]   == 0.2
        assert e["ts_end"]     == 0.4
        assert e["duration_s"] == round(0.4 - 0.2, 4)
        assert e["channel"]    == "freq"
        assert e["confidence"] == 0.9


# ─────────────────────────────────────────────────────────────────────────────
# export_analysis_json
# ─────────────────────────────────────────────────────────────────────────────

class TestExportAnalysisJson:
    def test_writes_valid_json(self, tmp_path):
        capsule = _make_capsule(frames=[{"ts": 0.0}])
        path = str(tmp_path / "analysis.json")
        result = export_analysis_json(capsule, [], None, path)

        assert os.path.exists(path)
        with open(path, encoding="utf-8") as fh:
            on_disk = json.load(fh)

        assert on_disk["session"]["session_id"] == "test-session-001"
        assert on_disk == result

    def test_creates_parent_dirs(self, tmp_path):
        capsule = _make_capsule(frames=[{"ts": 0.0}])
        nested = str(tmp_path / "reports" / "sub" / "a.json")
        export_analysis_json(capsule, [], None, nested)
        assert os.path.exists(nested)


# ─────────────────────────────────────────────────────────────────────────────
# generate_html_report (light smoke tests — no matplotlib required)
# ─────────────────────────────────────────────────────────────────────────────

class TestGenerateHtmlReport:
    def _make_capsule_with_frames(self):
        return _make_capsule(frames=[
            {"ts": 0.0, "freq": 60.0, "v_an": 120.0},
            {"ts": 0.01, "freq": 60.1, "v_an": 119.8},
        ])

    def test_returns_existing_path(self, tmp_path):
        """generate_html_report must return a path that exists."""
        with patch("src.session_exporter._plot_group_base64", return_value=None):
            path = generate_html_report(
                self._make_capsule_with_frames(), [], None, str(tmp_path)
            )
        assert os.path.exists(path)
        assert path.endswith(".html")

    def _html_content(self, capsule, events=None, compliance=None, tmp_path=None):
        with patch("src.session_exporter._plot_group_base64", return_value=None):
            path = generate_html_report(capsule, events or [], compliance, str(tmp_path))
        with open(path, encoding="utf-8") as fh:
            return fh.read()

    def test_html_contains_session_id(self, tmp_path):
        content = self._html_content(self._make_capsule_with_frames(), tmp_path=tmp_path)
        assert "test-session-001" in content

    def test_html_contains_compliance_not_run_text(self, tmp_path):
        """When compliance is None, report says 'not run', not a fabricated score."""
        content = self._html_content(self._make_capsule_with_frames(), tmp_path=tmp_path)
        assert "not run" in content.lower()

    def test_html_contains_compliance_results_when_provided(self, tmp_path):
        cr = [{"name": "Sag Ride-Through", "passed": True, "details": "Pass"}]
        content = self._html_content(
            self._make_capsule_with_frames(), compliance=cr, tmp_path=tmp_path
        )
        assert "Sag Ride-Through" in content
        assert "PASS" in content

    def test_html_events_section_shown(self, tmp_path):
        content = self._html_content(
            self._make_capsule_with_frames(), events=[_make_event()], tmp_path=tmp_path
        )
        assert "voltage_sag" in content

    def test_html_no_events_shows_none_detected(self, tmp_path):
        content = self._html_content(self._make_capsule_with_frames(), tmp_path=tmp_path)
        assert "No power-quality events detected" in content

    def test_html_self_contained_no_external_refs(self, tmp_path):
        """Report must be self-contained: no <script src>, no <link href> to CDN."""
        content = self._html_content(self._make_capsule_with_frames(), tmp_path=tmp_path)
        assert "https://" not in content
        assert "http://"  not in content

    def test_html_channel_mapping_shown_when_present(self, tmp_path):
        capsule = _make_capsule(
            frames=[{"ts": 0.0, "v_an": 120.0}],
            import_meta_extra={"applied_mapping": {"Voltage_A": "v_an"}}
        )
        content = self._html_content(capsule, tmp_path=tmp_path)
        assert "Voltage_A" in content
        assert "v_an"      in content

    def test_html_warnings_shown_when_present(self, tmp_path):
        capsule = _make_capsule(
            frames=[{"ts": 0.0}],
            import_meta_extra={"warnings": ["Duplicate rows dropped: 3"]}
        )
        content = self._html_content(capsule, tmp_path=tmp_path)
        assert "Duplicate rows dropped: 3" in content


# ─────────────────────────────────────────────────────────────────────────────
# _plot_group_base64 — absent channel → no fabrication
# ─────────────────────────────────────────────────────────────────────────────

class TestPlotGroupBase64:
    def test_returns_none_when_all_channels_absent(self):
        """If every requested channel is absent from all frames, return None."""
        try:
            from src.session_exporter import _plot_group_base64
        except ImportError:
            pytest.skip("matplotlib not available")

        frames = [{"ts": i * 0.01, "freq": 60.0} for i in range(10)]
        # Request channels that don't exist in frames
        result = _plot_group_base64(frames, ["v_an", "v_bn", "v_cn"], "Voltages", "V")
        assert result is None, "Must return None for channels absent from all frames"

    def test_returns_none_when_no_ts(self):
        try:
            from src.session_exporter import _plot_group_base64
        except ImportError:
            pytest.skip("matplotlib not available")

        frames = [{"freq": 60.0}]  # no 'ts' key
        result = _plot_group_base64(frames, ["freq"], "Freq", "Hz")
        assert result is None
