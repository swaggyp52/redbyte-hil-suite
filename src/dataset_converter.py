"""
Converts an ImportedDataset into a Data Capsule v1.2-compatible structure
that can be consumed by ReplayStudio and other existing UI components
without modification to their core rendering logic.

Design decisions:
  - Frames only contain channels actually present in the dataset.
  - Missing canonical fields (v_an, v_bn, …) are NOT fabricated; the UI
    must degrade gracefully when they are absent.
  - Large datasets are decimated to MAX_REPLAY_FRAMES for playback
    performance.  The full-resolution numpy arrays remain in the ImportedDataset
    for FFT, THD, and other analyses that need them.
  - A structured 'import_meta' key is added alongside the standard capsule
    keys to preserve provenance, warnings, and the applied channel mapping.
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Optional

import numpy as np

from src.derived_channels import derive_dataset_channels
from src.file_ingestion import ImportedDataset

logger = logging.getLogger(__name__)

# Replay decimation target — enough for smooth scrubbing without memory explosion.
# Increased to 20 000 so 60 Hz sinusoids in 10 MSa/s Rigol captures keep enough
# resolution after the min/max-envelope pass below.
MAX_REPLAY_FRAMES = 20_000
MIN_REPLAY_FRAMES = 50


def _minmax_decimate(arr: np.ndarray, target_pts: int) -> np.ndarray:
    """Return indices that preserve peaks/troughs via min/max pairs per bucket.

    For each of *target_pts//2* equal-width buckets the index of both the
    minimum and the maximum sample is included, so oscillating waveforms
    (60 Hz AC sinusoids) retain their amplitude envelope even after heavy
    decimation.  The returned indices are sorted and unique.
    """
    n = len(arr)
    if n <= target_pts:
        return np.arange(n, dtype=np.intp)
    n_buckets = max(1, target_pts // 2)
    bucket_size = n / n_buckets
    indices: list[int] = []
    for i in range(n_buckets):
        start = int(i * bucket_size)
        end   = min(int((i + 1) * bucket_size), n)
        if start >= end:
            continue
        chunk = arr[start:end]
        indices.append(start + int(np.argmin(chunk)))
        indices.append(start + int(np.argmax(chunk)))
    return np.array(sorted(set(indices)), dtype=np.intp)


# ---------------------------------------------------------------------------
# Main conversion
# ---------------------------------------------------------------------------

def dataset_to_session(
    dataset: ImportedDataset,
    session_id: Optional[str] = None,
) -> dict:
    """
    Convert an ImportedDataset to a Data Capsule v1.2-compatible dict.

    The returned dict can be passed directly to
    ``ReplayStudio.load_session_from_dict()`` or serialized to JSON.

    Args:
        dataset:     Source dataset (may be post channel-mapping).
        session_id:  Override session label.  Defaults to source filename stem.

    Returns:
        Dict with standard Data Capsule keys ('meta', 'frames', 'insights',
        'events') plus an extra 'import_meta' block with ingestion provenance.

    Raises:
        ValueError  if the dataset has no data rows.
    """
    t0 = time.perf_counter()
    dataset = derive_dataset_channels(dataset)
    n = len(dataset.time)
    if n == 0:
        raise ValueError("Dataset has no data rows — nothing to convert.")

    # ── Decimation ───────────────────────────────────────────────────────────
    target = max(MIN_REPLAY_FRAMES, min(MAX_REPLAY_FRAMES, n))
    if n > target:
        # Use min/max envelope decimation if any phase-voltage channel is present
        # so that AC sinusoid peaks are preserved.  Fall back to uniform sampling
        # for datasets that have no oscillating voltage channels.
        _PHASE_VOLTAGE_CHANNELS = {"v_an", "v_bn", "v_cn", "v_ab", "v_bc", "v_ca"}
        has_ac_voltage = bool(_PHASE_VOLTAGE_CHANNELS & dataset.channels.keys())
        if has_ac_voltage:
            # Use v_an (or the first available phase channel) as the reference
            # waveform for bucket min/max index selection.
            ref_ch = next(
                (ch for ch in ("v_an", "v_bn", "v_cn", "v_ab", "v_bc", "v_ca")
                 if ch in dataset.channels),
                None,
            )
            ref_arr = dataset.channels[ref_ch] if ref_ch else dataset.time
            indices = _minmax_decimate(ref_arr, target)
        else:
            indices = np.round(np.linspace(0, n - 1, target)).astype(int)
        dec_factor = round(n / len(indices), 1)
    else:
        indices = np.arange(n)
        dec_factor = 1.0

    dec_time = dataset.time[indices]
    dec_channels: dict[str, np.ndarray] = {
        ch: arr[indices]
        for ch, arr in dataset.channels.items()
    }

    # ── Build frame list ─────────────────────────────────────────────────────
    frames: list[dict] = []
    channel_names = list(dec_channels.keys())

    for i in range(len(indices)):
        frame: dict = {"ts": float(dec_time[i])}
        for ch in channel_names:
            val = float(dec_channels[ch][i])
            if not np.isnan(val):
                frame[ch] = val
        frames.append(frame)

    # Estimate sample rate from the decimated time axis
    if len(dec_time) > 1:
        diffs = np.diff(dec_time)
        pos_diffs = diffs[diffs > 0]
        sr_dec = float(1.0 / np.median(pos_diffs)) if len(pos_diffs) > 0 else 0.0
    else:
        sr_dec = 0.0

    sid = session_id or Path(dataset.source_path).stem

    # ── Assemble capsule ─────────────────────────────────────────────────────
    capsule = {
        "meta": {
            "version":               "1.2",
            "session_id":            sid,
            "start_time":            "",
            "frame_count":           len(frames),
            "sample_rate_estimate":  round(sr_dec, 2),
            "channels":              sorted(channel_names),
            "source_type":           dataset.source_type,
            "source_path":           dataset.source_path,
            "duration_s":            round(dataset.duration, 4),
            "original_row_count":    n,
            "decimation_factor":     dec_factor,
            "time_range_s":          {
                "start": round(float(dataset.time[0]), 6),
                "end": round(float(dataset.time[-1]), 6),
            },
        },
        "frames":   frames,
        "insights": [],
        "events":   [],
        "import_meta": {
            "source_type":           dataset.source_type,
            "source_path":           dataset.source_path,
            "warnings":              list(dataset.warnings),
            "raw_headers":           list(dataset.raw_headers),
            "applied_mapping":       dataset.meta.get("applied_mapping", {}),
            "original_sample_rate":  dataset.sample_rate,
            "original_row_count":    n,
            "derived_channels":      list(dataset.meta.get("derived_channels", [])),
            "scale_factors":         dict(dataset.meta.get("scale_factors", {})),
            "imported_at":           time.time(),
            "source_hash_sha256":    dataset.meta.get("source_hash_sha256"),
        },
    }

    logger.info(
        "Converted dataset '%s' → session '%s': %d → %d frames (%.1fx dec), "
        "channels=%s",
        Path(dataset.source_path).name, sid, n, len(frames), dec_factor,
        sorted(channel_names),
    )

    elapsed = time.perf_counter() - t0
    logger.info("dataset_to_session.end: %s (%.3fs)", Path(dataset.source_path).name, elapsed)

    return capsule


# ---------------------------------------------------------------------------
# Persistence helpers
# ---------------------------------------------------------------------------

def save_session(capsule: dict, out_dir: str = "data/sessions") -> str:
    """
    Serialize a session capsule dict to JSON and return the file path.

    Note: For Rigol files with 1 M rows the decimated replay capsule is
    typically ~500 kB — manageable.  Raw arrays are never written here.
    """
    os.makedirs(out_dir, exist_ok=True)
    sid = capsule["meta"]["session_id"]
    path = os.path.join(out_dir, f"{sid}.json")
    serializable = {
        key: value
        for key, value in capsule.items()
        if not key.startswith("_")
    }
    with open(path, "w") as fh:
        json.dump(serializable, fh, indent=2)
    logger.info("Session saved: %s", path)
    return path


def load_session(path: str) -> dict:
    """Load and return a Data Capsule JSON dict from disk."""
    with open(path, "r") as fh:
        return json.load(fh)


# ---------------------------------------------------------------------------
# Full-resolution analysis helpers
# ---------------------------------------------------------------------------

def get_channel_full_res(
    dataset: ImportedDataset,
    channel: str,
) -> Optional[tuple[np.ndarray, np.ndarray]]:
    """
    Return (time_array, signal_array) at full resolution for a given channel.

    Use this instead of the decimated frames when computing FFT, THD, or step
    metrics where resolution matters.

    Returns None if the channel is not present.
    """
    arr = dataset.channels.get(channel)
    if arr is None:
        return None
    return dataset.time, arr


def available_channels(dataset: ImportedDataset) -> dict[str, dict]:
    """
    Return a dict of channel_name → info for each channel in the dataset.

    Info includes:
      - 'unit': inferred unit string or ''
      - 'min', 'max', 'mean', 'std': basic statistics
      - 'has_nan': bool
    """
    from src.channel_mapping import infer_unit_from_header

    result: dict[str, dict] = {}
    for ch, arr in dataset.channels.items():
        valid = arr[~np.isnan(arr)]
        result[ch] = {
            "unit":    infer_unit_from_header(ch) or "",
            "min":     float(np.min(valid)) if len(valid) else float("nan"),
            "max":     float(np.max(valid)) if len(valid) else float("nan"),
            "mean":    float(np.mean(valid)) if len(valid) else float("nan"),
            "std":     float(np.std(valid)) if len(valid) else float("nan"),
            "has_nan": bool(np.any(np.isnan(arr))),
        }
    return result
