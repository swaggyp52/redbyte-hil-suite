import pytest
import numpy as np
from src.analysis import AnalysisEngine

def test_compare_identical():
    """RMSE should be 0 for identical sessions."""
    s1 = {"frames": [{"v": 100}, {"v": 101}]}
    s2 = {"frames": [{"v": 100}, {"v": 101}]}
    
    res = AnalysisEngine.compare_sessions(s1, s2, "v")
    assert res['rmse'] == 0.0
    assert res['max_delta'] == 0.0

def test_compare_offset():
    """RMSE should be calculated correctly."""
    s1 = {"frames": [{"v": 100}, {"v": 100}]}
    s2 = {"frames": [{"v": 102}, {"v": 102}]} # Offset by 2
    
    res = AnalysisEngine.compare_sessions(s1, s2, "v")
    assert res['max_delta'] == 2.0
    assert np.isclose(res['rmse'], 2.0)

def test_compare_length_mismatch():
    """Should truncate to shorter."""
    s1 = {"frames": [{"v": 1}]}
    s2 = {"frames": [{"v": 1}, {"v": 2}]}
    
    res = AnalysisEngine.compare_sessions(s1, s2, "v")
    assert len(res['ref_values']) == 1
    assert res['rmse'] == 0.0
