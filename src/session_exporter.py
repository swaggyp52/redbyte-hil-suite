"""
session_exporter.py — truth-first export engine for the GFM HIL Suite.

All exports operate on an in-memory Data Capsule dict, not a file path.
This means imported data and recorded sessions export identically without
requiring the data to be saved to disk first.

Truthfulness rules enforced here:
  - CSV export only writes columns that actually appear in frames.
    Missing channels get an empty cell, not a zero.
  - HTML report only plots waveform channels that have real data.
  - Analysis JSON marks missing sections as null, never invents values.
  - Events export shows only what the detector found; empty = no events.
"""

from __future__ import annotations

import base64
import csv
import io
import json
import logging
import math
import os
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.event_detector import DetectedEvent

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _session_meta(capsule: dict) -> dict:
    """Return the unified metadata dict for a capsule."""
    meta = capsule.get("meta", {})
    imp  = capsule.get("import_meta", {})
    frames = capsule.get("frames", [])
    # Prefer import_meta values (richer); fall back to meta
    return {
        "session_id":   meta.get("session_id", "unknown"),
        "source_type":  imp.get("source_type") or meta.get("source_type", "unknown"),
        "source_path":  imp.get("source_path") or meta.get("source_path", ""),
        "frame_count":  meta.get("frame_count", len(frames)),
        "duration_s":   imp.get("duration_s")  or meta.get("duration_s", 0.0),
        "sample_rate":  imp.get("original_sample_rate") or meta.get("sample_rate_estimate", 0),
        "channels":     meta.get("channels", []),
        "warnings":     list(imp.get("warnings", [])),
        "applied_mapping": dict(imp.get("applied_mapping", {})),
        "raw_headers":  list(imp.get("raw_headers", [])),
    }


def _actual_frame_columns(capsule: dict) -> list[str]:
    """Return the sorted set of field names that genuinely appear in frames."""
    seen: set[str] = set()
    for f in capsule.get("frames", []):
        seen.update(f.keys())
    return sorted(seen)


def _write_csv_preamble(fh: io.TextIOWrapper, capsule: dict) -> None:
    m = _session_meta(capsule)
    fh.write("# RedByte GFM HIL Suite — Session Export\n")
    fh.write(f"# Generated:    {_now_str()}\n")
    fh.write(f"# Session ID:   {m['session_id']}\n")
    fh.write(f"# Source type:  {m['source_type']}\n")
    if m["source_path"]:
        fh.write(f"# Source file:  {m['source_path']}\n")
    fh.write(f"# Frames:       {m['frame_count']}\n")
    if m["sample_rate"]:
        fh.write(f"# Sample rate:  {m['sample_rate']} Hz\n")
    if m["duration_s"]:
        fh.write(f"# Duration:     {m['duration_s']:.3f} s\n")
    if m["warnings"]:
        fh.write(f"# Import warnings ({len(m['warnings'])}):\n")
        for w in m["warnings"]:
            fh.write(f"#   {w}\n")
    fh.write("#\n")


# ─────────────────────────────────────────────────────────────────────────────
# Public exports
# ─────────────────────────────────────────────────────────────────────────────

def export_session_csv(capsule: dict, path: str) -> dict:
    """
    Export normalized session frames to CSV.

    Only columns that actually appear in the frame data are written.
    Frames that lack a column for which other frames have data get an empty
    cell — not a zero.  This preserves the truthfulness invariant.

    Returns a stats dict: {"format", "rows", "columns", "path"}.
    """
    frames = capsule.get("frames", [])
    if not frames:
        raise ValueError("capsule contains no frames to export")

    cols = _actual_frame_columns(capsule)
    os.makedirs(Path(path).parent, exist_ok=True)

    with open(path, "w", newline="", encoding="utf-8") as fh:
        _write_csv_preamble(fh, capsule)
        writer = csv.DictWriter(
            fh, fieldnames=cols, extrasaction="ignore", restval=""
        )
        writer.writeheader()
        for frame in frames:
            writer.writerow(frame)

    stats = {"format": "session_csv", "rows": len(frames),
             "columns": cols, "path": path}
    logger.info("session CSV exported: %d rows, %d columns → %s",
                len(frames), len(cols), path)
    return stats


def export_events_csv(
    events: list,
    annotations: dict | None,
    path: str,
) -> dict:
    """
    Export the detected event list to CSV.

    Each row is one DetectedEvent, with user annotations appended when present.
    If *events* is empty, writes a header-only file (truthful — no events found).

    Returns a stats dict: {"format", "rows", "path"}.
    """
    annotations = annotations or {}
    cols = [
        "kind", "severity", "ts_start", "ts_end", "duration_s",
        "channel", "description", "confidence",
        "metrics_json", "note",
    ]
    os.makedirs(Path(path).parent, exist_ok=True)

    def _ann_key(ts: float) -> str:
        return f"{ts:.6f}"

    with open(path, "w", newline="", encoding="utf-8") as fh:
        fh.write("# RedByte GFM HIL Suite — Detected Events Export\n")
        fh.write(f"# Generated: {_now_str()}\n")
        fh.write(f"# Events:    {len(events)}\n")
        fh.write("#\n")
        writer = csv.DictWriter(fh, fieldnames=cols)
        writer.writeheader()
        for evt in events:
            duration = evt.ts_end - evt.ts_start
            writer.writerow({
                "kind":         evt.kind,
                "severity":     evt.severity,
                "ts_start":     f"{evt.ts_start:.6f}",
                "ts_end":       f"{evt.ts_end:.6f}",
                "duration_s":   f"{duration:.4f}",
                "channel":      evt.channel,
                "description":  evt.description,
                "confidence":   f"{evt.confidence:.3f}",
                "metrics_json": json.dumps(evt.metrics),
                "note":         annotations.get(_ann_key(evt.ts_start), ""),
            })

    stats = {"format": "events_csv", "rows": len(events), "path": path}
    logger.info("events CSV exported: %d events → %s", len(events), path)
    return stats


def build_analysis_json(
    capsule: dict,
    events: list | None,
    compliance_results: list[dict] | None,
) -> dict:
    """
    Build an analysis summary dict (does not write to disk).

    The caller may serialize with json.dump or pass to generate_html_report.
    Returns None for any section that has no data — never fabricates.
    """
    m = _session_meta(capsule)
    events = events or []

    by_severity: dict[str, int] = {}
    for evt in events:
        by_severity[evt.severity] = by_severity.get(evt.severity, 0) + 1

    evt_dicts = []
    for evt in events:
        d = {
            "kind":        evt.kind,
            "severity":    evt.severity,
            "ts_start":    evt.ts_start,
            "ts_end":      evt.ts_end,
            "duration_s":  round(evt.ts_end - evt.ts_start, 4),
            "channel":     evt.channel,
            "description": evt.description,
            "confidence":  evt.confidence,
            "metrics":     evt.metrics,
        }
        evt_dicts.append(d)

    compliance_section = None
    if compliance_results is not None:
        passed = sum(1 for r in compliance_results if r.get("passed"))
        total  = len(compliance_results)
        compliance_section = {
            "passed":  passed,
            "total":   total,
            "pct":     int(100 * passed / total) if total else 0,
            "results": compliance_results,
        }

    # Channel mapping: only include entries that were actually applied
    mapping = {k: v for k, v in m["applied_mapping"].items() if v}

    return {
        "generated":     _now_str(),
        "session": {
            "session_id":  m["session_id"],
            "source_type": m["source_type"],
            "source_path": m["source_path"],
            "frame_count": m["frame_count"],
            "duration_s":  m["duration_s"],
            "sample_rate_hz": m["sample_rate"],
            "channels":    m["channels"],
        },
        "channel_mapping": mapping if mapping else None,
        "warnings":        m["warnings"] if m["warnings"] else None,
        "events": {
            "count":       len(events),
            "by_severity": by_severity,
            "list":        evt_dicts,
        },
        "compliance": compliance_section,
    }


def export_analysis_json(
    capsule: dict,
    events: list | None,
    compliance_results: list[dict] | None,
    path: str,
) -> dict:
    """Write analysis summary JSON to disk and return the summary dict."""
    summary = build_analysis_json(capsule, events, compliance_results)
    os.makedirs(Path(path).parent, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2)
    logger.info("analysis JSON exported → %s", path)
    return summary


# ─────────────────────────────────────────────────────────────────────────────
# HTML report
# ─────────────────────────────────────────────────────────────────────────────

_WAVEFORM_GROUPS = [
    ("Voltage Waveforms",  ["v_an", "v_bn", "v_cn"]),
    ("Current Waveforms",  ["i_a",  "i_b",  "i_c"]),
    ("Frequency",          ["freq"]),
]

_SEVERITY_COLOR = {
    "critical": "#ef4444",
    "warning":  "#f59e0b",
    "info":     "#64748b",
}


def _plot_group_base64(
    frames: list[dict],
    channels: list[str],
    title: str,
    y_label: str,
) -> str | None:
    """
    Plot the given channels from frames.  Returns base64-encoded PNG, or None
    if no channel in the group has actual data.
    """
    try:
        import warnings as _w
        _w.filterwarnings("ignore", category=DeprecationWarning)
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import numpy as np
    except ImportError:
        logger.warning("matplotlib not available — skipping plot")
        return None

    ts_raw = [f.get("ts") for f in frames]
    if not ts_raw or ts_raw[0] is None:
        return None
    t0 = ts_raw[0]
    t  = [v - t0 if v is not None else float("nan") for v in ts_raw]

    plotted_any = False
    fig, ax = plt.subplots(figsize=(9, 2.8))
    colors = ["#38bdf8", "#34d399", "#fb923c", "#a78bfa", "#f472b6", "#fbbf24"]

    for idx, ch in enumerate(channels):
        raw = [f.get(ch) for f in frames]
        if all(v is None for v in raw):
            continue  # channel absent — do NOT plot zeros
        y = np.array([float(v) if v is not None else float("nan") for v in raw])
        ax.plot(t, y, label=ch, color=colors[idx % len(colors)], linewidth=0.9)
        plotted_any = True

    if not plotted_any:
        plt.close(fig)
        return None

    ax.set_title(title, fontsize=11, color="#e6e9ef", pad=4)
    ax.set_xlabel("Time (s)", fontsize=9, color="#94a3b8")
    ax.set_ylabel(y_label, fontsize=9, color="#94a3b8")
    ax.legend(fontsize=8, loc="upper right")
    ax.grid(True, alpha=0.2, color="#334155")
    ax.set_facecolor("#0f1115")
    fig.patch.set_facecolor("#0f1115")
    ax.tick_params(colors="#94a3b8", labelsize=8)
    for spine in ax.spines.values():
        spine.set_edgecolor("#334155")

    buf = io.BytesIO()
    fig.tight_layout()
    fig.savefig(buf, format="png", dpi=90, bbox_inches="tight",
                facecolor="#0f1115")
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def generate_html_report(
    capsule: dict,
    events: list | None,
    compliance_results: list[dict] | None,
    output_dir: str,
) -> str:
    """
    Generate a self-contained HTML engineering report and return its path.

    The report includes:
      - Source file and dataset metadata
      - Channel mapping (from import_meta)
      - Import warnings (if any)
      - Waveform plots (only for channels that have real data)
      - Detected events table
      - IEEE 2800 compliance scorecard (if compliance was run)

    No data is fabricated for absent channels.
    """
    m = _session_meta(capsule)
    events = events or []
    frames = capsule.get("frames", [])

    # ── Build plots ──────────────────────────────────────────────────────────
    plots_html = ""
    for group_title, channels in _WAVEFORM_GROUPS:
        y_label = "Voltage (V)" if "Voltage" in group_title else (
            "Current (A)" if "Current" in group_title else "Frequency (Hz)"
        )
        b64 = _plot_group_base64(frames, channels, group_title, y_label)
        if b64:
            plots_html += (
                f'<img src="data:image/png;base64,{b64}" '
                f'style="width:100%;max-width:860px;margin-bottom:12px;'
                f'border:1px solid #1e293b;border-radius:4px;" />\n'
            )

    # ── Compliance section ───────────────────────────────────────────────────
    if compliance_results is not None:
        passed     = sum(1 for r in compliance_results if r.get("status") == "PASS")
        applicable = sum(1 for r in compliance_results if r.get("status") in {"PASS", "FAIL"})
        na_count   = sum(1 for r in compliance_results if r.get("status") == "N/A")
        total      = len(compliance_results)
        pct        = int(100 * passed / applicable) if applicable else 0
        na_note    = f" · {na_count} N/A" if na_count else ""
        grade_color = "#10b981" if passed == applicable and applicable > 0 else (
            "#f59e0b" if passed > 0 else "#ef4444"
        )
        rows_parts = []
        for r in compliance_results:
            status = r.get('status') or ('PASS' if r.get('passed') else 'FAIL')
            r_color  = {"PASS": "#10b981", "FAIL": "#ef4444", "N/A": "#64748b"}.get(status, "#64748b")
            r_result = status
            rows_parts.append(
                f"<tr>"
                f"<td>{r['name']}</td>"
                f"<td style='color:{r_color};font-weight:700'>{r_result}</td>"
                f"<td>{r.get('details','')}</td>"
                f"</tr>"
            )
        rows = "".join(rows_parts)
        compliance_html = f"""
<h2>Standards-Inspired Engineering Checks</h2>
<p style='font-size:16px;color:{grade_color};font-weight:700;'>
  {passed}/{applicable} applicable checks passed &nbsp; ({pct}%){na_note}
</p>
<table>
  <tr><th>Rule</th><th>Result</th><th>Details</th></tr>
  {rows}
</table>"""
    else:
        compliance_html = (
            "<h2>IEEE 2800 Compliance</h2>"
            "<p class='muted'>Compliance check was not run for this session.</p>"
        )

    # ── Events section ───────────────────────────────────────────────────────
    if events:
        n_crit = sum(1 for e in events if e.severity == "critical")
        n_warn = sum(1 for e in events if e.severity == "warning")
        n_info = sum(1 for e in events if e.severity == "info")
        evt_row_parts = []
        for e in events:
            sev_color = _SEVERITY_COLOR.get(e.severity, "#fff")
            duration  = round(e.ts_end - e.ts_start, 3)
            evt_row_parts.append(
                f"<tr>"
                f"<td>{e.kind}</td>"
                f"<td style='color:{sev_color};font-weight:600'>{e.severity}</td>"
                f"<td>{e.ts_start:.3f}</td>"
                f"<td>{duration:.3f}</td>"
                f"<td>{e.channel}</td>"
                f"<td>{e.description}</td>"
                f"</tr>"
            )
        evt_rows = "".join(evt_row_parts)
        events_html = f"""
<h2>Detected Events</h2>
<p>
  <span style='color:#ef4444;font-weight:700;'>{n_crit} critical</span> &nbsp;
  <span style='color:#f59e0b;font-weight:700;'>{n_warn} warning</span> &nbsp;
  <span style='color:#64748b;'>{n_info} info</span>
</p>
<table>
  <tr><th>Kind</th><th>Severity</th><th>Start (s)</th>
      <th>Duration (s)</th><th>Channel</th><th>Description</th></tr>
  {evt_rows}
</table>"""
    else:
        events_html = (
            "<h2>Detected Events</h2>"
            "<p class='muted'>No power-quality events detected in this session.</p>"
        )

    # ── Channel mapping section ───────────────────────────────────────────────
    mapping = {k: v for k, v in m["applied_mapping"].items() if v}
    if mapping:
        map_rows = "".join(
            f"<tr><td class='mono'>{src}</td><td class='mono'>{dst}</td></tr>"
            for src, dst in sorted(mapping.items())
        )
        mapping_html = f"""
<h2>Channel Mapping</h2>
<table>
  <tr><th>Source Column</th><th>Canonical Name</th></tr>
  {map_rows}
</table>"""
    else:
        mapping_html = ""

    # ── Warnings section ────────────────────────────────────────────────────
    if m["warnings"]:
        warn_items = "".join(f"<li>{w}</li>" for w in m["warnings"])
        warnings_html = f"""
<h2>Import Warnings</h2>
<ul style='color:#f59e0b;'>{warn_items}</ul>"""
    else:
        warnings_html = ""

    # ── Dataset metadata table ────────────────────────────────────────────────
    meta_rows = f"""
      <tr><td>Session ID</td><td class='mono'>{m['session_id']}</td></tr>
      <tr><td>Source type</td><td>{m['source_type'].replace('_',' ').title()}</td></tr>
      <tr><td>Source file</td><td class='mono'>{m['source_path'] or '—'}</td></tr>
      <tr><td>Frames</td><td>{m['frame_count']:,}</td></tr>
      <tr><td>Duration</td><td>{m['duration_s']:.3f} s</td></tr>
      <tr><td>Sample rate</td><td>{m['sample_rate']} Hz</td></tr>
      <tr><td>Channels present</td>
          <td class='mono'>{', '.join(m['channels']) or '—'}</td></tr>
    """

    # ── Assemble report ──────────────────────────────────────────────────────
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <title>GFM Analysis Report — {m['session_id']}</title>
  <style>
    body {{
      font-family: 'Segoe UI', Arial, sans-serif;
      background: #0f1115; color: #e6e9ef;
      margin: 0; padding: 24px 32px;
    }}
    h1 {{ color: #f8fafc; font-size: 20px; margin-bottom: 2px; }}
    h2 {{ color: #94a3b8; font-size: 14px; text-transform: uppercase;
           letter-spacing: .06em; margin: 28px 0 8px; border-bottom: 1px solid #1e293b;
           padding-bottom: 4px; }}
    table {{ border-collapse: collapse; width: 100%; max-width: 860px;
              font-size: 13px; margin-bottom: 16px; }}
    th {{ background: #1e293b; color: #94a3b8; font-weight: 600;
           text-align: left; padding: 6px 10px; }}
    td {{ border-top: 1px solid #1e293b; padding: 5px 10px; }}
    .mono {{ font-family: 'Consolas', monospace; font-size: 12px; }}
    .muted {{ color: #475569; font-size: 13px; }}
    .badge {{ display: inline-block; padding: 2px 8px; border-radius: 3px;
               font-size: 11px; font-weight: 700; }}
    footer {{ margin-top: 40px; color: #334155; font-size: 11px; }}
  </style>
</head>
<body>
  <h1>GFM HIL Analysis Report</h1>
  <p class='muted'>Generated {_now_str()} by RedByte GFM HIL Suite</p>

  <h2>Dataset</h2>
  <table>{meta_rows}</table>

  {mapping_html}
  {warnings_html}

  {"<h2>Waveforms</h2>" if plots_html else ""}
  {plots_html}

  {compliance_html}
  {events_html}

  <footer>
    RedByte GFM HIL Suite &nbsp;·&nbsp; Gannon University Senior Design 2025–2026<br/>
    Analysis is based solely on measured samples. Absent channels are omitted,
    not fabricated.
  </footer>
</body>
</html>"""

    Path(output_dir).mkdir(parents=True, exist_ok=True)
    ts_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    sid = m["session_id"].replace(" ", "_")
    out_path = str(Path(output_dir) / f"report_{sid}_{ts_str}.html")
    Path(out_path).write_text(html, encoding="utf-8")
    logger.info("HTML report generated → %s", out_path)
    return out_path


# ─────────────────────────────────────────────────────────────────────────────
# Quick Export — no QFileDialog, writes to artifacts/evidence_exports/
# ─────────────────────────────────────────────────────────────────────────────

def _write_json(path: Path, payload) -> str:
    """Write *payload* to *path* as pretty-printed JSON.  Returns path string."""
    import math as _math

    def _default(v):
        if hasattr(v, "item"):
            try:
                return v.item()
            except Exception:
                pass
        if isinstance(v, set):
            return sorted(v)
        if isinstance(v, Path):
            return str(v)
        if isinstance(v, float) and (_math.isnan(v) or _math.isinf(v)):
            return None
        return str(v)

    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=_default),
        encoding="utf-8",
    )
    return str(path.resolve())



def quick_export(
    capsule: dict,
    events: list | None = None,
    compliance_results: list[dict] | None = None,
    base_dir: str = "artifacts/evidence_exports",
    preview_csv_max_rows: int = 5000,
) -> dict:
    """
    Write a complete evidence package to a timestamped subfolder WITHOUT a
    QFileDialog.  Designed to be non-blocking for large files.

    Returns a dict with:
        export_dir   — absolute path to the created folder
        artifacts    — list of {name, path, size_bytes, description}
        session_id   — session identifier string
        timestamp    — ISO timestamp string
    """
    m = _session_meta(capsule)
    sid = m["session_id"].replace(" ", "_").replace("/", "-")
    ts_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    export_dir = Path(base_dir) / f"{sid}_{ts_str}"
    export_dir.mkdir(parents=True, exist_ok=True)

    artifacts: list[dict] = []

    def _add(name: str, path: Path, description: str) -> None:
        size = path.stat().st_size if path.exists() else 0
        artifacts.append({
            "name":        name,
            "path":        str(path.resolve()),
            "size_bytes":  size,
            "description": description,
        })
        logger.info("quick_export artifact: %s (%d bytes)", path.name, size)

    # 1. HTML report
    try:
        html_path_str = generate_html_report(
            capsule, events, compliance_results, output_dir=str(export_dir)
        )
        _add("HTML Report", Path(html_path_str), "Self-contained engineering analysis report")
    except Exception as exc:
        logger.warning("quick_export HTML report failed: %s", exc)

    # 2. Waveform PNG (phase voltages)
    try:
        frames = capsule.get("frames", [])
        _phase_chs = ["v_an", "v_bn", "v_cn"]
        b64_phase = _plot_group_base64(frames, _phase_chs, "Phase Voltages", "Voltage (V)")
        if b64_phase:
            img_path = export_dir / "waveform_phase.png"
            import base64 as _b64
            img_path.write_bytes(_b64.b64decode(b64_phase))
            _add("Phase Voltage PNG", img_path, "Phase-to-neutral voltage waveforms")
    except Exception as exc:
        logger.warning("quick_export phase PNG failed: %s", exc)

    # 3. Line-to-line PNG
    try:
        _line_chs = ["v_ab", "v_bc", "v_ca"]
        b64_line = _plot_group_base64(frames, _line_chs, "Line-to-Line Voltages", "Voltage (V)")
        if b64_line:
            img_path = export_dir / "waveform_line.png"
            img_path.write_bytes(_b64.b64decode(b64_line))
            _add("Line-to-Line Voltage PNG", img_path, "Line-to-line voltage waveforms")
    except Exception as exc:
        logger.warning("quick_export line PNG failed: %s", exc)

    # 4. Metrics JSON
    try:
        from src.session_analysis import compute_session_metrics
        from src.event_detector import detect_events as _detect_events
        from src.session_analysis import dataset_for_analysis
        ev_list = events if events is not None else []
        metrics_payload = compute_session_metrics(capsule, events=ev_list)
        metrics_path = export_dir / "metrics.json"
        _write_json(metrics_path, metrics_payload)
        _add("Metrics JSON", metrics_path, "Session engineering metrics summary")
    except Exception as exc:
        logger.warning("quick_export metrics JSON failed: %s", exc)

    # 5. Compliance JSON
    try:
        if compliance_results is not None:
            comp_path = export_dir / "compliance.json"
            _write_json(comp_path, compliance_results)
            _add("Compliance JSON", comp_path, "Standards-inspired check results")
    except Exception as exc:
        logger.warning("quick_export compliance JSON failed: %s", exc)

    # 6. Events JSON
    try:
        ev_list = events or []
        events_path = export_dir / "events.json"
        _write_json(events_path, [
            {
                "kind": e.kind, "severity": e.severity,
                "ts_start": e.ts_start, "ts_end": e.ts_end,
                "channel": e.channel, "description": e.description,
                "metrics": e.metrics,
            }
            for e in ev_list
        ])
        _add("Events JSON", events_path, "Detected power-quality events")
    except Exception as exc:
        logger.warning("quick_export events JSON failed: %s", exc)

    # 7. Metadata JSON
    try:
        meta_path = export_dir / "metadata.json"
        _write_json(meta_path, {
            "exported_at":    datetime.now().isoformat(),
            "session_id":     m["session_id"],
            "source_type":    m["source_type"],
            "source_path":    m["source_path"],
            "frame_count":    m["frame_count"],
            "duration_s":     m["duration_s"],
            "sample_rate_hz": m["sample_rate"],
            "channels":       m["channels"],
            "warnings":       m["warnings"],
            "applied_mapping": m["applied_mapping"],
        })
        _add("Metadata JSON", meta_path, "Session and import provenance")
    except Exception as exc:
        logger.warning("quick_export metadata JSON failed: %s", exc)

    # 8. Preview CSV (capped at preview_csv_max_rows)
    try:
        frames_all = capsule.get("frames", [])
        preview_frames = frames_all[:preview_csv_max_rows] if len(frames_all) > preview_csv_max_rows else frames_all
        if preview_frames:
            preview_capsule = dict(capsule)
            preview_capsule["frames"] = preview_frames
            csv_path = export_dir / "preview.csv"
            export_session_csv(preview_capsule, str(csv_path))
            note = f"Capped at {preview_csv_max_rows:,} rows" if len(frames_all) > preview_csv_max_rows else ""
            _add("Preview CSV", csv_path, f"Session data preview{' — ' + note if note else ''}")
    except Exception as exc:
        logger.warning("quick_export preview CSV failed: %s", exc)

    total_bytes = sum(a["size_bytes"] for a in artifacts)
    logger.info(
        "quick_export complete: %d artifacts, %d bytes → %s",
        len(artifacts), total_bytes, export_dir,
    )
    return {
        "export_dir":  str(export_dir.resolve()),
        "artifacts":   artifacts,
        "session_id":  m["session_id"],
        "timestamp":   datetime.now().isoformat(),
        "total_bytes": total_bytes,
    }
