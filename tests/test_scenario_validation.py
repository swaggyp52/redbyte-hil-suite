import pytest
import json
from src.scenario import ScenarioValidator

def test_validation_pass():
    # Session with freq always > 59.5
    session = {
        "frames": [
            {"ts": 0.1, "v": 120, "i": 5, "freq": 60.0},
            {"ts": 0.2, "v": 120, "i": 5, "freq": 59.9},
            {"ts": 0.3, "v": 120, "i": 5, "freq": 60.0}
        ]
    }
    rules = {"frequency_nadir": {"min": 59.5}}
    
    result = ScenarioValidator.validate(session, rules)
    assert result["passed"] is True
    assert "PASS" in result["logs"][0]

def test_validation_fail_voltage():
    # Session with voltage dip < 100
    session = {
        "frames": [
            {"ts": 0.1, "v": 120, "i": 5},
            {"ts": 0.2, "v": 90, "i": 5},
            {"ts": 0.3, "v": 120, "i": 5}
        ]
    }
    rules = {"voltage_sag": {"min": 100.0}}
    
    result = ScenarioValidator.validate(session, rules)
    assert result["passed"] is False
    assert "FAIL" in result["logs"][0]
    assert "90.00V" in result["logs"][0]
