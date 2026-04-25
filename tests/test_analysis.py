import pytest
import numpy as np
from src.analysis import AnalysisEngine


def _frames(values, dt=0.01):
    return [{"ts": i * dt, "v": v} for i, v in enumerate(values)]


def test_compare_identical():
    """RMSE should be 0 for identical time-aligned sessions."""
    s1 = {"frames": _frames([100, 101, 102, 103])}
    s2 = {"frames": _frames([100, 101, 102, 103])}

    res = AnalysisEngine.compare_sessions(s1, s2, "v")
    assert res['rmse'] == pytest.approx(0.0, abs=1e-6)
    assert res['max_delta'] == pytest.approx(0.0, abs=1e-6)


def test_compare_offset():
    """Constant offset of 2 → max_delta ≈ 2, rmse ≈ 2."""
    s1 = {"frames": _frames([100, 100, 100, 100])}
    s2 = {"frames": _frames([102, 102, 102, 102])}

    res = AnalysisEngine.compare_sessions(s1, s2, "v")
    assert res['max_delta'] == pytest.approx(2.0, abs=1e-6)
    assert res['rmse'] == pytest.approx(2.0, abs=1e-6)


def test_compare_length_mismatch():
    """Comparison is trimmed to the overlapping time window of the two runs."""
    s1 = {"frames": _frames([1, 1, 1])}                    # spans ts 0..0.02
    s2 = {"frames": _frames([1, 1, 1, 2, 2, 2])}           # spans ts 0..0.05

    res = AnalysisEngine.compare_sessions(s1, s2, "v")
    # Only the overlapping t_rel ∈ [0, 0.02] window is compared, where both are ~1.
    assert res['rmse'] == pytest.approx(0.0, abs=1e-6)
    assert len(res['ref_values']) == len(res['test_values'])
    assert len(res['ref_values']) >= 1
