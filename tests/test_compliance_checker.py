import pytest

from compliance_checker import _frames_from_waveform_context, evaluate_ieee_2800


def test_frames_from_waveform_context_uses_min_channel_length_and_metadata():
    session_data = {
        "waveform": {
            "timestamp": 10.0,
            "sample_rate": 50.0,
            "channels": {
                "v_an": [1.0, 2.0, 3.0, 4.0],
                "v_bn": [5.0, 6.0, 7.0, 8.0],
                "v_cn": [9.0, 10.0, 11.0, 12.0],
                "i_a": [0.1, 0.2, 0.3],
                "i_b": [0.4, 0.5, 0.6],
                "i_c": [0.7, 0.8, 0.9],
            },
        },
        "scenario": {"parameters": {"frequency_nominal": 59.9}},
    }

    frames = _frames_from_waveform_context(session_data)

    assert len(frames) == 3
    assert frames[0]["ts"] == pytest.approx(10.0)
    assert frames[1]["ts"] == pytest.approx(10.02)
    assert frames[2]["ts"] == pytest.approx(10.04)
    assert frames[0]["freq"] == pytest.approx(59.9)


def test_frames_from_waveform_context_uses_default_dt_when_sample_rate_not_positive():
    session_data = {
        "waveform": {
            "timestamp": 0.0,
            "sample_rate": 0,
            "channels": {
                "v_an": [1.0, 2.0],
                "v_bn": [1.0, 2.0],
                "v_cn": [1.0, 2.0],
                "i_a": [0.0, 0.0],
                "i_b": [0.0, 0.0],
                "i_c": [0.0, 0.0],
            },
        }
    }

    frames = _frames_from_waveform_context(session_data)

    assert len(frames) == 2
    assert frames[1]["ts"] == pytest.approx(0.01)


def test_evaluate_ieee_2800_uses_average_absolute_phase_magnitude():
    # Signed averaging would produce a negative minimum in this synthetic case.
    # The intended behavior is magnitude-based ride-through evaluation.
    session_data = {
        "waveform": {
            "timestamp": 0.0,
            "sample_rate": 100.0,
            "channels": {
                "v_an": [100.0, -100.0],
                "v_bn": [100.0, -100.0],
                "v_cn": [-50.0, 50.0],
                "i_a": [0.0, 0.0],
                "i_b": [0.0, 0.0],
                "i_c": [0.0, 0.0],
            },
        }
    }

    checks = evaluate_ieee_2800(session_data)
    by_name = {entry["name"]: entry for entry in checks}

    assert by_name["Ride-through 50% sag >=200ms"]["passed"] is True
    assert "Min avg V=83.3" in by_name["Ride-through 50% sag >=200ms"]["details"]
    assert by_name["Frequency within ±0.5Hz"]["passed"] is True


def test_evaluate_ieee_2800_reports_data_unavailable_when_no_frames_present():
    checks = evaluate_ieee_2800({"waveform": {"channels": {}}})

    assert len(checks) == 1
    assert checks[0]["name"] == "Data Availability"
    assert checks[0]["passed"] is False
