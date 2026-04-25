"""
analysis.py — Run-to-run comparison engine for the VSM Evidence Workbench.

Compares two session Data Capsules and produces engineering metrics:
RMSE, max |delta|, frequency nadir difference, recovery-time difference,
THD difference, voltage overshoot difference, and (where data supports it)
voltage-imbalance difference.

All comparisons are time-aligned (by t_rel from the start of each session)
rather than by raw index, so captures with different sample rates or
start offsets can still be compared sensibly.
"""
from __future__ import annotations

import json
import logging
from typing import Dict, List, Optional

import numpy as np

from src.signal_processing import compute_rms, compute_thd
from src.event_detector import run_summary

logger = logging.getLogger(__name__)


class AnalysisEngine:
    """Comparison logic for two recorded sessions."""

    # ------------------------------------------------------------------
    @staticmethod
    def load_session(filepath: str) -> Dict:
        with open(filepath, "r") as f:
            return json.load(f)

    # ------------------------------------------------------------------
    @staticmethod
    def _extract(session: Dict, key: str) -> Dict[str, np.ndarray]:
        frames = session.get("frames", [])
        if not frames:
            return {"t_rel": np.array([]), "vals": np.array([])}
        ts = np.array([f.get("ts", 0.0) for f in frames], dtype=float)
        vals = np.array([f.get(key, 0.0) for f in frames], dtype=float)
        t_rel = ts - ts[0] if ts.size else ts
        return {"t_rel": t_rel, "vals": vals}

    # ------------------------------------------------------------------
    @staticmethod
    def _time_aligned(
        session_ref: Dict, session_test: Dict, signal_key: str,
        dt: Optional[float] = None,
    ):
        """Return (t, ref_aligned, test_aligned) on a common uniform timebase."""
        ref = AnalysisEngine._extract(session_ref, signal_key)
        test = AnalysisEngine._extract(session_test, signal_key)
        if ref["t_rel"].size < 2 or test["t_rel"].size < 2:
            return np.array([]), np.array([]), np.array([])

        t_end = min(ref["t_rel"][-1], test["t_rel"][-1])
        if t_end <= 0:
            return np.array([]), np.array([]), np.array([])

        # Pick a common dt — the coarser of the two native rates, or user override.
        if dt is None:
            dt_ref = float(np.median(np.diff(ref["t_rel"])))
            dt_test = float(np.median(np.diff(test["t_rel"])))
            dt = max(dt_ref, dt_test, 1e-6)

        t_common = np.arange(0.0, t_end + dt * 0.5, dt)
        ref_vals = np.interp(t_common, ref["t_rel"], ref["vals"])
        test_vals = np.interp(t_common, test["t_rel"], test["vals"])
        return t_common, ref_vals, test_vals

    # ------------------------------------------------------------------
    @staticmethod
    def compare_sessions(session_ref: Dict, session_test: Dict, signal_key: str = "v_an") -> Dict:
        """
        Compare one signal between two sessions on a time-aligned grid.

        Returns
        -------
        dict with:
          - t: time base (s, relative to run start)
          - ref_values, test_values, deltas  (numeric lists)
          - rmse, max_delta, mean_delta  (floats)
          - signal_key  (str)
          - aligned_dt  (float)
        """
        t, ref, test = AnalysisEngine._time_aligned(session_ref, session_test, signal_key)
        if t.size == 0:
            return {"rmse": 0.0, "max_delta": 0.0, "mean_delta": 0.0,
                    "t": [], "ref_values": [], "test_values": [], "deltas": [],
                    "signal_key": signal_key, "aligned_dt": 0.0}
        deltas = test - ref
        return {
            "signal_key": signal_key,
            "aligned_dt": float(t[1] - t[0]) if t.size >= 2 else 0.0,
            "t": t.tolist(),
            "ref_values": ref.tolist(),
            "test_values": test.tolist(),
            "deltas": deltas.tolist(),
            "rmse": float(np.sqrt(np.mean(deltas ** 2))),
            "max_delta": float(np.max(np.abs(deltas))),
            "mean_delta": float(np.mean(deltas)),
        }

    # ------------------------------------------------------------------
    @staticmethod
    def comparison_scorecard(session_ref: Dict, session_test: Dict) -> Dict:
        """
        Produce an engineering scorecard comparing two runs.

        Returns a dict with per-metric delta values AND a high-level
        "which-run-performed-better" verdict, computed from improvements
        in stability (lower THD, smaller freq nadir deviation, shorter recovery).
        """
        s_ref = run_summary(session_ref)
        s_test = run_summary(session_test)

        # pairwise signal-wise RMSE/max deltas
        per_signal = {}
        for sig in ("v_an", "v_bn", "v_cn", "i_a", "i_b", "i_c", "freq"):
            c = AnalysisEngine.compare_sessions(session_ref, session_test, sig)
            per_signal[sig] = {
                "rmse": c["rmse"],
                "max_delta": c["max_delta"],
                "mean_delta": c["mean_delta"],
            }

        nadir_ref = s_ref.get("freq_min", 60.0)
        nadir_test = s_test.get("freq_min", 60.0)

        zenith_ref = s_ref.get("freq_max", 60.0)
        zenith_test = s_test.get("freq_max", 60.0)

        thd_ref = s_ref.get("thd_van_pct", 0.0)
        thd_test = s_test.get("thd_van_pct", 0.0)

        recov_ref = s_ref.get("recovery_time_estimate_s", 0.0)
        recov_test = s_test.get("recovery_time_estimate_s", 0.0)

        def _pct_diff(a, b):
            if abs(a) < 1e-9:
                return None
            return float((b - a) / abs(a) * 100.0)

        # Voltage imbalance — largest per-phase deviation from 3-phase mean RMS
        def imbalance(sess):
            r = sess.get("v_rms_per_phase", {})
            if not r:
                return 0.0
            vals = np.array([r.get("a", 0), r.get("b", 0), r.get("c", 0)])
            mean = np.mean(vals)
            if abs(mean) < 1e-9:
                return 0.0
            return float(np.max(np.abs(vals - mean)) / mean * 100.0)

        imb_ref = imbalance(s_ref)
        imb_test = imbalance(s_test)

        # Max |overshoot|: largest voltage excursion vs nominal 120 V
        def max_overshoot(sess):
            nom = 120.0 * np.sqrt(2)
            vmax = abs(sess.get("v_max", 0.0))
            vmin = abs(sess.get("v_min", 0.0))
            return max(vmax, vmin) - nom  # positive means peaked above nominal

        # ---- "which run was better" — count improvements ----
        improvements = 0
        regressions = 0
        if thd_test < thd_ref: improvements += 1
        elif thd_test > thd_ref: regressions += 1
        if abs(60.0 - nadir_test) < abs(60.0 - nadir_ref): improvements += 1
        elif abs(60.0 - nadir_test) > abs(60.0 - nadir_ref): regressions += 1
        if abs(60.0 - zenith_test) < abs(60.0 - zenith_ref): improvements += 1
        elif abs(60.0 - zenith_test) > abs(60.0 - zenith_ref): regressions += 1
        if recov_test < recov_ref: improvements += 1
        elif recov_test > recov_ref: regressions += 1
        if imb_test < imb_ref: improvements += 1
        elif imb_test > imb_ref: regressions += 1

        if improvements > regressions:
            verdict = "Test run performed better than reference."
        elif regressions > improvements:
            verdict = "Reference run performed better than test."
        else:
            verdict = "Runs are roughly equivalent."

        return {
            "verdict": verdict,
            "improvements": improvements,
            "regressions": regressions,
            "ref_summary": s_ref,
            "test_summary": s_test,
            "per_signal": per_signal,
            "deltas": {
                "thd_van_pct":       {"ref": thd_ref,   "test": thd_test,   "delta": thd_test - thd_ref},
                "freq_nadir_hz":     {"ref": nadir_ref, "test": nadir_test, "delta": nadir_test - nadir_ref},
                "freq_zenith_hz":    {"ref": zenith_ref,"test": zenith_test,"delta": zenith_test - zenith_ref},
                "recovery_time_s":   {"ref": recov_ref, "test": recov_test, "delta": recov_test - recov_ref},
                "voltage_imbalance_pct": {"ref": imb_ref, "test": imb_test, "delta": imb_test - imb_ref},
                "max_overshoot_peak_v":  {"ref": max_overshoot(s_ref), "test": max_overshoot(s_test),
                                          "delta": max_overshoot(s_test) - max_overshoot(s_ref)},
            },
        }

    # ------------------------------------------------------------------
    @staticmethod
    def scorecard_to_csv(scorecard: Dict, out_path: str) -> str:
        """Flatten a scorecard into a CSV table of metric / ref / test / delta."""
        import csv
        import os
        os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
        with open(out_path, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["metric", "ref", "test", "delta"])
            for metric, d in scorecard.get("deltas", {}).items():
                w.writerow([metric, d["ref"], d["test"], d["delta"]])
            w.writerow([])
            w.writerow(["signal", "rmse", "max_delta", "mean_delta"])
            for sig, d in scorecard.get("per_signal", {}).items():
                w.writerow([sig, d["rmse"], d["max_delta"], d["mean_delta"]])
            w.writerow([])
            w.writerow(["verdict", scorecard.get("verdict", "")])
        return os.path.abspath(out_path)
