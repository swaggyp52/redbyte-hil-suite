import json
import logging
import numpy as np

logger = logging.getLogger(__name__)

class AnalysisEngine:
    """
    Comparison logic for two recorded sessions.
    Assumes standard "Data Capsule" format.
    """
    
    @staticmethod
    def load_session(filepath: str):
        with open(filepath, 'r') as f:
            return json.load(f)

    @staticmethod
    def compare_sessions(session_ref, session_test, signal_key):
        """
        Compares a specific signal between two sessions.
        Simple logic: aligns by index (assuming same sample rate).
        Future: Align by timestamp.
        
        Returns:
            dict: {
                "rmse": float,
                "max_delta": float,
                "ref_values": list,
                "test_values": list,
                "deltas": list
            }
        """
        frames_ref = session_ref.get('frames', [])
        frames_test = session_test.get('frames', [])
        
        # Extract signal
        ref_vals = [f.get(signal_key, 0) for f in frames_ref]
        test_vals = [f.get(signal_key, 0) for f in frames_test]
        
        # Truncate to shorter
        min_len = min(len(ref_vals), len(test_vals))
        ref_vals = np.array(ref_vals[:min_len])
        test_vals = np.array(test_vals[:min_len])
        
        if min_len == 0:
             return {"rmse": 0, "max_delta": 0, "deltas": []}
             
        deltas = test_vals - ref_vals
        rmse = np.sqrt(np.mean(deltas**2))
        max_delta = np.max(np.abs(deltas))
        
        return {
            "rmse": rmse,
            "max_delta": max_delta,
            "ref_values": ref_vals.tolist(),
            "test_values": test_vals.tolist(),
            "deltas": deltas.tolist()
        }
