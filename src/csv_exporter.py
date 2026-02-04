"""
Robust CSV Export with validation and metadata
Designed for GFM senior design capstone evaluation
"""
import csv
import json
import os
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Any

logger = logging.getLogger(__name__)

class CSVExporter:
    """
    Export telemetry data to CSV with validation and rich metadata.
    
    Features:
    - Validates data integrity before export
    - Includes metadata header for traceability
    - Handles missing fields gracefully
    - Provides export summary/statistics
    - Supports multiple export formats (simple, detailed, analysis-ready)
    """
    
    def __init__(self):
        self.last_export_path = None
        self.last_export_stats = None
    
    def export_session(
        self,
        session_path: str,
        output_path: Optional[str] = None,
        format_type: str = "detailed",
        include_metadata: bool = True
    ) -> Optional[str]:
        """
        Export a session JSON to CSV format.
        
        Args:
            session_path: Path to session JSON file
            output_path: Output CSV path (auto-generated if None)
            format_type: "simple", "detailed", or "analysis"
            include_metadata: Whether to include metadata header
        
        Returns:
            Path to exported CSV, or None on failure
        """
        try:
            # Load session data
            with open(session_path, 'r') as f:
                session_data = json.load(f)
            
            # Validate session structure
            if not self._validate_session(session_data):
                logger.error(f"Session validation failed: {session_path}")
                return None
            
            # Auto-generate output path if not provided
            if output_path is None:
                session_id = session_data.get("meta", {}).get("session_id", "unknown")
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_path = f"exports/session_{session_id}_{timestamp}.csv"
            
            # Ensure output directory exists
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # Export based on format type
            if format_type == "simple":
                success = self._export_simple(session_data, output_path, include_metadata)
            elif format_type == "detailed":
                success = self._export_detailed(session_data, output_path, include_metadata)
            elif format_type == "analysis":
                success = self._export_analysis(session_data, output_path, include_metadata)
            else:
                logger.error(f"Unknown format type: {format_type}")
                return None
            
            if success:
                self.last_export_path = output_path
                logger.info(f"CSV export successful: {output_path}")
                return output_path
            else:
                return None
                
        except Exception as e:
            logger.error(f"CSV export failed: {e}")
            return None
    
    def _validate_session(self, session_data: Dict) -> bool:
        """Validate session data structure"""
        if "frames" not in session_data:
            logger.error("Session missing 'frames' field")
            return False
        
        frames = session_data["frames"]
        if not isinstance(frames, list) or len(frames) == 0:
            logger.error("Session has no frames")
            return False
        
        # Check first frame has required fields
        first_frame = frames[0]
        required_fields = ["ts"]  # Timestamp is critical
        for field in required_fields:
            if field not in first_frame:
                logger.error(f"Frame missing required field: {field}")
                return False
        
        logger.debug(f"Session validation passed ({len(frames)} frames)")
        return True
    
    def _export_simple(self, session_data: Dict, output_path: str, include_metadata: bool) -> bool:
        """Export minimal CSV with just core telemetry"""
        try:
            frames = session_data["frames"]
            
            with open(output_path, 'w', newline='') as csvfile:
                if include_metadata:
                    self._write_metadata_header(csvfile, session_data, "simple")
                
                writer = csv.writer(csvfile)
                
                # Header row
                writer.writerow(["timestamp", "v_an", "v_bn", "v_cn", "i_a", "i_b", "i_c", "freq"])
                
                # Data rows
                for frame in frames:
                    writer.writerow([
                        frame.get("ts", 0.0),
                        frame.get("v_an", 0.0),
                        frame.get("v_bn", 0.0),
                        frame.get("v_cn", 0.0),
                        frame.get("i_a", 0.0),
                        frame.get("i_b", 0.0),
                        frame.get("i_c", 0.0),
                        frame.get("freq", 60.0)
                    ])
            
            self.last_export_stats = {
                "format": "simple",
                "frames": len(frames),
                "columns": 8
            }
            return True
            
        except Exception as e:
            logger.error(f"Simple export failed: {e}")
            return False
    
    def _export_detailed(self, session_data: Dict, output_path: str, include_metadata: bool) -> bool:
        """Export detailed CSV with all available fields"""
        try:
            frames = session_data["frames"]
            events = session_data.get("events", [])
            
            # Detect all unique field names across all frames
            all_fields = set()
            for frame in frames:
                all_fields.update(frame.keys())
            
            # Sort fields for consistent column order
            field_list = sorted(all_fields)
            
            with open(output_path, 'w', newline='') as csvfile:
                if include_metadata:
                    self._write_metadata_header(csvfile, session_data, "detailed")
                
                writer = csv.DictWriter(csvfile, fieldnames=field_list, extrasaction='ignore')
                writer.writeheader()
                
                # Write all frames
                for frame in frames:
                    writer.writerow(frame)
            
            self.last_export_stats = {
                "format": "detailed",
                "frames": len(frames),
                "columns": len(field_list),
                "events": len(events)
            }
            return True
            
        except Exception as e:
            logger.error(f"Detailed export failed: {e}")
            return False
    
    def _export_analysis(self, session_data: Dict, output_path: str, include_metadata: bool) -> bool:
        """Export analysis-ready CSV with computed metrics"""
        try:
            frames = session_data["frames"]
            
            with open(output_path, 'w', newline='') as csvfile:
                if include_metadata:
                    self._write_metadata_header(csvfile, session_data, "analysis")
                
                writer = csv.writer(csvfile)
                
                # Header with computed fields
                writer.writerow([
                    "timestamp", "sample_index",
                    "v_an", "v_bn", "v_cn", "v_rms", "v_imbalance_pct",
                    "i_a", "i_b", "i_c", "i_rms",
                    "freq", "freq_deviation_hz",
                    "power_real_w", "power_reactive_var",
                    "fault_active", "event_marker"
                ])
                
                # Compute reference values
                freq_nominal = 60.0
                events_by_ts = {e.get("ts"): e.get("type", "unknown") for e in session_data.get("events", [])}
                
                # Data rows with computed metrics
                for idx, frame in enumerate(frames):
                    ts = frame.get("ts", 0.0)
                    v_an = frame.get("v_an", 0.0)
                    v_bn = frame.get("v_bn", 0.0)
                    v_cn = frame.get("v_cn", 0.0)
                    i_a = frame.get("i_a", 0.0)
                    i_b = frame.get("i_b", 0.0)
                    i_c = frame.get("i_c", 0.0)
                    freq = frame.get("freq", freq_nominal)
                    
                    # Compute derived metrics
                    v_rms = (abs(v_an) + abs(v_bn) + abs(v_cn)) / (3.0 * 1.414)  # Approx
                    v_avg = (abs(v_an) + abs(v_bn) + abs(v_cn)) / 3.0
                    v_imbalance = max(abs(v_an - v_avg), abs(v_bn - v_avg), abs(v_cn - v_avg)) / v_avg * 100 if v_avg > 0 else 0.0
                    i_rms = (abs(i_a) + abs(i_b) + abs(i_c)) / (3.0 * 1.414)  # Approx
                    freq_deviation = freq - freq_nominal
                    power_real = v_rms * i_rms  # Simplified, ignoring power factor
                    power_reactive = 0.0  # Placeholder
                    
                    fault_active = 1 if frame.get("fault_type") else 0
                    event_marker = events_by_ts.get(ts, "")
                    
                    writer.writerow([
                        ts, idx,
                        v_an, v_bn, v_cn, v_rms, v_imbalance,
                        i_a, i_b, i_c, i_rms,
                        freq, freq_deviation,
                        power_real, power_reactive,
                        fault_active, event_marker
                    ])
            
            self.last_export_stats = {
                "format": "analysis",
                "frames": len(frames),
                "columns": 17
            }
            return True
            
        except Exception as e:
            logger.error(f"Analysis export failed: {e}")
            return False
    
    def _write_metadata_header(self, csvfile, session_data: Dict, format_type: str):
        """Write metadata as commented header lines"""
        meta = session_data.get("meta", {})
        
        csvfile.write("# RedByte HIL Verifier Suite - Session Export\n")
        csvfile.write(f"# Export Format: {format_type}\n")
        csvfile.write(f"# Export Date: {datetime.now().isoformat()}\n")
        csvfile.write(f"# Session ID: {meta.get('session_id', 'unknown')}\n")
        csvfile.write(f"# Session Start: {meta.get('start_time', 'unknown')}\n")
        csvfile.write(f"# Frame Count: {meta.get('frame_count', len(session_data.get('frames', [])))}\n")
        csvfile.write(f"# Event Count: {len(session_data.get('events', []))}\n")
        csvfile.write("#\n")
        csvfile.write("# Column Units:\n")
        csvfile.write("#   timestamp: seconds (Unix epoch)\n")
        csvfile.write("#   v_an/bn/cn: Volts (instantaneous)\n")
        csvfile.write("#   i_a/b/c: Amperes (instantaneous)\n")
        csvfile.write("#   freq: Hertz\n")
        csvfile.write("#   power: Watts / VAR\n")
        csvfile.write("#\n")
    
    def get_export_summary(self) -> Optional[Dict]:
        """Get summary of last export operation"""
        if self.last_export_stats is None:
            return None
        
        return {
            "path": self.last_export_path,
            "stats": self.last_export_stats,
            "exists": os.path.exists(self.last_export_path) if self.last_export_path else False
        }
