"""
SignalEngine: Core signal processing and data management
Shared by all RedByte applications for consistent signal handling
"""

from collections import deque
from typing import Dict, List, Optional, Tuple
import numpy as np


_CHANNEL_ALIASES: Dict[str, str] = {
    "Va": "v_an",
    "Vb": "v_bn",
    "Vc": "v_cn",
    "Ia": "i_a",
    "Ib": "i_b",
    "Ic": "i_c",
}


class SignalEngine:
    """
    Unified signal processing engine for HIL data
    
    Features:
    - Circular buffer management
    - Real-time streaming
    - Signal statistics
    - FFT computation
    """
    
    def __init__(self, buffer_size: int = 10000, sample_rate: float = 10000):
        self.buffer_size = buffer_size
        self.sample_rate = sample_rate
        
        # Signal buffers (circular deques for efficiency)
        # Keys match canonical TelemetryFrame schema: v_an, v_bn, v_cn, i_a, i_b, i_c
        self.buffers: Dict[str, deque] = {
            'v_an': deque(maxlen=buffer_size),
            'v_bn': deque(maxlen=buffer_size),
            'v_cn': deque(maxlen=buffer_size),
            'i_a':  deque(maxlen=buffer_size),
            'i_b':  deque(maxlen=buffer_size),
            'i_c':  deque(maxlen=buffer_size),
        }
        
        self.time_buffer = deque(maxlen=buffer_size)
        self.current_time = 0.0
        
    def push_sample(self, channels: Dict[str, float], timestamp: float):
        """Add new sample to all channel buffers"""
        for ch, value in channels.items():
            canonical = _CHANNEL_ALIASES.get(ch, ch)
            if canonical in self.buffers:
                self.buffers[canonical].append(value)
        self.time_buffer.append(timestamp)
        self.current_time = timestamp
    
    def get_channel_data(self, channel: str, num_samples: Optional[int] = None) -> Tuple[np.ndarray, np.ndarray]:
        """
        Get time and data arrays for a channel
        
        Returns:
            (time_array, data_array)
        """
        canonical = _CHANNEL_ALIASES.get(channel, channel)
        if canonical not in self.buffers:
            return np.array([]), np.array([])
        
        if num_samples:
            data = list(self.buffers[canonical])[-num_samples:]
            time = list(self.time_buffer)[-num_samples:]
        else:
            data = list(self.buffers[canonical])
            time = list(self.time_buffer)
        
        return np.array(time), np.array(data)
    
    def get_rms(self, channel: str, num_samples: Optional[int] = None) -> float:
        """Calculate RMS value for channel"""
        _, data = self.get_channel_data(channel, num_samples)
        if len(data) == 0:
            return 0.0
        return float(np.sqrt(np.mean(data**2)))
    
    def get_peak(self, channel: str, num_samples: Optional[int] = None) -> float:
        """Get peak absolute value for channel"""
        _, data = self.get_channel_data(channel, num_samples)
        if len(data) == 0:
            return 0.0
        return float(np.max(np.abs(data)))
    
    def get_thd(self, channel: str, num_samples: Optional[int] = None) -> float:
        """
        Calculate Total Harmonic Distortion
        
        Returns:
            THD percentage (0-100)
        """
        _, data = self.get_channel_data(channel, num_samples)
        if len(data) < 64:  # Need minimum samples for FFT
            return 0.0
        
        # Compute FFT
        fft = np.fft.rfft(data)
        magnitudes = np.abs(fft)
        
        if len(magnitudes) < 10:
            return 0.0
        
        # Fundamental is typically at index 1 (skip DC)
        fundamental = magnitudes[1]
        
        # Harmonics are indices 2, 3, 4, ...
        harmonics = magnitudes[2:min(10, len(magnitudes))]
        
        if fundamental == 0:
            return 0.0
        
        # THD = sqrt(sum of harmonic powers) / fundamental
        thd = np.sqrt(np.sum(harmonics**2)) / fundamental
        return float(thd * 100)
    
    def get_frequency(self, channel: str, num_samples: Optional[int] = None) -> float:
        """
        Estimate fundamental frequency via FFT peak detection
        
        Returns:
            Frequency in Hz
        """
        _, data = self.get_channel_data(channel, num_samples)
        if len(data) < 64:
            return 60.0  # Default 60 Hz
        
        # Compute FFT
        fft = np.fft.rfft(data)
        freqs = np.fft.rfftfreq(len(data), 1/self.sample_rate)
        magnitudes = np.abs(fft)
        
        # Find peak (skip DC component)
        if len(magnitudes) < 2:
            return 60.0
        
        peak_idx = np.argmax(magnitudes[1:]) + 1
        return float(freqs[peak_idx])
    
    def get_all_channels(self) -> Dict[str, List[float]]:
        """Export all channel data as dict"""
        return {
            ch: list(buf) for ch, buf in self.buffers.items()
        }
    
    def clear(self):
        """Reset all buffers"""
        for buf in self.buffers.values():
            buf.clear()
        self.time_buffer.clear()
        self.current_time = 0.0
