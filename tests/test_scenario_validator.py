from src.scenario import ScenarioValidator


def test_scenario_validator_passes_basic_rules():
    session_data = {
        "frames": [
            {"ts": 0.0, "v_an": 120.0, "v_bn": 118.0, "v_cn": 122.0, "freq": 60.0},
            {"ts": 0.1, "v_an": 119.0, "v_bn": 117.0, "v_cn": 121.0, "freq": 59.8},
            {"ts": 0.2, "v_an": 121.0, "v_bn": 119.0, "v_cn": 123.0, "freq": 60.1},
        ]
    }
    rules = {
        "frequency_nadir": {"min": 59.5},
        "voltage_sag": {"min": 110.0},
    }

    result = ScenarioValidator.validate(session_data, rules)
    assert result["passed"] is True
    assert result["logs"]


def test_scenario_validator_fails_missing_frames():
    result = ScenarioValidator.validate({"frames": []}, {"frequency_nadir": {"min": 59.5}})
    assert result["passed"] is False
