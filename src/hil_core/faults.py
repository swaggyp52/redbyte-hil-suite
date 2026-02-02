"""
FaultEngine: Fault injection and scenario management
Shared fault logic for Diagnostics and Sculptor apps
"""

from typing import Dict, Any, Optional, Callable
from dataclasses import dataclass
from enum import Enum
import time


class FaultType(Enum):
    """Supported fault injection types"""
    VOLTAGE_SAG = "voltage_sag"
    PHASE_IMBALANCE = "phase_imbalance"
    FREQUENCY_DRIFT = "frequency_drift"
    HARMONIC_INJECTION = "harmonic_injection"
    TRANSIENT_SPIKE = "transient_spike"
    DROPOUT = "dropout"


@dataclass
class FaultParameters:
    """Parameters for fault injection"""
    fault_type: FaultType
    magnitude: float  # 0-100%
    duration: float   # seconds
    affected_phases: list  # ['A', 'B', 'C']
    ramp_time: float = 0.1  # seconds
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'type': self.fault_type.value,
            'magnitude': self.magnitude,
            'duration': self.duration,
            'affected_phases': self.affected_phases,
            'ramp_time': self.ramp_time
        }


class FaultEngine:
    """
    Centralized fault injection engine
    
    Features:
    - Scenario-based fault sequences
    - Real-time fault parameter modulation
    - Fault event callbacks
    """
    
    def __init__(self):
        self.active_fault: Optional[FaultParameters] = None
        self.fault_start_time: Optional[float] = None
        self.callbacks: list[Callable] = []
        
        # Fault history
        self.fault_log = []
    
    def inject_fault(self, params: FaultParameters):
        """
        Begin fault injection
        
        Args:
            params: Fault parameters defining type, magnitude, duration
        """
        self.active_fault = params
        self.fault_start_time = time.time()
        
        # Log fault
        self.fault_log.append({
            'timestamp': self.fault_start_time,
            'params': params.to_dict(),
            'status': 'started'
        })
        
        # Notify callbacks
        for callback in self.callbacks:
            callback('fault_started', params)
    
    def clear_fault(self):
        """Remove active fault"""
        if self.active_fault:
            # Log completion
            self.fault_log.append({
                'timestamp': time.time(),
                'params': self.active_fault.to_dict(),
                'status': 'cleared'
            })
            
            # Notify callbacks
            for callback in self.callbacks:
                callback('fault_cleared', self.active_fault)
            
            self.active_fault = None
            self.fault_start_time = None
    
    def get_fault_progress(self) -> float:
        """
        Get current fault progress as 0-1 value
        
        Returns:
            Progress ratio (0.0 = start, 1.0 = complete)
        """
        if not self.active_fault or not self.fault_start_time:
            return 0.0
        
        elapsed = time.time() - self.fault_start_time
        progress = elapsed / self.active_fault.duration
        return min(1.0, progress)
    
    def should_auto_clear(self) -> bool:
        """Check if fault duration has elapsed"""
        if not self.active_fault:
            return False
        
        return self.get_fault_progress() >= 1.0
    
    def register_callback(self, callback: Callable):
        """Register callback for fault events"""
        self.callbacks.append(callback)
    
    def get_fault_summary(self) -> Dict[str, Any]:
        """Get summary of current fault state"""
        if not self.active_fault:
            return {'active': False}
        
        return {
            'active': True,
            'type': self.active_fault.fault_type.value,
            'magnitude': self.active_fault.magnitude,
            'progress': self.get_fault_progress(),
            'elapsed': time.time() - self.fault_start_time if self.fault_start_time else 0
        }
    
    def get_fault_log(self, limit: Optional[int] = None) -> list:
        """Get fault history"""
        if limit:
            return self.fault_log[-limit:]
        return self.fault_log
