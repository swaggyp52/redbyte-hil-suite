import numpy as np
from scipy import signal as scipy_signal
from scipy import fft as scipy_fft
import logging

logger = logging.getLogger(__name__)


def apply_moving_average(data, window_size=5):
    """Applies a simple moving average filter."""
    if len(data) < window_size:
        return np.array(data, dtype=float)
    return np.convolve(data, np.ones(window_size) / window_size, mode='valid')


def compute_fft(time_data, signal_data):
    """
    Computes the one-sided FFT of the signal with Hann windowing.

    Args:
        time_data: Time points (seconds).
        signal_data: Signal values.

    Returns:
        tuple: (frequencies, magnitudes)
    """
    if len(time_data) < 2:
        return np.array([]), np.array([])

    dt = np.mean(np.diff(time_data))
    if dt <= 0:
        return np.array([]), np.array([])

    n = len(signal_data)
    sig = np.array(signal_data, dtype=float)

    # Apply Hann window to reduce spectral leakage
    window = np.hanning(n)
    windowed = sig * window

    fft_vals = scipy_fft.rfft(windowed)
    freqs = scipy_fft.rfftfreq(n, d=dt)
    # Normalize: compensate for Hann window coherent gain (~0.5)
    mags = np.abs(fft_vals) / (n * 0.5)

    return freqs, mags


def compute_rms(signal_data):
    """
    Computes the true RMS of a signal buffer.

    Args:
        signal_data: Array-like of instantaneous sample values.

    Returns:
        float: RMS value. Returns 0.0 for empty input.
    """
    sig = np.array(signal_data, dtype=float)
    if sig.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(sig ** 2)))


def compute_thd(signal_data, fundamental_freq=60.0, fs=None, time_data=None, n_harmonics=10):
    """
    Computes Total Harmonic Distortion from a signal buffer.

    Uses FFT to find the fundamental magnitude and harmonic magnitudes,
    then computes THD = sqrt(sum(H_k^2)) / H_1 * 100%.

    Args:
        signal_data: Array-like of instantaneous sample values.
        fundamental_freq: Expected fundamental frequency in Hz.
        fs: Sampling frequency in Hz. If None, estimated from time_data.
        time_data: Time points (used to estimate fs if fs is None).
        n_harmonics: Number of harmonics to include (default 10).

    Returns:
        float: THD as a percentage. Returns 0.0 if unable to compute.
    """
    sig = np.array(signal_data, dtype=float)
    if sig.size < 16:
        return 0.0

    # Determine sampling frequency
    if fs is None:
        if time_data is not None and len(time_data) >= 2:
            dt = np.mean(np.diff(time_data))
            if dt <= 0:
                return 0.0
            fs = 1.0 / dt
        else:
            return 0.0

    n = len(sig)

    # Apply Hann window
    window = np.hanning(n)
    windowed = sig * window
    fft_vals = np.abs(scipy_fft.rfft(windowed))

    freq_resolution = fs / n

    def find_peak_near(target_freq, tolerance_bins=2):
        """Find peak magnitude near a target frequency."""
        target_bin = int(round(target_freq / freq_resolution))
        low = max(0, target_bin - tolerance_bins)
        high = min(len(fft_vals) - 1, target_bin + tolerance_bins)
        if low > high or high >= len(fft_vals):
            return 0.0
        region = fft_vals[low:high + 1]
        return float(np.max(region))

    # Find fundamental
    h1 = find_peak_near(fundamental_freq)
    if h1 < 1e-10:
        return 0.0

    # Find harmonics 2..n_harmonics
    harmonic_sum_sq = 0.0
    for k in range(2, n_harmonics + 1):
        hk_freq = fundamental_freq * k
        if hk_freq >= fs / 2:
            break  # Beyond Nyquist
        hk = find_peak_near(hk_freq)
        harmonic_sum_sq += hk ** 2

    thd = np.sqrt(harmonic_sum_sq) / h1 * 100.0
    return float(thd)


def extract_phasor(signal_data, time_data=None, fs=None, fundamental_freq=60.0):
    """
    Extracts magnitude and phase angle of the fundamental component
    using the Hilbert transform.

    Args:
        signal_data: Array-like of instantaneous sample values.
        time_data: Time points (used to estimate fs if fs is None).
        fs: Sampling frequency in Hz.
        fundamental_freq: Expected fundamental frequency for bandpass.

    Returns:
        dict with magnitude, angle_deg, angle_rad, instantaneous_freq.
        Returns None if insufficient data.
    """
    sig = np.array(signal_data, dtype=float)
    if sig.size < 16:
        return None

    # Determine sampling frequency
    if fs is None:
        if time_data is not None and len(time_data) >= 2:
            dt = np.mean(np.diff(time_data))
            if dt <= 0:
                return None
            fs = 1.0 / dt
        else:
            return None

    # Bandpass filter around fundamental to isolate it
    nyq = fs / 2.0
    bw = max(5.0, fundamental_freq * 0.15)
    low = max(1.0, fundamental_freq - bw) / nyq
    high = min(nyq - 1.0, fundamental_freq + bw) / nyq

    if low >= high or high >= 1.0 or low <= 0.0:
        filtered = sig
    else:
        try:
            sos = scipy_signal.butter(4, [low, high], btype='bandpass', output='sos')
            filtered = scipy_signal.sosfiltfilt(sos, sig)
        except Exception:
            filtered = sig

    # Hilbert transform to get analytic signal
    analytic = scipy_signal.hilbert(filtered)
    envelope = np.abs(analytic)
    inst_phase = np.unwrap(np.angle(analytic))

    # RMS magnitude from envelope
    rms_mag = float(np.mean(envelope) / np.sqrt(2))

    # Phase angle at buffer midpoint
    mid = len(inst_phase) // 2
    angle_rad = float(inst_phase[mid]) % (2 * np.pi)
    angle_deg = float(np.degrees(angle_rad))

    # Instantaneous frequency from phase derivative
    if len(inst_phase) > 1:
        dphase = np.diff(inst_phase)
        dt = 1.0 / fs
        inst_freq = float(np.median(dphase / (2 * np.pi * dt)))
    else:
        inst_freq = fundamental_freq

    return {
        'magnitude': rms_mag,
        'angle_deg': angle_deg,
        'angle_rad': angle_rad,
        'instantaneous_freq': inst_freq,
    }


def extract_three_phase_phasors(v_a_data, v_b_data, v_c_data, time_data=None, fs=None, fundamental_freq=60.0):
    """
    Extracts phasor magnitude and angle for all three phases, plus
    relative angles between them.

    Returns:
        dict with per-phase phasors and relative angles.
        Returns None if any phase extraction fails.
    """
    pa = extract_phasor(v_a_data, time_data, fs, fundamental_freq)
    pb = extract_phasor(v_b_data, time_data, fs, fundamental_freq)
    pc = extract_phasor(v_c_data, time_data, fs, fundamental_freq)

    if pa is None or pb is None or pc is None:
        return None

    # Relative angles (B and C relative to A)
    ab_angle = (pb['angle_deg'] - pa['angle_deg']) % 360
    if ab_angle > 180:
        ab_angle -= 360
    ac_angle = (pc['angle_deg'] - pa['angle_deg']) % 360
    if ac_angle > 180:
        ac_angle -= 360

    # Check balance: ideal is -120 and +120
    balanced = (abs(abs(ab_angle) - 120) < 15) and (abs(abs(ac_angle) - 120) < 15)

    return {
        'a': pa,
        'b': pb,
        'c': pc,
        'ab_angle': float(ab_angle),
        'ac_angle': float(ac_angle),
        'balanced': balanced,
    }


def calculate_step_metrics(time_data, signal_data):
    """
    Calculates step response metrics from a signal buffer.

    Returns:
        dict: {rise_time, overshoot, settling_time, final_value}
    """
    if len(signal_data) < 10:
        return None

    sig = np.array(signal_data, dtype=float)
    t = np.array(time_data, dtype=float)

    n_steady = max(1, len(sig) // 10)
    final_val = np.mean(sig[-n_steady:])
    start_val = np.mean(sig[:n_steady])

    step_height = final_val - start_val
    if abs(step_height) < 1e-3:
        return None

    low_thresh = start_val + 0.1 * step_height
    high_thresh = start_val + 0.9 * step_height

    try:
        if step_height > 0:
            idx_low = np.where(sig >= low_thresh)[0][0]
            idx_high = np.where(sig >= high_thresh)[0][0]
        else:
            idx_low = np.where(sig <= low_thresh)[0][0]
            idx_high = np.where(sig <= high_thresh)[0][0]
        rise_time = abs(t[idx_high] - t[idx_low])
    except IndexError:
        rise_time = 0.0

    peak_val = np.max(sig) if step_height > 0 else np.min(sig)
    overshoot = (peak_val - final_val) / abs(step_height) * 100.0

    # Settling time (within 2% band of final value)
    band = abs(step_height) * 0.02
    settled = np.abs(sig - final_val) <= band
    outside_band = np.where(~settled)[0]
    if len(outside_band) > 0:
        settling_time = float(t[outside_band[-1]] - t[0])
    else:
        settling_time = 0.0

    return {
        'rise_time': float(rise_time),
        'overshoot': float(overshoot),
        'settling_time': settling_time,
        'final_value': float(final_val),
    }


def compute_frequency_from_zero_crossings(signal_data, time_data):
    """
    Estimates frequency from positive-going zero crossings.
    More robust than FFT for short windows.

    Returns:
        float: Estimated frequency in Hz. Returns 0.0 if unable to determine.
    """
    sig = np.array(signal_data, dtype=float)
    t = np.array(time_data, dtype=float)

    if sig.size < 4:
        return 0.0

    crossings = []
    for i in range(len(sig) - 1):
        if sig[i] <= 0 and sig[i + 1] > 0:
            # Linear interpolation for sub-sample accuracy
            denom = sig[i + 1] - sig[i]
            frac = -sig[i] / denom if denom != 0 else 0
            crossing_time = t[i] + frac * (t[i + 1] - t[i])
            crossings.append(crossing_time)

    if len(crossings) < 2:
        return 0.0

    periods = np.diff(crossings)
    if len(periods) == 0:
        return 0.0

    avg_period = float(np.median(periods))
    if avg_period <= 0:
        return 0.0

    return 1.0 / avg_period
