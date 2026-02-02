"""
ContextExporter: Cross-app context export/import utilities
Handles session handoff between RedByte applications
"""

from pathlib import Path
from typing import Dict, Any, Optional
import json
from .session import SessionContext


class ContextExporter:
    """
    Utility for exporting/importing context between apps
    
    Provides convenience methods for common handoff scenarios
    """
    
    @staticmethod
    def export_for_replay(waveform_channels: Dict[str, list],
                          sample_rate: float,
                          scenario_name: str,
                          insights: list,
                          tags: list) -> Path:
        """
        Export context optimized for Replay Studio
        
        Args:
            waveform_channels: Dict of channel data
            sample_rate: Sampling rate in Hz
            scenario_name: Name of current scenario
            insights: List of insight dicts
            tags: List of timeline tags
        
        Returns:
            Path to exported file
        """
        session = SessionContext()
        session.source_app = 'diagnostics'
        
        # Calculate duration
        max_len = max(len(ch) for ch in waveform_channels.values()) if waveform_channels else 0
        duration = max_len / sample_rate if max_len > 0 else 0
        
        session.set_waveform(
            channels=waveform_channels,
            sample_rate=sample_rate,
            duration=duration,
            metadata={'scenario': scenario_name}
        )
        
        session.set_scenario(
            name=scenario_name,
            insights=insights
        )
        
        session.insights = insights
        session.tags = tags
        
        return session.export_context('replay')
    
    @staticmethod
    def export_for_compliance(waveform_channels: Dict[str, list],
                              sample_rate: float,
                              validation_results: Dict[str, Any],
                              scenario_name: str) -> Path:
        """
        Export context optimized for Compliance Lab
        
        Args:
            waveform_channels: Dict of channel data
            sample_rate: Sampling rate in Hz
            validation_results: Validation test results
            scenario_name: Name of scenario
        
        Returns:
            Path to exported file
        """
        session = SessionContext()
        session.source_app = 'diagnostics'
        
        max_len = max(len(ch) for ch in waveform_channels.values()) if waveform_channels else 0
        duration = max_len / sample_rate if max_len > 0 else 0
        
        session.set_waveform(
            channels=waveform_channels,
            sample_rate=sample_rate,
            duration=duration,
            metadata={
                'scenario': scenario_name,
                'validation': validation_results
            }
        )
        
        session.set_scenario(
            name=scenario_name,
            parameters=validation_results
        )
        
        session.config['validation_results'] = validation_results
        
        return session.export_context('compliance')
    
    @staticmethod
    def export_for_insights(insights: list,
                           waveform_channels: Optional[Dict[str, list]] = None,
                           sample_rate: float = 10000,
                           scenario_name: str = "Insight Analysis") -> Path:
        """
        Export context optimized for Insight Studio
        
        Args:
            insights: List of insight dicts
            waveform_channels: Optional waveform data
            sample_rate: Sampling rate
            scenario_name: Scenario name
        
        Returns:
            Path to exported file
        """
        session = SessionContext()
        session.source_app = 'diagnostics'
        
        if waveform_channels:
            max_len = max(len(ch) for ch in waveform_channels.values())
            duration = max_len / sample_rate
            
            session.set_waveform(
                channels=waveform_channels,
                sample_rate=sample_rate,
                duration=duration,
                metadata={'scenario': scenario_name}
            )
        
        session.insights = insights
        session.set_scenario(
            name=scenario_name,
            insights=insights
        )
        
        return session.export_context('insights')
    
    @staticmethod
    def import_from_diagnostics() -> Optional[SessionContext]:
        """
        Import context from Diagnostics app
        
        Returns:
            SessionContext if successful, None otherwise
        """
        session = SessionContext()
        if session.import_context('diagnostics'):
            return session
        return None
    
    @staticmethod
    def quick_export(target_app: str, **kwargs) -> Path:
        """
        Quick export with arbitrary data
        
        Args:
            target_app: Target application name
            **kwargs: Data to include in export
        
        Returns:
            Path to exported file
        """
        session = SessionContext()
        session.config.update(kwargs)
        return session.export_context(target_app)
