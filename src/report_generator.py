"""
Generate evidence reports and export bundles from recorded analysis sessions.

This module is intentionally offline-first:
all metrics, compliance results, events, and plots are derived from recorded
session data or imported files. It does not fabricate missing channels.
"""

from __future__ import annotations

import json
import math
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from src.analysis import AnalysisEngine
from src.compliance_checker import available_profiles, evaluate_session
from src.derived_channels import ensure_capsule_derived_channels
from src.event_detector import DetectedEvent
from src.session_analysis import APP_VERSION, compute_session_metrics, dataset_for_analysis, events_for_capsule


_PHASE_CHANNELS = ("v_an", "v_bn", "v_cn")
_LINE_CHANNELS = ("v_ab", "v_bc", "v_ca")
_CURRENT_CHANNELS = ("i_a", "i_b", "i_c")
_DEFAULT_PREVIEW_CSV_ROWS = 50_000
_COLORS = {
    "v_an": "#f97316",
    "v_bn": "#3b82f6",
    "v_cn": "#22c55e",
    "v_ab": "#f97316",
    "v_bc": "#3b82f6",
    "v_ca": "#22c55e",
    "i_a": "#f97316",
    "i_b": "#3b82f6",
    "i_c": "#22c55e",
    "freq": "#a78bfa",
    "p_mech": "#38bdf8",
    "v_dc": "#fbbf24",
}


def _profile_label(profile: str) -> str:
    for item in available_profiles():
        if item.get("id") == profile:
            return str(item.get("label", profile))
    return profile


def _fmt_value(value: Any, digits: int = 3) -> str:
    if value is None:
        return "N/A"
    if isinstance(value, str):
        return value
    if isinstance(value, bool):
        return "PASS" if value else "FAIL"
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return str(value)
    if math.isnan(numeric) or math.isinf(numeric):
        return "N/A"
    return f"{numeric:.{digits}f}"


def _json_default(value: Any) -> Any:
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            pass
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, set):
        return sorted(value)
    return str(value)


def _write_json(path: Path, payload: Any) -> str:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=_json_default),
        encoding="utf-8",
    )
    return str(path.resolve())


def _safe_capsule_copy(capsule: dict) -> dict:
    return {
        "meta": dict(capsule.get("meta", {})),
        "import_meta": dict(capsule.get("import_meta", {})),
        "events": list(capsule.get("events", [])),
        "frames": [dict(frame) for frame in capsule.get("frames", [])],
    }


def _write_dataset_csv(
    dataset,
    capsule: dict,
    path: Path,
    *,
    include_full_resolution: bool = False,
    max_preview_rows: int = _DEFAULT_PREVIEW_CSV_ROWS,
) -> dict:
    del capsule

    total_rows = int(dataset.row_count)
    indices = np.arange(total_rows, dtype=np.int64)
    mode = "full_resolution"
    note = "Full-resolution normalized CSV export."
    if total_rows > max_preview_rows and not include_full_resolution:
        indices = np.unique(
            np.round(np.linspace(0, total_rows - 1, max_preview_rows)).astype(np.int64)
        )
        mode = "preview_downsampled"
        note = (
            f"Preview CSV downsampled to {len(indices):,} rows for package size; "
            "metrics computed on full-resolution data."
        )

    with open(path, "w", newline="", encoding="utf-8") as handle:
        handle.write("# VSM Evidence Workbench - Normalized Data Export\n")
        handle.write(f"# Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}\n")
        handle.write(f"# Source file: {dataset.source_path}\n")
        handle.write(f"# Samples: {dataset.row_count}\n")
        handle.write(f"# CSV mode: {mode}\n")
        handle.write(f"# Note: {note}\n")
        if dataset.sample_rate:
            handle.write(f"# Sample rate: {dataset.sample_rate} Hz\n")
        handle.write("#\n")

        columns = ["ts"] + sorted(dataset.channels.keys())
        try:
            import pandas as pd

            data = {"ts": np.asarray(dataset.time, dtype=np.float64)[indices]}
            for channel in columns[1:]:
                data[channel] = np.asarray(dataset.channels[channel], dtype=np.float64)[indices]
            pd.DataFrame(data, columns=columns).to_csv(handle, index=False)
        except Exception:
            handle.write(",".join(columns) + "\n")
            matrix = np.column_stack(
                [np.asarray(dataset.time, dtype=np.float64)[indices]]
                + [np.asarray(dataset.channels[channel], dtype=np.float64)[indices] for channel in columns[1:]]
            )
            np.savetxt(handle, matrix, delimiter=",", fmt="%.12g")
    return {
        "path": str(path.resolve()),
        "mode": mode,
        "rows_written": int(indices.size),
        "source_rows": total_rows,
        "note": note,
    }


def _event_to_payload(event: Any) -> dict:
    if isinstance(event, DetectedEvent):
        return {
            "kind": event.kind,
            "ts_start": round(float(event.ts_start), 6),
            "ts_end": round(float(event.ts_end), 6),
            "duration_s": round(float(event.ts_end - event.ts_start), 6),
            "channel": event.channel,
            "severity": event.severity,
            "description": event.description,
            "confidence": round(float(event.confidence), 6),
            "metrics": event.metrics,
            "status": None,
        }

    payload = dict(event)
    ts_start = payload.get("ts_start", payload.get("ts", payload.get("t_rel", 0.0)))
    ts_end = payload.get("ts_end", payload.get("ts", payload.get("t_rel", ts_start)))
    details = payload.get("details") or payload.get("description", "")
    metrics = payload.get("meta") or payload.get("metrics", {})
    return {
        "kind": payload.get("kind") or payload.get("type", "event"),
        "ts_start": round(float(ts_start), 6),
        "ts_end": round(float(ts_end), 6),
        "duration_s": round(float(ts_end) - float(ts_start), 6),
        "channel": payload.get("channel", ""),
        "severity": payload.get("severity", "info"),
        "description": details,
        "confidence": round(float(payload.get("confidence", 1.0)), 6),
        "metrics": metrics,
        "status": payload.get("status"),
    }


def _event_payloads(events: list[Any] | None) -> list[dict]:
    return [_event_to_payload(event) for event in (events or [])]


def _event_marker_groups(event_payloads: list[dict]) -> dict[str, list[float]]:
    markers = {"voltage": [], "frequency": [], "current": []}
    for event in event_payloads:
        start = float(event["ts_start"])
        kind = str(event["kind"])
        if "sag" in kind or "swell" in kind:
            markers["voltage"].append(start)
        elif "freq" in kind:
            markers["frequency"].append(start)
        elif "current" in kind:
            markers["current"].append(start)
    return markers


def _apply_axes_style(ax, title: str, y_label: str, *, show_xlabel: bool = False) -> None:
    ax.set_facecolor("#161b24")
    ax.set_title(title, color="#e6e9ef", fontsize=10, pad=6)
    ax.set_ylabel(y_label, color="#e6e9ef", fontsize=9)
    if show_xlabel:
        ax.set_xlabel("Time (s)", color="#e6e9ef", fontsize=9)
    ax.tick_params(colors="#94a3b8", labelsize=8)
    ax.grid(True, alpha=0.22, color="#334155")
    for spine in ax.spines.values():
        spine.set_edgecolor("#334155")


def _plot_ready_series(time_s, values, max_points: int = 10_000):
    arr_t = np.asarray(time_s, dtype=np.float64)
    arr_y = np.asarray(values, dtype=np.float64)
    if arr_t.size <= max_points:
        return arr_t, arr_y
    step = max(1, int(np.ceil(arr_t.size / max_points)))
    return arr_t[::step], arr_y[::step]


def _plot_group(ax, time_s, dataset, channels: tuple[str, ...], title: str, y_label: str) -> bool:
    plotted = False
    for channel in channels:
        values = dataset.channels.get(channel)
        if values is None:
            continue
        plot_t, plot_y = _plot_ready_series(time_s, values)
        ax.plot(
            plot_t,
            plot_y,
            color=_COLORS.get(channel, "#38bdf8"),
            linewidth=1.0,
            label=channel.replace("v_", "V_").replace("i_", "I_"),
        )
        plotted = True

    _apply_axes_style(ax, title, y_label)
    if plotted:
        ax.legend(loc="upper right", fontsize=8, facecolor="#161b24", labelcolor="#e6e9ef")
    else:
        ax.text(
            0.5,
            0.5,
            "N/A — required channels not present",
            color="#94a3b8",
            ha="center",
            va="center",
            transform=ax.transAxes,
            fontsize=9,
        )
    return plotted


def _save_waveform_overview_png(dataset, event_payloads: list[dict], path: Path) -> str:
    time_s = dataset.time
    fig, axes = plt.subplots(4, 1, figsize=(12, 10), sharex=True, facecolor="#0f1115")
    markers = _event_marker_groups(event_payloads)

    _plot_group(axes[0], time_s, dataset, _PHASE_CHANNELS, "Phase-to-Neutral Voltage", "Voltage (V)")
    _plot_group(axes[1], time_s, dataset, _LINE_CHANNELS, "Line-to-Line Voltage Overlay", "Voltage (V)")
    _plot_group(axes[2], time_s, dataset, _CURRENT_CHANNELS, "Current Channels", "Current (A)")

    aux_plotted = False
    freq_values = dataset.channels.get("freq")
    if freq_values is not None:
        plot_t, plot_y = _plot_ready_series(time_s, freq_values)
        axes[3].plot(plot_t, plot_y, color=_COLORS["freq"], linewidth=1.15, label="Frequency")
        axes[3].axhline(59.5, color="#ef4444", linewidth=0.8, linestyle="--", alpha=0.7)
        axes[3].axhline(60.5, color="#ef4444", linewidth=0.8, linestyle="--", alpha=0.7)
        aux_plotted = True
    for channel in ("p_mech", "v_dc"):
        values = dataset.channels.get(channel)
        if values is None:
            continue
        plot_t, plot_y = _plot_ready_series(time_s, values)
        axes[3].plot(plot_t, plot_y, color=_COLORS[channel], linewidth=1.0, label=channel)
        aux_plotted = True
    _apply_axes_style(axes[3], "Frequency / Auxiliary Channels", "Hz / mixed", show_xlabel=True)
    if aux_plotted:
        axes[3].legend(loc="upper right", fontsize=8, facecolor="#161b24", labelcolor="#e6e9ef")
    else:
        axes[3].text(
            0.5,
            0.5,
            "N/A — no frequency or auxiliary channels present",
            color="#94a3b8",
            ha="center",
            va="center",
            transform=axes[3].transAxes,
            fontsize=9,
        )

    marker_specs = (
        (axes[0], markers["voltage"], "#ef4444"),
        (axes[1], markers["voltage"], "#ef4444"),
        (axes[2], markers["current"], "#f59e0b"),
        (axes[3], markers["frequency"], "#a855f7"),
    )
    for ax, starts, color in marker_specs:
        for start in starts:
            ax.axvline(start, color=color, linewidth=0.8, linestyle="--", alpha=0.5)

    fig.tight_layout()
    fig.savefig(path, dpi=140, bbox_inches="tight", facecolor="#0f1115")
    plt.close(fig)
    return str(path.resolve())


def _save_line_to_line_png(dataset, path: Path) -> str | None:
    available = [channel for channel in _LINE_CHANNELS if dataset.channels.get(channel) is not None]
    if not available:
        return None

    fig, ax = plt.subplots(figsize=(12, 4.5), facecolor="#0f1115")
    _plot_group(ax, dataset.time, dataset, tuple(available), "Line-to-Line Voltage Overlay", "Voltage (V)")
    _apply_axes_style(ax, "Line-to-Line Voltage Overlay", "Voltage (V)", show_xlabel=True)
    fig.tight_layout()
    fig.savefig(path, dpi=140, bbox_inches="tight", facecolor="#0f1115")
    plt.close(fig)
    return str(path.resolve())


def _compliance_summary(checks: list[dict]) -> tuple[int, int, int]:
    passes = sum(1 for check in checks if check.get("status") == "PASS")
    fails = sum(1 for check in checks if check.get("status") == "FAIL")
    na_count = sum(1 for check in checks if check.get("status") == "N/A")
    return passes, fails, na_count


def _status_badge(status: str) -> str:
    colors = {"PASS": "#10b981", "FAIL": "#ef4444", "N/A": "#f59e0b"}
    color = colors.get(status, "#64748b")
    return (
        f"<span style='background:{color}; color:#fff; padding:2px 10px; "
        f"border-radius:999px; font-weight:700; font-size:12px;'>{status}</span>"
    )


def _build_comparison_section(compare_path: str, session_path: str, output_dir: str) -> tuple[str, str | None]:
    try:
        ref = AnalysisEngine.load_session(compare_path)
        test = AnalysisEngine.load_session(session_path)
        scorecard = AnalysisEngine.comparison_scorecard(ref, test)
    except Exception as exc:
        return f"<p style='color:#ef4444'>Comparison unavailable: {exc}</p>", None

    comparison_csv = os.path.join(output_dir, "comparison_scorecard.csv")
    try:
        AnalysisEngine.scorecard_to_csv(scorecard, comparison_csv)
    except Exception:
        comparison_csv = None

    delta_rows = []
    for metric, payload in scorecard.get("deltas", {}).items():
        delta_rows.append(
            "<tr>"
            f"<td>{metric}</td>"
            f"<td>{_fmt_value(payload.get('ref'), 4)}</td>"
            f"<td>{_fmt_value(payload.get('test'), 4)}</td>"
            f"<td>{_fmt_value(payload.get('delta'), 4)}</td>"
            "</tr>"
        )

    signal_rows = []
    for signal, payload in scorecard.get("per_signal", {}).items():
        signal_rows.append(
            "<tr>"
            f"<td>{signal}</td>"
            f"<td>{_fmt_value(payload.get('rmse'), 4)}</td>"
            f"<td>{_fmt_value(payload.get('max_delta'), 4)}</td>"
            f"<td>{_fmt_value(payload.get('mean_delta'), 4)}</td>"
            "</tr>"
        )

    html = f"""
    <h2>Run Comparison</h2>
    <p class="muted">Baseline: <code>{os.path.basename(compare_path)}</code> &nbsp;•&nbsp; Comparison: <code>{os.path.basename(session_path)}</code></p>
    <div class="callout">
      <strong>{scorecard.get("verdict", "Comparison complete")}</strong><br/>
      Improvements: {scorecard.get("improvements", 0)} &nbsp;•&nbsp;
      Regressions: {scorecard.get("regressions", 0)}
    </div>
    <table>
      <tr><th>Metric</th><th>Baseline</th><th>Comparison</th><th>Δ</th></tr>
      {''.join(delta_rows) or '<tr><td colspan="4">No aggregate deltas available.</td></tr>'}
    </table>
    <table>
      <tr><th>Channel</th><th>RMSE</th><th>max |Δ|</th><th>mean Δ</th></tr>
      {''.join(signal_rows) or '<tr><td colspan="4">No signal-level comparison rows available.</td></tr>'}
    </table>
    """
    return html, os.path.abspath(comparison_csv) if comparison_csv else None


def _build_metadata_payload(
    capsule: dict,
    summary: dict,
    profile: str,
    *,
    normalized_csv: dict | None = None,
) -> dict:
    session = summary["session"]
    import_meta = capsule.get("import_meta", {})
    meta = capsule.get("meta", {})
    return {
        "session_id": session["session_id"],
        "source_file_name": session["source_name"],
        "source_file_path": session["source_path"],
        "source_hash_sha256": session.get("source_hash_sha256"),
        "import_timestamp": import_meta.get("imported_at"),
        "sample_count": session["sample_count"],
        "sample_rate_hz": session["sample_rate_hz"],
        "time_range_s": {
            "start": session["time_start_s"],
            "end": session["time_end_s"],
            "window": session["time_window_s"],
        },
        "mapped_channels": session["mapped_channels"],
        "derived_channels": session["derived_channels"],
        "scale_factors": session["scale_factors"],
        "compliance_profile": profile,
        "normalized_csv": normalized_csv or {},
        "app_version": session.get("app_version", APP_VERSION),
        "git_commit": _git_commit(),
        "meta_channels": list(meta.get("channels", [])),
    }


def _git_commit() -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
        )
    except Exception:
        return None
    commit = result.stdout.strip()
    return commit or None


def _build_report_html(
    summary: dict,
    compliance: list[dict],
    event_payloads: list[dict],
    *,
    metadata: dict,
    profile: str,
    waveform_plot_name: str,
    line_plot_name: str | None,
    report_title: str,
    section_title: str,
    compare_html: str = "",
) -> str:
    session = summary["session"]
    passes, fails, na_count = _compliance_summary(compliance)
    overall = "PASS" if fails == 0 and passes > 0 else "FAIL" if fails > 0 else "N/A"

    metric_rows = []
    for section_name, payload in (
        ("Phase Voltage", summary["phase_voltage"]),
        ("Line Voltage", summary["line_voltage"]),
    ):
        for channel, values in payload.items():
            if values.get("available"):
                metric_rows.append(
                    "<tr>"
                    f"<td>{section_name}</td><td>{channel} RMS</td><td>{_fmt_value(values.get('rms'), 3)}</td>"
                    f"<td>{values.get('unit', '')}</td><td>{'THD ' + _fmt_value(values.get('thd_pct'), 3) + ' %' if 'thd_pct' in values else ''}</td>"
                    "</tr>"
                )
            else:
                metric_rows.append(
                    "<tr>"
                    f"<td>{section_name}</td><td>{channel}</td><td>N/A</td><td>{values.get('unit', '')}</td><td>{values.get('reason', '')}</td>"
                    "</tr>"
                )

    frequency = summary["frequency"]
    if frequency.get("available"):
        metric_rows.extend(
            [
                f"<tr><td>Frequency</td><td>Mean</td><td>{_fmt_value(frequency.get('mean_hz'), 4)}</td><td>Hz</td><td>{frequency.get('source', '')}</td></tr>",
                f"<tr><td>Frequency</td><td>Min / Max</td><td>{_fmt_value(frequency.get('min_hz'), 4)} / {_fmt_value(frequency.get('max_hz'), 4)}</td><td>Hz</td><td>Deviation vs 60 Hz: {_fmt_value(frequency.get('max_deviation_hz'), 4)} Hz</td></tr>",
            ]
        )
    else:
        metric_rows.append(
            f"<tr><td>Frequency</td><td>Summary</td><td>N/A</td><td>Hz</td><td>{frequency.get('reason', '')}</td></tr>"
        )

    balance = summary["balance"]
    if balance.get("available"):
        metric_rows.append(
            f"<tr><td>Balance</td><td>Voltage imbalance</td><td>{_fmt_value(balance.get('percent_voltage_imbalance'), 3)}</td><td>%</td><td>Max RMS deviation: {_fmt_value(balance.get('max_rms_deviation_v'), 3)} V</td></tr>"
        )
    else:
        metric_rows.append(
            f"<tr><td>Balance</td><td>Voltage imbalance</td><td>N/A</td><td>%</td><td>{balance.get('reason', '')}</td></tr>"
        )

    event_counts = summary["events"]["counts"]
    metric_rows.extend(
        [
            f"<tr><td>Events</td><td>Voltage sag count</td><td>{event_counts['voltage_sag']}</td><td>events</td><td></td></tr>",
            f"<tr><td>Events</td><td>Frequency excursion count</td><td>{event_counts['frequency_excursion']}</td><td>events</td><td></td></tr>",
            f"<tr><td>Events</td><td>Overcurrent count</td><td>{event_counts['overcurrent'] if summary['current_thresholds'].get('available') else 'N/A'}</td><td>events</td><td>{'' if summary['current_thresholds'].get('available') else summary['current_thresholds'].get('reason', '')}</td></tr>",
        ]
    )

    compliance_rows = []
    for check in compliance:
        compliance_rows.append(
            "<tr>"
            f"<td>{check.get('name')}</td>"
            f"<td>{_fmt_value(check.get('measured'), 4) if check.get('measured') is not None else 'N/A'}</td>"
            f"<td>{_fmt_value(check.get('threshold'), 4) if check.get('threshold') is not None else 'N/A'}</td>"
            f"<td>{check.get('units', '')}</td>"
            f"<td>{_status_badge(check.get('status', 'N/A'))}</td>"
            f"<td>{check.get('source', _profile_label(profile))}</td>"
            f"<td>{check.get('notes') or check.get('na_reason') or check.get('details', '')}</td>"
            "</tr>"
        )

    event_rows = []
    for event in event_payloads:
        event_rows.append(
            "<tr>"
            f"<td>{event['kind']}</td>"
            f"<td>{_fmt_value(event['ts_start'], 4)}</td>"
            f"<td>{_fmt_value(event['duration_s'], 4)}</td>"
            f"<td>{event['channel'] or '—'}</td>"
            f"<td>{event['severity']}</td>"
            f"<td>{event['description']}</td>"
            "</tr>"
        )

    line_plot_html = (
        f"<img class='plot' src='{line_plot_name}' alt='Line-to-line overlay'/>"
        if line_plot_name
        else "<p class='muted'>Line-to-line overlay unavailable because the required source phase channels were not present.</p>"
    )

    css = """
    :root {
      --bg:#0f1115; --surface:#161b24; --surface-2:#1b2230; --border:#243244;
      --text:#e6e9ef; --muted:#94a3b8; --accent:#38bdf8;
    }
    * { box-sizing:border-box; }
    body {
      margin:0; padding:24px; background:var(--bg); color:var(--text);
      font-family:'Segoe UI',Arial,sans-serif; line-height:1.55; font-size:14px;
    }
    h1 { margin:0 0 6px; font-size:26px; }
    h2 { margin:24px 0 10px; font-size:18px; color:#dbeafe; }
    p { margin:6px 0 0; }
    .subtitle { color:var(--muted); margin-bottom:14px; }
    .hero {
      display:grid; grid-template-columns:repeat(auto-fit,minmax(220px,1fr));
      gap:12px; margin:18px 0 10px;
    }
    .card, .callout {
      background:linear-gradient(180deg, rgba(29,39,54,.98), rgba(21,27,36,.98));
      border:1px solid var(--border); border-radius:10px; padding:12px 14px;
    }
    .label { color:var(--muted); font-size:12px; text-transform:uppercase; letter-spacing:.06em; }
    .value { font-size:20px; font-weight:700; margin-top:4px; }
    table {
      width:100%; border-collapse:collapse; background:var(--surface);
      border:1px solid var(--border); border-radius:10px; overflow:hidden;
    }
    th {
      text-align:left; background:var(--surface-2); color:var(--muted);
      font-size:12px; text-transform:uppercase; letter-spacing:.05em; padding:10px;
    }
    td { padding:10px; border-top:1px solid var(--border); vertical-align:top; }
    img.plot {
      width:100%; border:1px solid var(--border); border-radius:10px; margin-top:8px;
      background:#111827;
    }
    .muted { color:var(--muted); }
    code {
      background:#172132; border:1px solid var(--border); border-radius:6px;
      padding:2px 6px; color:#cbd5e1;
    }
    .footer {
      margin-top:28px; padding-top:14px; border-top:1px solid var(--border);
      color:var(--muted); font-size:12px;
    }
    """

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>{report_title} — {session['session_id']}</title>
  <style>{css}</style>
</head>
<body>
  <h1>{report_title}</h1>
  <p class="subtitle">Offline recorded-session analysis · Standards-inspired engineering checks · {_profile_label(profile)}</p>

  <h2>{section_title}</h2>
  <div class="hero">
    <div class="card"><div class="label">Source File</div><div class="value">{session['source_name']}</div></div>
    <div class="card"><div class="label">Samples</div><div class="value">{session['sample_count']:,}</div></div>
    <div class="card"><div class="label">Sample Rate</div><div class="value">{_fmt_value(session['sample_rate_hz'], 2)} Hz</div></div>
    <div class="card"><div class="label">Time Window</div><div class="value">{_fmt_value(session['time_window_s'], 4)} s</div></div>
    <div class="card"><div class="label">Overall Check Status</div><div class="value">{overall}</div></div>
    <div class="card"><div class="label">Compliance Totals</div><div class="value">{passes} PASS / {fails} FAIL / {na_count} N/A</div></div>
  </div>

  <h2>Waveform Overview</h2>
  <img class="plot" src="{waveform_plot_name}" alt="Waveform overview"/>

  <h2>Line-to-Line Overlay</h2>
  {line_plot_html}

  <h2>Metrics Summary</h2>
  <table>
    <tr><th>Section</th><th>Metric</th><th>Measured Value</th><th>Units</th><th>Notes</th></tr>
    {''.join(metric_rows)}
  </table>

  <h2>Standards-Inspired Engineering Checks</h2>
  <table>
    <tr><th>Check</th><th>Measured</th><th>Threshold</th><th>Units</th><th>Result</th><th>Standard / Profile Reference</th><th>Notes</th></tr>
    {''.join(compliance_rows) or '<tr><td colspan="7">No compliance results generated.</td></tr>'}
  </table>

  <h2>Detected Events</h2>
  <table>
    <tr><th>Event</th><th>Start (s)</th><th>Duration (s)</th><th>Channel</th><th>Severity</th><th>Description</th></tr>
    {''.join(event_rows) or '<tr><td colspan="6">No events detected.</td></tr>'}
  </table>

  {compare_html}

  <h2>Provenance</h2>
  <table>
    <tr><th>Field</th><th>Value</th></tr>
    <tr><td>Source path</td><td><code>{session['source_path'] or 'N/A'}</code></td></tr>
    <tr><td>Source SHA-256</td><td><code>{metadata.get('source_hash_sha256') or 'N/A'}</code></td></tr>
    <tr><td>Mapped channels</td><td><code>{', '.join(session['mapped_channels']) or 'N/A'}</code></td></tr>
    <tr><td>Derived channels</td><td><code>{', '.join(session['derived_channels']) or 'N/A'}</code></td></tr>
    <tr><td>Scale factors</td><td><code>{json.dumps(session['scale_factors'], sort_keys=True)}</code></td></tr>
    <tr><td>Compliance profile</td><td><code>{profile}</code></td></tr>
    <tr><td>Normalized CSV mode</td><td><code>{metadata.get('normalized_csv', {}).get('mode', 'N/A')}</code></td></tr>
    <tr><td>Normalized CSV note</td><td>{metadata.get('normalized_csv', {}).get('note', 'N/A')}</td></tr>
    <tr><td>App version</td><td><code>{metadata.get('app_version') or APP_VERSION}</code></td></tr>
    <tr><td>Git commit</td><td><code>{metadata.get('git_commit') or 'N/A'}</code></td></tr>
  </table>

  <div class="footer">
    Generated by VSM Evidence Workbench. This report documents deterministic,
    offline engineering analysis of recorded data. It is not a certification statement.
  </div>
</body>
</html>"""


def _resolve_inputs(
    session_path: str,
    *,
    profile: str,
    thresholds: dict | None,
    compliance_results: list[dict] | None,
    events: list[Any] | None,
    metrics: dict | None,
    session_data: dict | None = None,
) -> tuple[dict, list[dict], list[dict], dict, Any]:
    if session_data is None:
        with open(session_path, "r", encoding="utf-8") as handle:
            capsule = json.load(handle)
    else:
        capsule = session_data

    ensure_capsule_derived_channels(capsule)
    dataset = dataset_for_analysis(capsule)

    raw_events = events
    if raw_events is None:
        raw_events = events_for_capsule(capsule)
    event_payloads = _event_payloads(raw_events)

    summary = metrics
    if summary is None:
        if raw_events and all(isinstance(event, DetectedEvent) for event in raw_events):
            summary = compute_session_metrics(capsule, events=raw_events)
        else:
            summary = compute_session_metrics(capsule)

    checks = compliance_results or evaluate_session(capsule, profile=profile, thresholds=thresholds)
    return capsule, checks, event_payloads, summary, dataset


def generate_report(
    session_path: str,
    output_dir: str = "reports",
    insights_path: str = "data/insights_log.json",
) -> str:
    """
    Generate a timestamped HTML session report.

    The *insights_path* parameter is kept for compatibility; the current report
    is built directly from the session data and computed analysis outputs.
    """
    del insights_path

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    capsule, checks, event_payloads, summary, dataset = _resolve_inputs(
        session_path,
        profile="ieee_2800_inspired",
        thresholds=None,
        compliance_results=None,
        events=None,
        metrics=None,
        session_data=None,
    )

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    waveform_name = f"waveform_plot_{stamp}.png"
    line_name = f"line_to_line_plot_{stamp}.png"
    waveform_path = output / waveform_name
    line_path = output / line_name
    _save_waveform_overview_png(dataset, event_payloads, waveform_path)
    line_plot_path = _save_line_to_line_png(dataset, line_path)

    report_html = _build_report_html(
        summary,
        checks,
        event_payloads,
        metadata=_build_metadata_payload(capsule, summary, "ieee_2800_inspired"),
        profile="ieee_2800_inspired",
        waveform_plot_name=waveform_name,
        line_plot_name=line_name if line_plot_path else None,
        report_title="VSM Evidence Workbench — Session Report",
        section_title="HIL Session Report",
    )
    html_path = output / f"session_report_{stamp}.html"
    html_path.write_text(report_html, encoding="utf-8")
    return str(html_path.resolve())


def generate_evidence_package(
    session_path: str,
    output_dir: str = "exports",
    profile: str = "project_demo",
    thresholds: dict | None = None,
    compare_path: str | None = None,
    insights_path: str = "data/insights_log.json",
    compliance_results: list[dict] | None = None,
    events: list[Any] | None = None,
    metrics: dict | None = None,
    session_data: dict | None = None,
    include_full_resolution_csv: bool = False,
    preview_csv_max_rows: int = _DEFAULT_PREVIEW_CSV_ROWS,
) -> dict:
    """
    Generate an evidence package that matches the app's recorded-data analysis.
    """
    del insights_path

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    capsule, checks, event_payloads, summary, dataset = _resolve_inputs(
        session_path,
        profile=profile,
        thresholds=thresholds,
        compliance_results=compliance_results,
        events=events,
        metrics=metrics,
        session_data=session_data,
    )

    waveform_png = output / "waveform_overview.png"
    line_png = output / "line_to_line_overlay.png"
    csv_path = output / "normalized_frames.csv"
    metadata_json = output / "metadata.json"
    metrics_json = output / "metrics.json"
    compliance_json = output / "compliance.json"
    events_json = output / "events.json"
    capsule_json = output / "session_capsule.json"

    _save_waveform_overview_png(dataset, event_payloads, waveform_png)
    line_plot_path = _save_line_to_line_png(dataset, line_png)
    csv_export = _write_dataset_csv(
        dataset,
        capsule,
        csv_path,
        include_full_resolution=include_full_resolution_csv,
        max_preview_rows=preview_csv_max_rows,
    )

    metadata_payload = _build_metadata_payload(
        capsule,
        summary,
        profile,
        normalized_csv=csv_export,
    )
    compliance_payload = {
        "profile": profile,
        "profile_label": _profile_label(profile),
        "overall": {
            "pass": _compliance_summary(checks)[0],
            "fail": _compliance_summary(checks)[1],
            "na": _compliance_summary(checks)[2],
        },
        "checks": checks,
    }
    events_payload = {
        "count": len(event_payloads),
        "events": event_payloads,
    }

    _write_json(metadata_json, metadata_payload)
    _write_json(metrics_json, summary)
    _write_json(compliance_json, compliance_payload)
    _write_json(events_json, events_payload)
    _write_json(capsule_json, _safe_capsule_copy(capsule))

    comparison_html = ""
    comparison_csv = None
    if compare_path:
        comparison_html, comparison_csv = _build_comparison_section(compare_path, session_path, str(output))

    html = _build_report_html(
        summary,
        checks,
        event_payloads,
        metadata=metadata_payload,
        profile=profile,
        waveform_plot_name=waveform_png.name,
        line_plot_name=line_png.name if line_plot_path else None,
        report_title="VSM Evidence Workbench — Evidence Report",
        section_title="Recorded Session Analysis",
        compare_html=comparison_html,
    )
    html_path = output / "evidence_report.html"
    html_path.write_text(html, encoding="utf-8")

    result = {
        "html": str(html_path.resolve()),
        "plot": str(waveform_png.resolve()),
        "line_plot": str(line_png.resolve()) if line_plot_path else "",
        "csv": csv_export["path"],
        "capsule_json": str(capsule_json.resolve()),
        "metrics_json": str(metrics_json.resolve()),
        "summary_json": str(metrics_json.resolve()),
        "compliance_json": str(compliance_json.resolve()),
        "events_json": str(events_json.resolve()),
        "metadata_json": str(metadata_json.resolve()),
    }
    if comparison_csv:
        result["comparison_csv"] = comparison_csv
    return result
