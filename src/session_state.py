"""
Active session state for the GFM HIL Suite.

Provides a single, clean in-memory descriptor of whichever session the user is
currently working with — whether imported from a real file or loaded from a saved
Data Capsule.  AppShell owns one optional ActiveSession at a time; all pages that
care about the analysis context read from it.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


_SOURCE_TYPE_LABELS: dict[str, str] = {
    "rigol_csv":          "Rigol CSV",
    "simulation_excel":   "Simulation Excel",
    "data_capsule_json":  "Data Capsule",
    "live":               "Live Telemetry",
}

#: Sentinel value used in channel mapping for channels that were NOT renamed.
_UNMAPPED = "__unmapped__"


@dataclass
class ActiveSession:
    """
    Descriptor for the session currently open in the application.

    Attributes:
        capsule:           Full Data Capsule dict (meta + frames [+ import_meta]).
        label:             Display name (session_id or filename stem).
        source_type:       'rigol_csv' | 'simulation_excel' |
                           'data_capsule_json' | 'live'
        source_path:       Absolute path to the source file (empty for live).
        sample_rate:       Estimated sample rate in Hz (0.0 if unknown).
        duration:          Total captured duration in seconds.
        row_count:         Number of rows / frames in the session.
        mapped_channels:   Channels renamed to canonical engineering names.
        unmapped_channels: Channels that kept their original source names.
        warnings:          User-visible issues raised during ingest/mapping.
        imported_at:       Unix timestamp when this session was created.
        is_imported:       True when session originated from a file import.
    """

    capsule:           dict
    label:             str
    source_type:       str
    source_path:       str
    sample_rate:       float
    duration:          float
    row_count:         int
    mapped_channels:   list[str] = field(default_factory=list)
    unmapped_channels: list[str] = field(default_factory=list)
    warnings:          list[str] = field(default_factory=list)
    imported_at:       float     = field(default_factory=time.time)
    is_imported:       bool      = False

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def from_capsule(
        cls,
        capsule: dict,
        label: Optional[str] = None,
    ) -> "ActiveSession":
        """
        Build an ActiveSession from a Data Capsule dict.

        Works for both imported files (has ``import_meta`` block) and plain
        saved sessions (no ``import_meta``).
        """
        meta        = capsule.get("meta", {})
        import_meta = capsule.get("import_meta", {})
        frames      = capsule.get("frames", [])

        # --- basic identity -----------------------------------------------
        session_label = label or meta.get("session_id", "session")

        # --- row count / duration -----------------------------------------
        row_count = (
            import_meta.get("original_row_count")
            or meta.get("frame_count")
            or len(frames)
        )
        row_count = int(row_count) if row_count else len(frames)

        duration = float(meta.get("duration", 0.0))
        if not duration and len(frames) >= 2:
            t0 = frames[0].get("ts", 0.0)
            t1 = frames[-1].get("ts", 0.0)
            duration = float(t1 - t0)

        # --- sample rate --------------------------------------------------
        sample_rate = float(
            import_meta.get("original_sample_rate")
            or meta.get("sample_rate", 0.0)
            or 0.0
        )

        # --- source provenance --------------------------------------------
        source_type = (
            import_meta.get("source_type")
            or meta.get("source_type", "data_capsule_json")
        )
        source_path = import_meta.get("source_path") or meta.get("source_path", "")

        # --- channel classification ---------------------------------------
        applied_mapping: dict = import_meta.get("applied_mapping", {})
        all_channels: list[str] = sorted(meta.get("channels", []))

        if applied_mapping:
            mapped   = [v for v in applied_mapping.values()
                        if v and v != _UNMAPPED]
            unmapped = [k for k, v in applied_mapping.items()
                        if v == _UNMAPPED]
        elif all_channels:
            mapped   = all_channels
            unmapped = []
        else:
            mapped   = []
            unmapped = []

        warnings    = list(import_meta.get("warnings", []))
        is_imported = "import_meta" in capsule

        return cls(
            capsule           = capsule,
            label             = session_label,
            source_type       = source_type,
            source_path       = source_path,
            sample_rate       = sample_rate,
            duration          = duration,
            row_count         = row_count,
            mapped_channels   = mapped,
            unmapped_channels = unmapped,
            warnings          = warnings,
            imported_at       = time.time(),
            is_imported       = is_imported,
        )

    # ------------------------------------------------------------------
    # Convenience properties
    # ------------------------------------------------------------------

    @property
    def has_warnings(self) -> bool:
        """True if there are any user-visible warnings on this session."""
        return len(self.warnings) > 0

    @property
    def channel_count(self) -> int:
        """Total number of channels (mapped + unmapped)."""
        return len(self.mapped_channels) + len(self.unmapped_channels)

    @property
    def source_filename(self) -> str:
        """Filename portion of source_path, or label if path is empty."""
        if self.source_path:
            return Path(self.source_path).name
        return self.label

    @property
    def source_type_display(self) -> str:
        """Human-readable label for the source_type."""
        return _SOURCE_TYPE_LABELS.get(self.source_type, self.source_type)

    @property
    def duration_display(self) -> str:
        """Duration formatted as 'X.XXX s'."""
        return f"{self.duration:.3f} s"

    @property
    def sample_rate_display(self) -> str:
        """Sample rate formatted as 'X Hz' or '— Hz' if unknown."""
        if self.sample_rate > 0:
            return f"{self.sample_rate:,.0f} Hz"
        return "— Hz"

    @property
    def row_count_display(self) -> str:
        """Row count formatted with thousands separator."""
        return f"{self.row_count:,}"
