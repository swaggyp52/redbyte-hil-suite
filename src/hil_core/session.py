"""
SessionContext: Singleton state manager for cross-app context sharing
Handles waveform data, configuration, metadata, and app-to-app handoff
"""

import json
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, asdict
from datetime import datetime
import threading


@dataclass
class WaveformSnapshot:
    """Captured waveform data for handoff"""
    timestamp: float
    channels: Dict[str, List[float]]
    sample_rate: float
    duration: float
    metadata: Dict[str, Any]


@dataclass
class ScenarioContext:
    """Current scenario state"""
    name: str
    fault_type: Optional[str]
    parameters: Dict[str, Any]
    start_time: float
    insights: List[Dict[str, Any]]


class SessionContext:
    """
    Global singleton managing HIL session state across all RedByte apps
    
    Provides:
    - Waveform data sharing
    - Configuration persistence
    - Cross-app context export/import
    - Session metadata tracking
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._initialized = True
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.temp_dir = Path("temp")
        self.temp_dir.mkdir(exist_ok=True)
        
        # Core state
        self.waveform: Optional[WaveformSnapshot] = None
        self.scenario: Optional[ScenarioContext] = None
        self.config: Dict[str, Any] = {}
        self.insights: List[Dict[str, Any]] = []
        self.tags: List[Dict[str, Any]] = []
        
        # App tracking
        self.source_app: Optional[str] = None
        self.target_app: Optional[str] = None
        
    def set_waveform(self, channels: Dict[str, List[float]], 
                     sample_rate: float, duration: float,
                     metadata: Optional[Dict[str, Any]] = None):
        """Capture current waveform state"""
        self.waveform = WaveformSnapshot(
            timestamp=datetime.now().timestamp(),
            channels=channels,
            sample_rate=sample_rate,
            duration=duration,
            metadata=metadata or {}
        )
    
    def set_scenario(self, name: str, fault_type: Optional[str] = None,
                     parameters: Optional[Dict[str, Any]] = None,
                     insights: Optional[List[Dict[str, Any]]] = None):
        """Set current scenario context"""
        self.scenario = ScenarioContext(
            name=name,
            fault_type=fault_type,
            parameters=parameters or {},
            start_time=datetime.now().timestamp(),
            insights=insights or []
        )
    
    def add_insight(self, event_type: str, severity: str, 
                    message: str, timestamp: float,
                    metrics: Optional[Dict[str, Any]] = None):
        """Add insight to current session"""
        insight = {
            'type': event_type,
            'severity': severity,
            'message': message,
            'timestamp': timestamp,
            'metrics': metrics or {}
        }
        self.insights.append(insight)
        if self.scenario:
            self.scenario.insights.append(insight)
    
    def add_tag(self, timestamp: float, label: str, 
                color: str = "#3b82f6", notes: str = ""):
        """Add timeline tag for replay"""
        self.tags.append({
            'timestamp': timestamp,
            'label': label,
            'color': color,
            'notes': notes
        })
    
    def export_context(self, target_app: str) -> Path:
        """
        Export current session context to temp file for app handoff
        
        Args:
            target_app: Name of destination app (e.g., 'replay', 'compliance')
        
        Returns:
            Path to exported context file
        """
        self.target_app = target_app
        
        export_data = {
            'session_id': self.session_id,
            'source_app': self.source_app,
            'target_app': target_app,
            'timestamp': datetime.now().isoformat(),
            'waveform': asdict(self.waveform) if self.waveform else None,
            'scenario': asdict(self.scenario) if self.scenario else None,
            'config': self.config,
            'insights': self.insights,
            'tags': self.tags
        }
        
        export_path = self.temp_dir / f"redbyte_session_{target_app}.json"
        with open(export_path, 'w') as f:
            json.dump(export_data, f, indent=2)
        
        return export_path
    
    def import_context(self, source_app: str) -> bool:
        """
        Import session context from temp file
        
        Args:
            source_app: Name of source app (e.g., 'diagnostics')
        
        Returns:
            True if import successful, False otherwise
        """
        import_path = self.temp_dir / f"redbyte_session_{source_app}.json"
        
        if not import_path.exists():
            return False
        
        try:
            with open(import_path, 'r') as f:
                data = json.load(f)
            
            self.session_id = data.get('session_id', self.session_id)
            self.source_app = data.get('source_app')
            
            # Restore waveform
            if data.get('waveform'):
                wf = data['waveform']
                self.waveform = WaveformSnapshot(**wf)
            
            # Restore scenario
            if data.get('scenario'):
                sc = data['scenario']
                self.scenario = ScenarioContext(**sc)
            
            # Restore other state
            self.config = data.get('config', {})
            self.insights = data.get('insights', [])
            self.tags = data.get('tags', [])
            
            return True
        
        except Exception as e:
            print(f"Failed to import context: {e}")
            return False
    
    def clear(self):
        """Reset session state"""
        self.waveform = None
        self.scenario = None
        self.config = {}
        self.insights = []
        self.tags = []
        self.source_app = None
        self.target_app = None
    
    def get_summary(self) -> Dict[str, Any]:
        """Get session summary for display"""
        return {
            'session_id': self.session_id,
            'has_waveform': self.waveform is not None,
            'has_scenario': self.scenario is not None,
            'insight_count': len(self.insights),
            'tag_count': len(self.tags),
            'source_app': self.source_app
        }
