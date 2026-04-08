"""
Channel mapping system for RedByte GFM HIL Suite.

Maps generic source column names (e.g. CH1(V), Pinv) to canonical engineering
signal names (v_an, p_mech, …).

Mapping profiles are persisted in config/channel_mappings.json so the same
instrument format or simulation layout can be reused without re-entering the
mapping each time.

Usage:
    mapper = ChannelMapper()

    # Suggest a mapping automatically
    mapping = mapper.auto_suggest(dataset.raw_headers)

    # User may override specific entries
    mapping['CH1(V)'] = 'v_an'
    mapping['CH2(V)'] = 'v_bn'

    # Apply to produce a new dataset with renamed channels
    mapped = mapper.apply(dataset, mapping)

    # Persist for reuse
    mapper.save_profile('rigol_3phase_inverter', mapping)
"""

from __future__ import annotations

import json
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

_PROFILES_PATH = "config/channel_mappings.json"

# Sentinel value meaning "do not rename; keep original name"
UNMAPPED = "__unmapped__"


# ---------------------------------------------------------------------------
# Registry of canonical engineering signals
# ---------------------------------------------------------------------------

CANONICAL_SIGNALS: dict[str, dict] = {
    "v_an":   {"label": "V_an — Phase A voltage (V)",   "unit": "V",   "type": "voltage"},
    "v_bn":   {"label": "V_bn — Phase B voltage (V)",   "unit": "V",   "type": "voltage"},
    "v_cn":   {"label": "V_cn — Phase C voltage (V)",   "unit": "V",   "type": "voltage"},
    "i_a":    {"label": "I_a — Phase A current (A)",    "unit": "A",   "type": "current"},
    "i_b":    {"label": "I_b — Phase B current (A)",    "unit": "A",   "type": "current"},
    "i_c":    {"label": "I_c — Phase C current (A)",    "unit": "A",   "type": "current"},
    "freq":   {"label": "Frequency (Hz)",               "unit": "Hz",  "type": "frequency"},
    "p_mech": {"label": "Active (mechanical) power (W)", "unit": "W",  "type": "power"},
    "q":      {"label": "Reactive power (VAR)",          "unit": "VAR","type": "power"},
    "v_dc":   {"label": "DC bus voltage (V)",            "unit": "V",  "type": "voltage"},
    "i_dc":   {"label": "DC bus current (A)",            "unit": "A",  "type": "current"},
    "angle":  {"label": "Rotor angle (deg)",             "unit": "deg","type": "angle"},
}


def infer_unit_from_header(header: str) -> Optional[str]:
    """
    Attempt to infer the physical unit from a column header string.

    Examples that will match:
        "CH1(V)"  → "V"
        "I_a(A)"  → "A"
        "Freq(Hz)"→ "Hz"
        "Pinv"    → None  (no explicit unit)
    """
    lo = header.lower()
    for unit, patterns in [
        ("V",   ["(v)", "(volt)", "voltage"]),
        ("A",   ["(a)", "(amp)", "current"]),
        ("Hz",  ["(hz)", "freq"]),
        ("W",   ["(w)", "(watt)", "power"]),
        ("VAR", ["(var)", "reactive"]),
        ("s",   ["(s)", "(sec)", "time"]),
    ]:
        if any(p in lo for p in patterns):
            return unit
    return None


def auto_suggest_mapping(headers: list[str]) -> dict[str, str]:
    """
    Return a suggested mapping dict:  original_header  →  canonical_name | UNMAPPED

    Rules (in descending confidence):
      1. Exact canonical name match (case-insensitive).
      2. Known aliases from a curated list.
      3. Substring / partial matches for well-known column names.
      4. Everything else → UNMAPPED  (never silently guess CH1 = v_an).

    This function is deterministic and never mutates state.
    """
    mapping: dict[str, str] = {}

    for hdr in headers:
        lo = hdr.strip().lower()
        target = UNMAPPED

        # ── Direct canonical match ───────────────────────────────────────────
        if lo in CANONICAL_SIGNALS:
            target = lo

        # ── Voltage phase aliases ────────────────────────────────────────────
        elif lo in ("v_a", "va", "van", "v_phase_a", "ph_a_v", "vphase_a"):
            target = "v_an"
        elif lo in ("v_b", "vb", "vbn", "v_phase_b", "ph_b_v"):
            target = "v_bn"
        elif lo in ("v_c", "vc", "vcn", "v_phase_c", "ph_c_v"):
            target = "v_cn"

        # ── Current phase aliases ────────────────────────────────────────────
        elif lo in ("i_a", "ia", "i_an", "il_a", "ph_a_curr", "il1"):
            target = "i_a"
        elif lo in ("i_b", "ib", "i_bn", "il_b", "ph_b_curr", "il2"):
            target = "i_b"
        elif lo in ("i_c", "ic", "i_cn", "il_c", "ph_c_curr", "il3"):
            target = "i_c"

        # ── Frequency aliases ────────────────────────────────────────────────
        elif lo in ("frequency", "f", "freq_hz", "freq_out", "f_out"):
            target = "freq"
        elif "freq" in lo and "vsg" in lo:
            target = "freq"

        # ── Power aliases ────────────────────────────────────────────────────
        elif lo in (
            "p", "p_mech", "p_inv", "pinv", "pout", "p_out",
            "active_power", "real_power", "p_e", "power",
            "p_kw", "pkw", "p_w",
        ):
            target = "p_mech"
        elif "pinv" in lo or "p_inv" in lo:
            target = "p_mech"

        # ── Reactive power ───────────────────────────────────────────────────
        elif lo in ("q", "q_inv", "q_out", "reactive", "reactive_power",
                    "q_kvar", "qkvar", "q_var"):
            target = "q"

        # ── DC bus ───────────────────────────────────────────────────────────
        elif lo in ("vdc", "v_dc", "dc_bus", "dc_voltage", "dc_link", "vbus"):
            target = "v_dc"

        # ── Everything else: no confident mapping ────────────────────────────
        # CH1, CH2, CH3, CH4 deliberately fall through to UNMAPPED.

        mapping[hdr] = target

    return mapping


# ---------------------------------------------------------------------------
# ChannelMapper class
# ---------------------------------------------------------------------------

class ChannelMapper:
    """
    Manages channel mappings with profile persistence.

    Profiles are stored as a JSON file at _PROFILES_PATH so the same
    instrument format can be reloaded in future sessions without re-entering
    the mapping manually.
    """

    def __init__(self, profiles_path: str = _PROFILES_PATH):
        self._profiles_path = profiles_path
        self._profiles: dict[str, dict[str, str]] = {}
        self._load_profiles()

    # ── Profile persistence ──────────────────────────────────────────────────

    def _load_profiles(self) -> None:
        if os.path.isfile(self._profiles_path):
            try:
                with open(self._profiles_path, "r") as fh:
                    self._profiles = json.load(fh)
                logger.debug(
                    "Loaded %d channel-mapping profiles from %s",
                    len(self._profiles), self._profiles_path,
                )
            except Exception as exc:
                logger.warning(
                    "Could not load channel mapping profiles from '%s': %s",
                    self._profiles_path, exc,
                )
                self._profiles = {}

    def save_profile(self, name: str, mapping: dict[str, str]) -> None:
        """Persist a mapping dict under the given profile name."""
        self._profiles[name] = {k: v for k, v in mapping.items()}
        os.makedirs(os.path.dirname(self._profiles_path) or ".", exist_ok=True)
        try:
            with open(self._profiles_path, "w") as fh:
                json.dump(self._profiles, fh, indent=2)
            logger.info("Saved channel mapping profile '%s'", name)
        except Exception as exc:
            logger.error(
                "Failed to save channel mapping profile '%s': %s", name, exc
            )

    def load_profile(self, name: str) -> Optional[dict[str, str]]:
        """Return a copy of a named profile, or None if not found."""
        prof = self._profiles.get(name)
        return dict(prof) if prof is not None else None

    def list_profiles(self) -> list[str]:
        return list(self._profiles.keys())

    def delete_profile(self, name: str) -> bool:
        if name in self._profiles:
            del self._profiles[name]
            self.save_profile.__func__  # trigger rewrite
            os.makedirs(os.path.dirname(self._profiles_path) or ".", exist_ok=True)
            try:
                with open(self._profiles_path, "w") as fh:
                    json.dump(self._profiles, fh, indent=2)
            except Exception:
                pass
            return True
        return False

    # ── Suggestion ───────────────────────────────────────────────────────────

    def auto_suggest(self, headers: list[str]) -> dict[str, str]:
        """Return a suggested mapping for the given headers (no side effects)."""
        return auto_suggest_mapping(headers)

    # ── Application ──────────────────────────────────────────────────────────

    def apply(self, dataset, mapping: dict[str, str]):
        """
        Return a *new* ImportedDataset with channels renamed per mapping.

        - Channels mapped to UNMAPPED or absent from the mapping keep their
          original names (no silent drops, no silent renames).
        - If two source channels map to the same canonical target, the first
          wins and subsequent entries keep their original names (with a warning).
        - The applied mapping is recorded in the returned dataset's meta dict
          under ``'applied_mapping'``.
        """
        from src.file_ingestion import ImportedDataset
        import numpy as np

        new_channels: dict[str, np.ndarray] = {}
        used_targets: set[str] = set()

        for src_col, data_arr in dataset.channels.items():
            target = mapping.get(src_col, UNMAPPED)
            if not target or target == UNMAPPED:
                out_name = src_col
            else:
                out_name = target

            if out_name in used_targets:
                logger.warning(
                    "Mapping conflict: source '%s' → '%s' already occupied; "
                    "channel kept under original name '%s'.",
                    src_col, out_name, src_col,
                )
                out_name = src_col

            new_channels[out_name] = data_arr
            used_targets.add(out_name)

        new_meta = dict(dataset.meta)
        new_meta["applied_mapping"] = {k: v for k, v in mapping.items()}

        new_warnings = list(dataset.warnings)
        # Warn about unmapped channels so the user knows they exist
        unmapped_cols = [
            src for src in dataset.channels
            if mapping.get(src, UNMAPPED) in (UNMAPPED, "", None)
        ]
        if unmapped_cols:
            new_warnings.append(
                f"The following channel(s) are unmapped and will appear under "
                f"their original names: {unmapped_cols}"
            )

        return ImportedDataset(
            source_type=dataset.source_type,
            source_path=dataset.source_path,
            channels=new_channels,
            time=dataset.time,
            sample_rate=dataset.sample_rate,
            duration=dataset.duration,
            warnings=new_warnings,
            meta=new_meta,
            raw_headers=list(dataset.raw_headers),
        )
