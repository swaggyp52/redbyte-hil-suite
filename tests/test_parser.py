import pytest
import json
from src.data_parser import parse_telemetry_line

def test_parse_simple_spec_example():
    """Test the example from the PDF: {"freq":60.0,"Vabc":[120,119,121]}"""
    line = '{"freq":60.0,"Vabc":[120,119,121]}'
    data = parse_telemetry_line(line)
    
    assert data['freq'] == 60.0
    assert data['Vabc'] == [120, 119, 121]

def test_parse_extra_fields():
    """Test robustness to extra fields."""
    line = '{"v": 120, "extra": "ignored"}'
    data = parse_telemetry_line(line)
    assert data['v'] == 120
    assert data['extra'] == "ignored"

def test_parse_malformed_completeness():
    """Test that it raises ValueError on incomplete JSON."""
    line = '{"v": 120'
    with pytest.raises(ValueError):
        parse_telemetry_line(line)

def test_parse_empty():
    with pytest.raises(ValueError):
        parse_telemetry_line("")
