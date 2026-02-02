import numpy as np
import pytest

from src.signal_processing import compute_rms, compute_thd, extract_three_phase_phasors


def _make_sine(freq, fs, duration, amplitude=1.0, phase=0.0):
    t = np.arange(0, duration, 1.0 / fs)
    sig = amplitude * np.sin(2 * np.pi * freq * t + phase)
    return t, sig


def test_compute_rms_sine():
    fs = 2000
    t, sig = _make_sine(60, fs, 0.5, amplitude=2.0)
    rms = compute_rms(sig)
    assert rms == pytest.approx(2.0 / np.sqrt(2), rel=0.05)


def test_compute_thd_known_harmonic():
    fs = 5000
    t, fundamental = _make_sine(60, fs, 0.5, amplitude=1.0)
    _, h5 = _make_sine(300, fs, 0.5, amplitude=0.1)
    sig = fundamental + h5

    thd = compute_thd(sig, fundamental_freq=60.0, time_data=t, n_harmonics=10)
    assert thd == pytest.approx(10.0, rel=0.3)


def test_extract_three_phase_phasors_balanced():
    fs = 2000
    duration = 0.5
    t, va = _make_sine(60, fs, duration, amplitude=1.0, phase=0.0)
    _, vb = _make_sine(60, fs, duration, amplitude=1.0, phase=-2.0944)
    _, vc = _make_sine(60, fs, duration, amplitude=1.0, phase=2.0944)

    result = extract_three_phase_phasors(va, vb, vc, time_data=t, fundamental_freq=60.0)
    assert result is not None
    assert abs(abs(result['ab_angle']) - 120) < 20
    assert abs(abs(result['ac_angle']) - 120) < 20


def test_compute_rms_empty_buffer():
    assert compute_rms([]) == 0.0


def test_compute_thd_empty_buffer():
    assert compute_thd([]) == 0.0


def test_compute_thd_noisy_signal_stability():
    fs = 5000
    t, fundamental = _make_sine(60, fs, 0.5, amplitude=1.0)
    noise = np.random.normal(0, 0.02, size=len(t))
    sig = fundamental + noise

    thd = compute_thd(sig, fundamental_freq=60.0, time_data=t, n_harmonics=10)
    assert thd >= 0.0
