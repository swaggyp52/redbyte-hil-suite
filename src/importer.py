"""
importer.py — External data ingest for the VSM Evidence Workbench.

This module converts exported tabular datasets (CSV / Excel) from lab and
simulation tools into the project's standard Data Capsule format:

    {
      "meta":   {...},
      "events": [...],
      "frames": [ {"ts": float, "v_an": float, "v_bn": float, ...}, ... ]
    }

It is the plumbing that replaces the old "must already be an internal JSON
session" assumption, so real engineering data can flow through replay,
comparison, and standards evaluation without hand-editing files.

Public API
----------
    DataImporter.import_csv(filepath, column_map=None, options=None)
    DataImporter.import_excel(filepath, sheet_name=None, column_map=None, options=None)
    DataImporter.import_auto(filepath, options=None)
    DataImporter.save_capsule(capsule, output_path)
    DataImporter.suggest_mapping(columns)           # alias auto-detect helper
    DataImporter.preview(filepath, sheet_name=None) # head() preview without mapping
"""
from __future__ import annotations

import json
import logging
import math
import os
import time
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


# ---- Canonical engineering channels expected downstream ------------------
CANONICAL_CHANNELS: Tuple[str, ...] = (
    "v_an", "v_bn", "v_cn",
    "i_a", "i_b", "i_c",
    "freq", "p_mech",
)

# ---- Alias table for auto-detection --------------------------------------
# Keys are canonical channel names; values are lowercased alias fragments
# that may appear in real-world header names.  Matching is loose: header is
# lowercased, stripped, and compared against the alias list (exact or substring).
ALIAS_TABLE: Dict[str, Tuple[str, ...]] = {
    "ts": (
        "ts", "time", "t", "time_s", "time(s)", "time_sec", "time sec",
        "time(ms)", "time_ms", "time ms", "timestamp", "timestamp_s",
        "seconds", "sec", "msec", "milliseconds", "ms",
    ),
    "v_an": (
        "v_an", "van", "va", "v_a", "v a", "vphasea", "phase_a_voltage",
        "phase a voltage", "voltage_a", "volt_a", "va(v)", "vag", "vaa",
        "u_a", "uan", "v1", "vab_n",
    ),
    "v_bn": (
        "v_bn", "vbn", "vb", "v_b", "v b", "vphaseb", "phase_b_voltage",
        "phase b voltage", "voltage_b", "volt_b", "vb(v)", "vbg",
        "u_b", "ubn", "v2",
    ),
    "v_cn": (
        "v_cn", "vcn", "vc", "v_c", "v c", "vphasec", "phase_c_voltage",
        "phase c voltage", "voltage_c", "volt_c", "vc(v)", "vcg",
        "u_c", "ucn", "v3",
    ),
    "i_a": (
        "i_a", "ia", "i a", "iphasea", "phase_a_current", "phase a current",
        "current_a", "curr_a", "ia(a)", "amp_a", "i1",
    ),
    "i_b": (
        "i_b", "ib", "i b", "iphaseb", "phase_b_current", "phase b current",
        "current_b", "curr_b", "ib(a)", "amp_b", "i2",
    ),
    "i_c": (
        "i_c", "ic", "i c", "iphasec", "phase_c_current", "phase c current",
        "current_c", "curr_c", "ic(a)", "amp_c", "i3",
    ),
    "freq": (
        "freq", "frequency", "hz", "f", "f_grid", "grid_freq", "grid_frequency",
        "fgrid", "fline",
        # VSG / VSM simulation exports
        "freq_vsg", "vsg_freq", "vsgfreq", "f_vsg", "fvsg", "vsgfrequency",
        "freq_out", "fout", "omega", "omega_r",
    ),
    "p_mech": (
        "p_mech", "pmech", "mechanical_power", "mech_power", "power",
        "p_kw", "p(kw)", "kw", "p_out", "active_power", "p", "p_w",
        # Simulink / VSM inverter power exports
        "pinv", "p_inv", "p_inverter", "inverter_power", "inverterpwr",
        "p_elec", "pelec", "pout_inv",
    ),
}


# ==========================================================================
# Results
# ==========================================================================
class ImportResult(dict):
    """A Data Capsule with added .warnings / .mapping fields for UI feedback."""

    @property
    def warnings(self) -> List[str]:
        return self.get("meta", {}).get("import", {}).get("warnings", [])

    @property
    def mapping(self) -> Dict[str, str]:
        return self.get("meta", {}).get("import", {}).get("column_map", {})


# ==========================================================================
# DataImporter
# ==========================================================================
class DataImporter:
    """Convert CSV/Excel tabular exports into Data Capsules."""

    # ---- helpers ---------------------------------------------------------
    @staticmethod
    def _normalize_header(name: str) -> str:
        if name is None:
            return ""
        return str(name).strip().lower().replace("_", "").replace(" ", "").replace("-", "")

    @classmethod
    def suggest_mapping(cls, columns: List[str]) -> Dict[str, str]:
        """
        Auto-detect which source columns map to which canonical channels.

        Returns
        -------
        dict
            canonical_key -> source_column_name.  Only populated for detected
            channels.  Unmapped channels are simply absent.
        """
        mapping: Dict[str, str] = {}
        norm_to_original: Dict[str, str] = {
            cls._normalize_header(c): c for c in columns if c is not None
        }

        # Exact match pass first, then substring pass.
        for canonical, aliases in ALIAS_TABLE.items():
            norm_aliases = [cls._normalize_header(a) for a in aliases]

            # exact
            for na in norm_aliases:
                if na in norm_to_original and norm_to_original[na] not in mapping.values():
                    mapping[canonical] = norm_to_original[na]
                    break
            if canonical in mapping:
                continue

            # Substring / startswith — only for aliases of length >= 3 so
            # single-character aliases ("f", "t") can't gobble random headers
            # like "foo".  Pick the shortest matching header so "van" doesn't
            # accidentally swallow "vbn_avg".
            candidates = []
            for norm, orig in norm_to_original.items():
                if orig in mapping.values():
                    continue
                for na in norm_aliases:
                    if not na or len(na) < 3:
                        continue
                    if norm == na or norm.startswith(na) or na in norm:
                        candidates.append((len(norm), orig))
                        break
            if candidates:
                candidates.sort()
                mapping[canonical] = candidates[0][1]

        return mapping

    @staticmethod
    def _detect_time_unit(series: pd.Series) -> str:
        """
        Infer whether a time column is in seconds or milliseconds.

        Heuristic, conservative:
          - If the total span exceeds ~10 minutes (600) treat as ms.
          - If the median dt is ≥ 1 (a full unit between samples) treat as ms
            (no realistic lab sampling rate has dt of 1+ second).
          - Otherwise assume seconds.
        """
        arr = pd.to_numeric(series, errors="coerce").dropna().to_numpy()
        if arr.size < 2:
            return "s"
        diffs = np.diff(arr)
        diffs = diffs[diffs > 0]
        if diffs.size == 0:
            return "s"
        median_dt = float(np.median(diffs))
        total_span = float(arr[-1] - arr[0])
        # Clear "obviously ms" signals:
        if median_dt >= 1.0:
            return "ms"
        if total_span > 600.0 and median_dt > 0.1:
            return "ms"
        return "s"

    @staticmethod
    def _read_tabular(filepath: str, sheet_name=None, nrows: Optional[int] = None) -> pd.DataFrame:
        ext = os.path.splitext(filepath)[1].lower()
        if ext == ".csv":
            # tolerate common separators
            try:
                return pd.read_csv(filepath, nrows=nrows)
            except Exception:
                return pd.read_csv(filepath, sep=None, engine="python", nrows=nrows)
        if ext in (".xlsx", ".xls"):
            return pd.read_excel(filepath, sheet_name=sheet_name or 0, nrows=nrows)
        raise ValueError(f"Unsupported file extension: {ext}")

    # ---- preview ---------------------------------------------------------
    @classmethod
    def preview(cls, filepath: str, sheet_name=None, n_rows: int = 10) -> Dict:
        """Return columns + head rows without converting to a capsule.

        For CSV files only ``n_rows`` data rows are read from disk so that
        previewing a 1 M-row Rigol capture does not block the UI thread.
        Excel files are small enough that a full read is acceptable.
        The total row count is estimated by a fast line-count pass for CSV.
        """
        ext = os.path.splitext(filepath)[1].lower()
        # For CSV, read only as many rows as needed for the preview.  A separate
        # fast pass counts lines so we can still report the total row count.
        if ext == ".csv":
            df_head = cls._read_tabular(filepath, sheet_name=None, nrows=n_rows)
            # Count lines quickly (subtract 1 for header)
            try:
                with open(filepath, "rb") as _fh:
                    total_rows = sum(1 for _ in _fh) - 1
            except Exception:
                total_rows = n_rows
        else:
            df_head = cls._read_tabular(filepath, sheet_name=sheet_name)
            total_rows = int(len(df_head))

        # For time-unit detection we need a few rows — df_head is enough.
        cols = list(df_head.columns)
        suggested = cls.suggest_mapping(cols)
        time_unit = "s"
        if "ts" in suggested and suggested["ts"] in df_head.columns:
            time_unit = cls._detect_time_unit(df_head[suggested["ts"]])
        return {
            "columns": [str(c) for c in cols],
            "n_rows": total_rows,
            "head": df_head.head(n_rows).to_dict(orient="records"),
            "suggested_mapping": suggested,
            "suggested_time_unit": time_unit,
        }

    @classmethod
    def list_excel_sheets(cls, filepath: str) -> List[str]:
        try:
            with pd.ExcelFile(filepath) as xl:
                return list(xl.sheet_names)
        except Exception as e:
            logger.error(f"Could not read sheet list from {filepath}: {e}")
            return []

    # ---- main import entry points ----------------------------------------
    @classmethod
    def import_csv(
        cls,
        filepath: str,
        column_map: Optional[Dict[str, str]] = None,
        options: Optional[Dict] = None,
        max_rows: Optional[int] = None,
    ) -> ImportResult:
        """Import a CSV file.

        Parameters
        ----------
        max_rows:
            When set, only the first *max_rows* data rows are loaded.  Used
            by the import wizard's live-validation preview to avoid blocking
            the UI thread on large Rigol captures (1 M+ rows).
        """
        df = cls._read_tabular(filepath, nrows=max_rows)
        return cls._dataframe_to_capsule(
            df,
            source_path=filepath,
            source_type="csv",
            column_map=column_map,
            options=options or {},
        )

    @classmethod
    def import_excel(
        cls,
        filepath: str,
        sheet_name: Optional[str] = None,
        column_map: Optional[Dict[str, str]] = None,
        options: Optional[Dict] = None,
    ) -> ImportResult:
        df = cls._read_tabular(filepath, sheet_name=sheet_name)
        return cls._dataframe_to_capsule(
            df,
            source_path=filepath,
            source_type="excel",
            column_map=column_map,
            options=options or {},
            source_sheet=sheet_name,
        )

    @classmethod
    def import_auto(
        cls,
        filepath: str,
        options: Optional[Dict] = None,
    ) -> ImportResult:
        ext = os.path.splitext(filepath)[1].lower()
        if ext == ".csv":
            return cls.import_csv(filepath, column_map=None, options=options)
        if ext in (".xlsx", ".xls"):
            return cls.import_excel(filepath, sheet_name=None, column_map=None, options=options)
        if ext == ".json":
            # Already a capsule — passthrough with import metadata so the rest
            # of the pipeline can treat any source uniformly.
            with open(filepath, "r") as f:
                data = json.load(f)
            cap = ImportResult(data)
            cap.setdefault("meta", {}).setdefault("import", {
                "source_path": os.path.abspath(filepath),
                "source_type": "json",
                "column_map": {},
                "warnings": [],
                "imported_at": time.time(),
            })
            return cap
        raise ValueError(f"Unsupported file extension: {ext}")

    # ---- core conversion -------------------------------------------------
    @classmethod
    def _dataframe_to_capsule(
        cls,
        df: pd.DataFrame,
        source_path: str,
        source_type: str,
        column_map: Optional[Dict[str, str]] = None,
        options: Optional[Dict] = None,
        source_sheet: Optional[str] = None,
    ) -> ImportResult:
        options = options or {}
        warnings: List[str] = []
        if df is None or df.empty:
            raise ValueError("Input dataframe is empty.")

        # 1) mapping
        if not column_map:
            column_map = cls.suggest_mapping(list(df.columns))
            if not column_map:
                raise ValueError(
                    "Could not auto-detect any known engineering channels. "
                    "Provide an explicit column_map."
                )

        if "ts" not in column_map:
            raise ValueError(
                "No time column mapped. Set column_map['ts'] to the source time column."
            )

        time_col = column_map["ts"]
        if time_col not in df.columns:
            raise ValueError(f"Mapped time column '{time_col}' not in source columns.")

        # 2) time handling
        raw_ts = pd.to_numeric(df[time_col], errors="coerce").to_numpy(dtype=float)
        if np.all(np.isnan(raw_ts)):
            raise ValueError(f"Time column '{time_col}' has no numeric values.")

        time_unit = str(options.get("time_unit") or "auto").lower()
        if time_unit == "auto":
            time_unit = cls._detect_time_unit(df[time_col])
            warnings.append(f"Auto-detected time unit: {time_unit}")
        if time_unit not in ("s", "ms"):
            warnings.append(f"Unknown time unit '{time_unit}', assuming seconds.")
            time_unit = "s"

        ts = raw_ts / 1000.0 if time_unit == "ms" else raw_ts.copy()

        # Handle NaN timestamps
        nan_mask = np.isnan(ts)
        if nan_mask.any():
            n_nan = int(nan_mask.sum())
            warnings.append(f"Dropped {n_nan} row(s) with non-numeric time values.")
            ts = ts[~nan_mask]
            df = df.loc[~nan_mask].reset_index(drop=True)

        if ts.size == 0:
            raise ValueError("All time values were invalid.")

        # Sort if non-monotonic
        if np.any(np.diff(ts) < 0):
            warnings.append("Non-monotonic time detected; rows sorted by time.")
            order = np.argsort(ts, kind="stable")
            ts = ts[order]
            df = df.iloc[order].reset_index(drop=True)

        # Deduplicate exact-duplicate timestamps (keep first occurrence)
        # If dt == 0 anywhere we nudge by a tiny epsilon so downstream code
        # that computes 1/dt doesn't explode.
        if ts.size >= 2:
            zero_dt = np.where(np.diff(ts) == 0)[0]
            if zero_dt.size:
                warnings.append(
                    f"Found {zero_dt.size} duplicate timestamp(s); nudged by 1 us."
                )
                eps = 1e-6
                for j in zero_dt:
                    ts[j + 1] = ts[j] + eps

        # Normalize so the first sample is t=0 internally? — NO.
        # Replay code tolerates arbitrary absolute ts and subtracts t0 itself.
        # Keep source-relative ts for fidelity.

        # 3) build per-frame data
        n_frames = len(ts)
        frames: List[Dict] = []
        missing_channels: List[str] = []
        channel_arrays: Dict[str, np.ndarray] = {}

        for canonical in CANONICAL_CHANNELS:
            src = column_map.get(canonical)
            if src and src in df.columns:
                vals = pd.to_numeric(df[src], errors="coerce").to_numpy(dtype=float)
                # Pad / truncate to n_frames (defensive — should already match).
                if vals.size != n_frames:
                    if vals.size > n_frames:
                        vals = vals[:n_frames]
                    else:
                        pad = np.full(n_frames - vals.size, np.nan)
                        vals = np.concatenate([vals, pad])
                # Fill NaN with 0.0
                n_nan = int(np.isnan(vals).sum())
                if n_nan:
                    warnings.append(f"Channel '{canonical}' had {n_nan} NaN(s), filled with 0.0.")
                    vals = np.where(np.isnan(vals), 0.0, vals)
                channel_arrays[canonical] = vals
            else:
                missing_channels.append(canonical)
                channel_arrays[canonical] = np.zeros(n_frames, dtype=float)

        if missing_channels:
            warnings.append(
                "Missing channels (filled with 0.0): " + ", ".join(missing_channels)
            )

        # Optional extras: unmapped source columns kept per-frame if the user
        # asks for them and the column is numeric.
        keep_extras = bool(options.get("keep_extras", False))
        extra_arrays: Dict[str, np.ndarray] = {}
        if keep_extras:
            mapped_source = set(column_map.values())
            for col in df.columns:
                if col in mapped_source:
                    continue
                vals = pd.to_numeric(df[col], errors="coerce")
                if vals.notna().sum() == 0:
                    continue
                extra_key = f"extra__{col}"
                extra_arrays[extra_key] = vals.fillna(0.0).to_numpy(dtype=float)

        # 4) optional resampling to uniform dt
        resample = options.get("resample")  # None | "auto" | float(seconds)
        resample_info: Optional[Dict] = None
        if resample is not None:
            if isinstance(resample, str) and resample == "auto":
                # Use median dt as target
                if ts.size >= 2:
                    target_dt = float(np.median(np.diff(ts)))
                else:
                    target_dt = 0.02
            else:
                target_dt = float(resample)

            if target_dt <= 0:
                warnings.append(f"Invalid resample dt={target_dt}, skipping resample.")
            else:
                new_ts = np.arange(ts[0], ts[-1] + target_dt * 0.5, target_dt)
                # interpolate each channel
                for k, arr in list(channel_arrays.items()):
                    channel_arrays[k] = np.interp(new_ts, ts, arr)
                for k, arr in list(extra_arrays.items()):
                    extra_arrays[k] = np.interp(new_ts, ts, arr)
                resample_info = {
                    "target_dt_s": target_dt,
                    "original_frames": int(n_frames),
                    "resampled_frames": int(new_ts.size),
                    "method": "linear",
                }
                ts = new_ts
                n_frames = ts.size
                warnings.append(
                    f"Resampled to uniform dt = {target_dt:.6g} s ({n_frames} frames)."
                )

        # 5) assemble frames
        for i in range(n_frames):
            frame: Dict = {"ts": float(ts[i])}
            for ch in CANONICAL_CHANNELS:
                frame[ch] = float(channel_arrays[ch][i])
            # status flag: if the source had one, use it; else 0 (nominal).
            if "status" in df.columns and len(df) == n_frames:
                try:
                    frame["status"] = int(df.iloc[i].get("status", 0) or 0)
                except Exception:
                    frame["status"] = 0
            else:
                frame["status"] = 0
            for k, arr in extra_arrays.items():
                frame[k] = float(arr[i])
            frames.append(frame)

        # 6) events: preserve only if the source provides them — nothing to
        # fabricate here.  Event extraction happens in replay / event_detector.
        events: List[Dict] = []

        # 7) meta
        duration_s = float(ts[-1] - ts[0]) if ts.size >= 2 else 0.0
        meta = {
            "session_id": os.path.splitext(os.path.basename(source_path))[0],
            "start_time": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "frame_count": n_frames,
            "duration_s": duration_s,
            "source": {
                "type": source_type,
                "path": os.path.abspath(source_path),
                "sheet": source_sheet,
                "file_size_bytes": os.path.getsize(source_path) if os.path.exists(source_path) else None,
            },
            "import": {
                "column_map": dict(column_map),
                "time_unit_detected": time_unit,
                "time_origin": "source-relative (preserved)",
                "missing_channels": missing_channels,
                "resample": resample_info,
                "warnings": warnings,
                "importer_version": "1.0",
                "imported_at": time.time(),
            },
        }

        return ImportResult({"meta": meta, "events": events, "frames": frames})

    # ---- persistence -----------------------------------------------------
    @staticmethod
    def save_capsule(capsule: Dict, output_path: str) -> str:
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(capsule, f, indent=2)
        return os.path.abspath(output_path)
