"""
Derived engineering channels for imported and replayed sessions.

The core rule is simple: only derive line-to-line voltages when the required
phase-to-neutral source channels actually exist. No missing source channel is
ever fabricated here.
"""

from __future__ import annotations

from dataclasses import replace

import numpy as np

from src.file_ingestion import ImportedDataset


LINE_TO_LINE_CHANNELS: dict[str, tuple[str, str, str]] = {
    "v_ab": ("v_an", "v_bn", "V_ab"),
    "v_bc": ("v_bn", "v_cn", "V_bc"),
    "v_ca": ("v_cn", "v_an", "V_ca"),
}


def compute_line_to_line_channels(
    channels: dict[str, np.ndarray],
) -> dict[str, np.ndarray]:
    """
    Return any line-to-line voltage channels derivable from *channels*.

    Existing direct-measurement line-to-line channels are never overwritten.
    """
    derived: dict[str, np.ndarray] = {}

    for target, (pos_key, neg_key, _label) in LINE_TO_LINE_CHANNELS.items():
        if target in channels:
            continue
        if pos_key not in channels or neg_key not in channels:
            continue

        pos = np.asarray(channels[pos_key], dtype=np.float64)
        neg = np.asarray(channels[neg_key], dtype=np.float64)
        if pos.shape != neg.shape or pos.size == 0:
            continue

        derived[target] = pos - neg

    return derived


def derive_dataset_channels(dataset: ImportedDataset) -> ImportedDataset:
    """
    Return a dataset with derived line-to-line voltage channels appended.
    """
    derived = compute_line_to_line_channels(dataset.channels)
    present_targets = {
        target
        for target, (pos_key, neg_key, _label) in LINE_TO_LINE_CHANNELS.items()
        if target in dataset.channels and pos_key in dataset.channels and neg_key in dataset.channels
    }
    derived_targets = set(derived) | present_targets
    if not derived_targets:
        return dataset

    new_channels = dict(dataset.channels)
    new_channels.update(derived)

    meta = dict(dataset.meta)
    existing = list(meta.get("derived_channels", []))
    meta["derived_channels"] = sorted(set(existing) | derived_targets)

    return replace(dataset, channels=new_channels, meta=meta)


def ensure_capsule_derived_channels(capsule: dict) -> list[str]:
    """
    Mutate *capsule* in place to append derived line-to-line frame values.

    Returns the list of derived channels that were added.
    """
    frames = capsule.get("frames", [])
    if not frames:
        return []

    added: list[str] = []
    meta = capsule.setdefault("meta", {})
    import_meta = capsule.setdefault("import_meta", {})

    for target, (pos_key, neg_key, _label) in LINE_TO_LINE_CHANNELS.items():
        if any(target in frame for frame in frames):
            continue

        pos_vals: list[float] = []
        neg_vals: list[float] = []
        derivable = True

        for frame in frames:
            if pos_key not in frame or neg_key not in frame:
                derivable = False
                break
            pos_vals.append(float(frame[pos_key]))
            neg_vals.append(float(frame[neg_key]))

        if not derivable:
            continue

        derived_vals = np.asarray(pos_vals, dtype=np.float64) - np.asarray(
            neg_vals, dtype=np.float64
        )
        for frame, value in zip(frames, derived_vals):
            frame[target] = float(value)
        added.append(target)

    if not added:
        return []

    meta_channels = list(meta.get("channels", []))
    meta["channels"] = sorted(set(meta_channels) | set(added))

    existing = list(import_meta.get("derived_channels", []))
    import_meta["derived_channels"] = sorted(set(existing) | set(added))
    return added
