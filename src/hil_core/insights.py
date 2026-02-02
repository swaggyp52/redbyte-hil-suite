"""
InsightEngine: AI-powered event detection and clustering
Shared insight generation for all RedByte apps
"""

from typing import Dict, List, Any, Optional
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime


@dataclass
class Insight:
    """Individual insight/event"""
    timestamp: float
    event_type: str  # 'unbalance', 'thd', 'frequency', 'transient', etc.
    severity: str    # 'critical', 'warning', 'info'
    message: str
    metrics: Dict[str, float]
    phase: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'timestamp': self.timestamp,
            'type': self.event_type,
            'severity': self.severity,
            'message': self.message,
            'metrics': self.metrics,
            'phase': self.phase
        }


class InsightEngine:
    """
    Centralized insight generation and clustering
    
    Features:
    - Real-time event detection
    - Severity classification
    - Temporal clustering
    - Insight aggregation
    """
    
    def __init__(self):
        self.insights: List[Insight] = []
        self.clusters: Dict[str, List[Insight]] = defaultdict(list)
        
        # Thresholds for detection
        self.thresholds = {
            'thd_critical': 10.0,
            'thd_warning': 5.0,
            'unbalance_critical': 15.0,
            'unbalance_warning': 10.0,
            'frequency_critical': 1.0,
            'frequency_warning': 0.5,
        }
    
    def detect_thd_event(self, thd_value: float, phase: str, timestamp: float) -> Optional[Insight]:
        """Detect THD anomaly"""
        if thd_value > self.thresholds['thd_critical']:
            return Insight(
                timestamp=timestamp,
                event_type='thd',
                severity='critical',
                message=f"Critical THD {thd_value:.1f}% on phase {phase}",
                metrics={'thd': thd_value},
                phase=phase
            )
        elif thd_value > self.thresholds['thd_warning']:
            return Insight(
                timestamp=timestamp,
                event_type='thd',
                severity='warning',
                message=f"Elevated THD {thd_value:.1f}% on phase {phase}",
                metrics={'thd': thd_value},
                phase=phase
            )
        return None
    
    def detect_unbalance_event(self, unbalance: float, timestamp: float) -> Optional[Insight]:
        """Detect phase imbalance"""
        if unbalance > self.thresholds['unbalance_critical']:
            return Insight(
                timestamp=timestamp,
                event_type='unbalance',
                severity='critical',
                message=f"Critical unbalance {unbalance:.1f}°",
                metrics={'unbalance': unbalance}
            )
        elif unbalance > self.thresholds['unbalance_warning']:
            return Insight(
                timestamp=timestamp,
                event_type='unbalance',
                severity='warning',
                message=f"Phase unbalance {unbalance:.1f}°",
                metrics={'unbalance': unbalance}
            )
        return None
    
    def detect_frequency_event(self, frequency: float, timestamp: float) -> Optional[Insight]:
        """Detect frequency deviation"""
        deviation = abs(frequency - 60.0)
        
        if deviation > self.thresholds['frequency_critical']:
            return Insight(
                timestamp=timestamp,
                event_type='frequency',
                severity='critical',
                message=f"Critical frequency drift {frequency:.2f} Hz",
                metrics={'frequency': frequency, 'deviation': deviation}
            )
        elif deviation > self.thresholds['frequency_warning']:
            return Insight(
                timestamp=timestamp,
                event_type='frequency',
                severity='warning',
                message=f"Frequency drift {frequency:.2f} Hz",
                metrics={'frequency': frequency, 'deviation': deviation}
            )
        return None
    
    def add_insight(self, insight: Insight):
        """Add insight and cluster by type"""
        self.insights.append(insight)
        self.clusters[insight.event_type].append(insight)
    
    def get_insights_by_type(self, event_type: str) -> List[Insight]:
        """Get all insights of a specific type"""
        return self.clusters.get(event_type, [])
    
    def get_insights_by_severity(self, severity: str) -> List[Insight]:
        """Get all insights with specific severity"""
        return [i for i in self.insights if i.severity == severity]
    
    def get_recent_insights(self, count: int = 10) -> List[Insight]:
        """Get most recent insights"""
        return self.insights[-count:]
    
    def get_cluster_summary(self) -> Dict[str, int]:
        """Get count of insights by type"""
        return {
            event_type: len(insights)
            for event_type, insights in self.clusters.items()
        }
    
    def get_critical_count(self) -> int:
        """Get count of critical insights"""
        return len(self.get_insights_by_severity('critical'))
    
    def clear(self):
        """Reset all insights"""
        self.insights.clear()
        self.clusters.clear()
    
    def export_insights(self) -> List[Dict[str, Any]]:
        """Export all insights as dict list"""
        return [i.to_dict() for i in self.insights]
