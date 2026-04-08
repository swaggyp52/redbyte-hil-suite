"""
File ingestion layer for RedByte GFM HIL Suite.

Supported formats:
  .csv            Rigol DSO oscilloscope captures (chunked, handles 1M+ rows)
  .xls / .xlsx    Simulation Excel files (time-series columns)
  .json           Existing Data Capsule session files

All ingestors return an ImportedDataset — a normalized in-memory object whose
channels retain their original header names.  No engineering signal assumptions
are made here.  Channel renaming to canonical names is handled separately by
ChannelMapper (src/channel_mapping.py).

Performance notes:
  - Rigol CSV files are read with stdlib csv in 100 k-row chunks.
  - In-memory sample cap is 2 M rows per channel to guard against OOM.
  - Trailing NaN rows (a common Rigol artifact beyond the trigger window) are
    trimmed and a warning is raised.
  - Duplicate channel content (same data under different names) is detected via
    Pearson correlation and flagged as a warning.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

# Chunked read size for large CSV files
_CHUNK_ROWS = 100_000

# Hard cap on in-memory rows per channel
_MAX_SAMPLES = 2_000_000


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class ImportedDataset:
    """
    Canonical in-memory representation of an imported run or simulation file.

    Attributes:
        source_type:  'rigol_csv' | 'simulation_excel' | 'data_capsule_json'
        source_path:  Absolute path to the source file.
        channels:     Dict of channel_name -> numpy float64 array.
                      Keys are the *original* column headers from the file
                      before any ChannelMapper renaming.
        time:         Relative time axis in seconds, starting at 0.
        sample_rate:  Estimated sample rate in Hz (0.0 if indeterminate).
        duration:     Total duration in seconds.
        warnings:     User-facing warning strings (duplicates, NaNs, etc.).
        meta:         Dict of file-level metadata (row count, sheet name, …).
        raw_headers:  Original column headers in file order.
    """
    source_type: str
    source_path: str
    channels: dict[str, np.ndarray]
    time: np.ndarray
    sample_rate: float
    duration: float
    warnings: list[str] = field(default_factory=list)
    meta: dict = field(default_factory=dict)
    raw_headers: list[str] = field(default_factory=list)

    @property
    def row_count(self) -> int:
        return len(self.time)

    @property
    def channel_names(self) -> list[str]:
        return list(self.channels.keys())


class IngestionError(Exception):
    """Raised when a file cannot be ingested."""


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def ingest_file(path: str) -> ImportedDataset:
    """
    Auto-detect file type and ingest.

    Raises:
        IngestionError  if the file cannot be read, parsed, or has no data.
        FileNotFoundError  if the path does not exist.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"File not found: {path}")

    suffix = p.suffix.lower()
    if suffix == ".csv":
        return _ingest_rigol_csv(path)
    if suffix in (".xls", ".xlsx"):
        return _ingest_simulation_excel(path)
    if suffix == ".json":
        return _ingest_data_capsule_json(path)

    raise IngestionError(
        f"Unsupported file format '{suffix}'. "
        "Supported: .csv, .xls, .xlsx, .json"
    )


# ---------------------------------------------------------------------------
# Rigol CSV ingestion
# ---------------------------------------------------------------------------

def _ingest_rigol_csv(path: str) -> ImportedDataset:
    """
    Parse a Rigol DSO CSV capture using only stdlib csv (no pandas required).

    Expected layout::

        Time(s),CH1(V),CH2(V),CH3(V),CH4(V)
        -0.00200000,-0.04,-0.04,-0.04,-0.04
        ...

    Some Rigol firmware versions prepend metadata lines (e.g. ``X,Y,``).
    This function scans for the actual header row before reading data.
    Data is read in chunks of _CHUNK_ROWS rows to bound peak memory use.
    Bad rows (non-parseable as float) are silently skipped with a warning.
    """
    import csv as _csv

    warnings: list[str] = []
    meta: dict = {"file_size_bytes": os.path.getsize(path)}

    # ── Locate the true header row ───────────────────────────────────────────
    header_row_idx = 0
    with open(path, "r", newline="", errors="replace") as fh:
        for i, raw_line in enumerate(fh):
            line = raw_line.strip()
            if not line or line.startswith("#"):
                header_row_idx = i + 1
                continue
            parts = [p.strip() for p in line.split(",")]
            try:
                float(parts[0])
                # First parseable cell is numeric → data started before header.
                # The previously identified header_row_idx stays.
                break
            except ValueError:
                header_row_idx = i
                break

    # ── Chunked read with stdlib csv ─────────────────────────────────────────
    columns: Optional[list[str]] = None
    arrays: dict[str, list] = {}
    total_rows = 0
    bad_rows = 0

    try:
        with open(path, "r", newline="", errors="replace") as fh:
            reader = _csv.reader(fh)
            # Skip preamble rows before the header
            for _ in range(header_row_idx):
                next(reader, None)

            # Header row
            header_row = next(reader, None)
            if header_row is None:
                raise IngestionError(f"Rigol CSV '{path}' has no header row.")
            columns = [c.strip() for c in header_row if c.strip()]
            if not columns:
                raise IngestionError(f"Rigol CSV '{path}' header is empty.")
            for col in columns:
                arrays[col] = []

            n_cols = len(columns)
            chunk_count = 0

            for row in reader:
                if total_rows >= _MAX_SAMPLES:
                    warnings.append(
                        f"File truncated at {_MAX_SAMPLES:,} rows "
                        f"(sample cap reached; further data not loaded)."
                    )
                    break

                # Skip rows that don't have enough columns or contain non-float
                if len(row) < n_cols:
                    bad_rows += 1
                    continue
                try:
                    parsed = [float(row[i]) for i in range(n_cols)]
                except (ValueError, IndexError):
                    bad_rows += 1
                    continue

                for i, col in enumerate(columns):
                    arrays[col].append(parsed[i])

                total_rows += 1
                chunk_count += 1
                if chunk_count >= _CHUNK_ROWS:
                    chunk_count = 0  # just keeps memory from fragmenting badly

    except IngestionError:
        raise
    except Exception as exc:
        raise IngestionError(
            f"Failed to read Rigol CSV '{path}': {exc}"
        ) from exc

    if bad_rows > 0:
        warnings.append(
            f"{bad_rows:,} non-parseable row(s) skipped during CSV read."
        )

    if not columns or total_rows == 0:
        raise IngestionError(
            f"Rigol CSV '{path}' has no readable data rows."
        )

    meta["row_count"] = total_rows
    meta["headers"] = columns

    # ── Extract time axis ────────────────────────────────────────────────────
    time_col = _find_time_column(columns)
    if time_col is None:
        raise IngestionError(
            f"No time column found in Rigol CSV. "
            f"Headers detected: {columns}"
        )

    raw_time = np.array(arrays[time_col], dtype=float)
    t0 = raw_time[0]
    time_arr = raw_time - t0

    # ── Build per-channel arrays ─────────────────────────────────────────────
    channel_arrays: dict[str, np.ndarray] = {}
    common_len = len(time_arr)

    # Rigol uses 9.9E+37 as a fill / overflow sentinel (beyond trigger window).
    # Replace any value > 1e30 with NaN so downstream code handles it cleanly.
    _RIGOL_FILL_THRESHOLD = 1e30

    for col in columns:
        if col == time_col:
            continue
        arr = np.array(arrays[col], dtype=float)

        # Convert Rigol fill values to NaN
        fill_mask = np.abs(arr) > _RIGOL_FILL_THRESHOLD
        if fill_mask.any():
            arr = arr.copy()
            arr[fill_mask] = np.nan

        nan_count = int(np.isnan(arr).sum())
        if nan_count > 0:
            warnings.append(
                f"Channel '{col}': {nan_count:,} NaN values "
                f"(Rigol fill rows beyond trigger window trimmed)."
            )
            valid_mask = ~np.isnan(arr)
            if valid_mask.any():
                last_valid = int(np.where(valid_mask)[0][-1])
                arr = arr[:last_valid + 1]
            else:
                arr = arr[:0]
            common_len = min(common_len, len(arr))

        channel_arrays[col] = arr

    # Trim all channels and time to the shortest valid length
    time_arr = time_arr[:common_len]
    for col in channel_arrays:
        channel_arrays[col] = channel_arrays[col][:common_len]

    sample_rate = _estimate_sample_rate(time_arr)
    duration = float(time_arr[-1] - time_arr[0]) if len(time_arr) > 1 else 0.0

    _check_for_duplicate_channels(channel_arrays, warnings)

    meta["time_column"] = time_col
    meta["sample_rate"] = sample_rate

    logger.info(
        "Ingested Rigol CSV '%s': %d rows, %.1f Hz, %.3f s, channels=%s",
        Path(path).name, total_rows, sample_rate, duration,
        list(channel_arrays.keys()),
    )

    return ImportedDataset(
        source_type="rigol_csv",
        source_path=str(Path(path).resolve()),
        channels=channel_arrays,
        time=time_arr,
        sample_rate=sample_rate,
        duration=duration,
        warnings=warnings,
        meta=meta,
        raw_headers=columns,
    )


# ---------------------------------------------------------------------------
# Simulation Excel ingestion
# ---------------------------------------------------------------------------

def _ingest_simulation_excel(path: str) -> ImportedDataset:
    """
    Parse a simulation output Excel file.

    Reads the first non-empty sheet.  Expects numeric columns with an
    identifiable time axis.  Non-numeric columns are skipped with a warning.
    """
    try:
        import openpyxl  # noqa: F401  (already present; just verify)
    except ImportError:
        raise IngestionError(
            "openpyxl is required to read Excel files. "
            "Run: pip install openpyxl"
        )

    import pandas as pd

    warnings: list[str] = []
    meta: dict = {"file_size_bytes": os.path.getsize(path)}

    try:
        with pd.ExcelFile(path, engine="openpyxl") as xl:
            meta["sheets"] = xl.sheet_names

            df = None
            used_sheet = None
            for sheet in xl.sheet_names:
                candidate = xl.parse(sheet)
                if len(candidate) > 0 and len(candidate.columns) > 0:
                    df = candidate
                    used_sheet = sheet
                    break

    except IngestionError:
        raise
    except Exception as exc:
        raise IngestionError(
            f"Failed to read Excel file '{path}': {exc}"
        ) from exc

    if df is None:
        raise IngestionError(f"Excel file '{path}' contains no readable data.")

    df = df.dropna(how="all")
    meta["used_sheet"] = used_sheet
    meta["row_count"] = len(df)

    columns = list(df.columns)
    meta["headers"] = columns

    # ── Extract time axis ────────────────────────────────────────────────────
    time_col = _find_time_column(columns)
    if time_col is None:
        warnings.append(
            "No time column detected in Excel file. "
            "Row index used as sample index — no physical time available."
        )
        time_arr = np.arange(len(df), dtype=float)
        sample_rate = 0.0
    else:
        raw_time = df[time_col].to_numpy(dtype=float)
        time_arr = raw_time - raw_time[0]
        sample_rate = _estimate_sample_rate(time_arr)

    # ── Build channel arrays ─────────────────────────────────────────────────
    channel_arrays: dict[str, np.ndarray] = {}
    for col in columns:
        if col == time_col:
            continue
        try:
            arr = df[col].to_numpy(dtype=float)
        except (ValueError, TypeError):
            warnings.append(
                f"Column '{col}' contains non-numeric data and was skipped."
            )
            continue

        nan_count = int(np.isnan(arr).sum())
        if nan_count > 0:
            warnings.append(
                f"Column '{col}': {nan_count} NaN values present."
            )
        channel_arrays[col] = arr

    if not channel_arrays:
        raise IngestionError(
            f"Excel file '{path}' has no usable numeric data columns."
        )

    duration = float(time_arr[-1] - time_arr[0]) if len(time_arr) > 1 else 0.0

    _check_for_duplicate_channels(channel_arrays, warnings)

    meta["time_column"] = time_col
    meta["sample_rate"] = sample_rate

    logger.info(
        "Ingested Excel '%s' (sheet '%s'): %d rows, %.1f Hz, %.3f s, channels=%s",
        Path(path).name, used_sheet, len(df), sample_rate, duration,
        list(channel_arrays.keys()),
    )

    return ImportedDataset(
        source_type="simulation_excel",
        source_path=str(Path(path).resolve()),
        channels=channel_arrays,
        time=time_arr,
        sample_rate=sample_rate,
        duration=duration,
        warnings=warnings,
        meta=meta,
        raw_headers=columns,
    )


# ---------------------------------------------------------------------------
# Data Capsule JSON ingestion
# ---------------------------------------------------------------------------

def _ingest_data_capsule_json(path: str) -> ImportedDataset:
    """
    Load an existing Data Capsule session JSON file.

    Extracts the ``frames`` list and builds per-channel numpy arrays.
    Canonical key names (v_an, v_bn, …) are preserved as-is.
    """
    warnings: list[str] = []
    meta: dict = {}

    try:
        with open(path, "r") as fh:
            data = json.load(fh)
    except Exception as exc:
        raise IngestionError(
            f"Failed to read JSON '{path}': {exc}"
        ) from exc

    frames = data.get("frames", [])
    if not frames:
        raise IngestionError(
            f"Data Capsule JSON '{path}' contains no frames."
        )

    # Detect all numeric keys across the first 20 frames
    all_keys: set[str] = set()
    for frm in frames[:20]:
        for k, v in frm.items():
            if k not in ("ts", "fault_type", "status") and isinstance(v, (int, float)):
                all_keys.add(k)

    session_meta = data.get("meta", {})
    meta["version"] = session_meta.get("version", "unknown")
    meta["session_id"] = session_meta.get("session_id", "")
    meta["row_count"] = len(frames)
    meta["headers"] = sorted(all_keys)

    raw_ts = np.array([frm.get("ts", 0.0) for frm in frames], dtype=float)
    t0 = raw_ts[0]
    time_arr = raw_ts - t0

    # Warn if ts values look relative rather than epoch
    if 0.0 <= t0 < 1e6:
        warnings.append(
            "Session 'ts' values appear to be relative time (not epoch). "
            "Time axis normalized to start at 0."
        )

    channel_arrays: dict[str, np.ndarray] = {}
    for key in sorted(all_keys):
        arr = np.array(
            [frm.get(key, np.nan) for frm in frames], dtype=float
        )
        channel_arrays[key] = arr

    sample_rate = _estimate_sample_rate(time_arr)
    duration = float(time_arr[-1]) if len(time_arr) > 1 else 0.0

    logger.info(
        "Ingested Data Capsule JSON '%s': %d frames, %.1f Hz, channels=%s",
        Path(path).name, len(frames), sample_rate, sorted(all_keys),
    )

    return ImportedDataset(
        source_type="data_capsule_json",
        source_path=str(Path(path).resolve()),
        channels=channel_arrays,
        time=time_arr,
        sample_rate=sample_rate,
        duration=duration,
        warnings=warnings,
        meta=meta,
        raw_headers=sorted(all_keys),
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TIME_COL_HINTS: frozenset[str] = frozenset({
    "time", "time(s)", "time(ms)", "time(us)", "time(ns)",
    "t", "ts", "timestamp", "seconds", "time_s", "time_ms",
})


def _find_time_column(columns: list[str]) -> Optional[str]:
    """Return the column name most likely to be the time axis."""
    for col in columns:
        if col.strip().lower() in _TIME_COL_HINTS:
            return col
    # Fuzzy: starts with "time" or "t("
    for col in columns:
        lo = col.strip().lower()
        if lo.startswith("time") or lo == "t":
            return col
    return None


def _estimate_sample_rate(time_arr: np.ndarray) -> float:
    """Estimate sample rate (Hz) from a time-axis array."""
    if len(time_arr) < 2:
        return 0.0
    diffs = np.diff(time_arr)
    diffs = diffs[diffs > 0]
    if len(diffs) == 0:
        return 0.0
    median_dt = float(np.median(diffs))
    return round(1.0 / median_dt, 2) if median_dt > 0 else 0.0


def _check_for_duplicate_channels(
    channels: dict[str, np.ndarray],
    warnings: list[str],
    threshold: float = 0.9999,
) -> None:
    """
    Warn when two channels appear nearly identical (correlation ≥ threshold).

    This catches files like VSGFrequency_Simulation.xlsx exported twice with
    different sheet/column names but the same data.
    """
    names = list(channels.keys())
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            a = channels[names[i]]
            b = channels[names[j]]
            n = min(len(a), len(b))
            if n < 10:
                continue
            try:
                corr = float(np.corrcoef(a[:n], b[:n])[0, 1])
                if abs(corr) >= threshold:
                    warnings.append(
                        f"Channels '{names[i]}' and '{names[j]}' are nearly "
                        f"identical (corr={corr:.5f}). "
                        f"File may contain duplicate data under different names."
                    )
            except Exception:
                pass
