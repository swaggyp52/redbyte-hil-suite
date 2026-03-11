import time

from src.models import make_insight_event, normalize_frame


def test_normalize_frame_canonical_keys_passthrough():
    raw = {
        "ts": 123.45,
        "v_an": 120.0,
        "v_bn": -60.0,
        "v_cn": -60.0,
        "i_a": 10.0,
        "i_b": -5.0,
        "i_c": -5.0,
        "freq": 60.0,
        "p_mech": 5000.0,
    }
    f = normalize_frame(raw)
    assert f["ts"] == 123.45
    assert f["v_an"] == 120.0
    assert f["freq"] == 60.0


def test_normalize_frame_alias_remap_legacy_keys():
    raw = {
        "timestamp": 10.0,
        "Va": 100.0,
        "Vb": 101.0,
        "Vc": 102.0,
        "Ia": 1.0,
        "Ib": 2.0,
        "Ic": 3.0,
        "f": 59.8,
        "p": 4500.0,
    }
    f = normalize_frame(raw)
    assert f["ts"] == 10.0
    assert f["v_an"] == 100.0
    assert f["v_bn"] == 101.0
    assert f["v_cn"] == 102.0
    assert f["i_a"] == 1.0
    assert f["i_b"] == 2.0
    assert f["i_c"] == 3.0
    assert f["freq"] == 59.8
    assert f["p_mech"] == 4500.0


def test_normalize_frame_ts_fallback_when_invalid():
    before = time.time()
    f = normalize_frame({"ts": "bad_value"})
    after = time.time()
    assert before <= f["ts"] <= after


def test_normalize_frame_missing_required_floats_filled_with_zero():
    f = normalize_frame({"ts": 1.0})
    assert f["v_an"] == 0.0
    assert f["v_bn"] == 0.0
    assert f["v_cn"] == 0.0
    assert f["i_a"] == 0.0
    assert f["i_b"] == 0.0
    assert f["i_c"] == 0.0
    assert f["freq"] == 0.0
    assert f["p_mech"] == 0.0


def test_make_insight_event_defaults_and_fields():
    evt = make_insight_event(
        ts=12.3,
        event_type="frequency_drift",
        description="Frequency exceeded nominal",
    )
    assert evt["ts"] == 12.3
    assert evt["type"] == "frequency_drift"
    assert evt["severity"] == "info"
    assert evt["description"] == "Frequency exceeded nominal"
    assert evt["metrics"] == {}
    assert evt["phase"] is None


def test_make_insight_event_invalid_severity_defaults_to_info():
    evt = make_insight_event(
        ts=5.0,
        event_type="voltage_sag",
        description="Phase A sag",
        severity="extreme",  # invalid
    )
    assert evt["severity"] == "info"
