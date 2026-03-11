import json

from src.replayer import Replayer


def test_load_file_valid_session(tmp_path):
    session = {
        "meta": {"version": "1.2"},
        "frames": [
            {"ts": 1.0, "v_an": 10.0},
            {"ts": 1.1, "v_an": 11.0},
        ],
        "events": [{"ts": 1.05, "type": "test"}],
    }
    p = tmp_path / "session.json"
    p.write_text(json.dumps(session))

    r = Replayer()
    assert r.load_file(str(p)) is True
    assert r.total_frames == 2
    assert len(r.frames) == 2
    assert len(r.events) == 1
    assert r.mode == "realtime"


def test_load_file_missing_frames_returns_false(tmp_path):
    p = tmp_path / "bad_session.json"
    p.write_text(json.dumps({"meta": {"version": "1.2"}, "events": []}))

    r = Replayer()
    assert r.load_file(str(p)) is False


def test_load_file_without_ts_switches_to_fast_mode(tmp_path):
    session = {
        "meta": {"version": "1.2"},
        "frames": [{"v_an": 10.0}, {"v_an": 11.0}],
        "events": [],
    }
    p = tmp_path / "session_no_ts.json"
    p.write_text(json.dumps(session))

    r = Replayer()
    assert r.load_file(str(p)) is True
    assert r.mode == "fast"
    assert any("missing 'ts'" in msg for msg in r.validation_errors)


def test_load_file_detects_non_monotonic_timestamps(tmp_path):
    session = {
        "meta": {"version": "1.2"},
        "frames": [
            {"ts": 1.0, "v_an": 10.0},
            {"ts": 0.9, "v_an": 11.0},
            {"ts": 1.2, "v_an": 12.0},
        ],
        "events": [],
    }
    p = tmp_path / "session_nonmono.json"
    p.write_text(json.dumps(session))

    r = Replayer()
    assert r.load_file(str(p)) is True
    assert any("Non-monotonic timestamp" in msg for msg in r.validation_errors)
