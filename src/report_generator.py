"""
report_generator.py — HIL Session Report Generator

Produces a self-contained HTML report from a JSON Data Capsule session file.
The report includes:
  - Session metadata (ID, duration, frame count, acquisition rate)
  - Per-channel RMS summary (v_an, v_bn, v_cn, i_a, i_b, i_c)
  - V_an waveform plot
  - THD value
  - IEEE 2800-2022 subset compliance table
  - InsightEngine event timeline

Usage
-----
    from src.report_generator import generate_report
    html_path = generate_report(
        session_path="data/sessions/session_001.json",
        output_dir="reports",
        insights_path="data/insights_log.json"
    )
"""

import json
import os
from pathlib import Path
from datetime import datetime, timezone

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec

from src.compliance_checker import evaluate_ieee_2800, evaluate_session, available_profiles
from src.signal_processing import compute_rms, compute_thd
from src.event_detector import detect_events, run_summary


def _fmt_ts(ts_epoch):
    """Convert epoch float to readable UTC string."""
    try:
        return datetime.fromtimestamp(ts_epoch, timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    except Exception:
        return str(ts_epoch)


def _pass_badge(passed):
    color = "#22c55e" if passed else "#ef4444"
    label = "PASS" if passed else "FAIL"
    return (
        f"<span style='background:{color}; color:#fff; padding:2px 10px; "
        f"border-radius:4px; font-weight:bold; font-size:0.85em;'>{label}</span>"
    )


def generate_report(
    session_path: str,
    output_dir: str = "reports",
    insights_path: str = "data/insights_log.json",
):
    """
    Generate an HTML session report from a JSON Data Capsule.

    Parameters
    ----------
    session_path : str
        Path to the JSON Data Capsule produced by Recorder.
    output_dir : str
        Directory where output files (HTML + PNG plot) are written.
    insights_path : str
        Path to the InsightEngine JSON log (optional).

    Returns
    -------
    str
        Absolute path to the generated HTML report file.
    """
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    with open(session_path, "r") as f:
        data = json.load(f)

    meta = data.get("meta", {})
    frames = data.get("frames", [])
    events = data.get("events", [])

    if not frames:
        raise RuntimeError("No frames in session data capsule.")

    # ── Time axis ────────────────────────────────────────────────────────────
    ts0 = frames[0].get("ts", 0)
    ts_end = frames[-1].get("ts", ts0)
    t = [f.get("ts", ts0) - ts0 for f in frames]
    duration_s = ts_end - ts0
    acq_rate = len(frames) / duration_s if duration_s > 0 else 0.0

    # ── Channel extraction ───────────────────────────────────────────────────
    v_an = [f.get("v_an", 0.0) for f in frames]
    v_bn = [f.get("v_bn", 0.0) for f in frames]
    v_cn = [f.get("v_cn", 0.0) for f in frames]
    i_a  = [f.get("i_a", 0.0) for f in frames]
    i_b  = [f.get("i_b", 0.0) for f in frames]
    i_c  = [f.get("i_c", 0.0) for f in frames]
    freq = [f.get("freq", 60.0) for f in frames]

    # ── Signal metrics ───────────────────────────────────────────────────────
    rms_van = compute_rms(v_an)
    rms_vbn = compute_rms(v_bn)
    rms_vcn = compute_rms(v_cn)
    rms_ia  = compute_rms(i_a)
    rms_ib  = compute_rms(i_b)
    rms_ic  = compute_rms(i_c)
    thd_van = compute_thd(v_an, time_data=[f.get("ts", 0) for f in frames])

    # ── Compliance ───────────────────────────────────────────────────────────
    compliance = evaluate_ieee_2800(data)
    overall_pass = all(c["passed"] for c in compliance)

    # ── Plot (3-panel: Voltage, Current, Frequency) ──────────────────────────
    fig = plt.figure(figsize=(12, 7), facecolor="#0f1115")
    gs = gridspec.GridSpec(3, 1, hspace=0.45, figure=fig)

    ax_v = fig.add_subplot(gs[0])
    ax_v.plot(t, v_an, color="#f97316", linewidth=1.0, label="V_an")
    ax_v.plot(t, v_bn, color="#3b82f6", linewidth=1.0, label="V_bn")
    ax_v.plot(t, v_cn, color="#22c55e", linewidth=1.0, label="V_cn")
    ax_v.set_facecolor("#1a1d24")
    ax_v.set_ylabel("Voltage (V)", color="#e6e9ef", fontsize=9)
    ax_v.set_title("Three-Phase Voltage", color="#e6e9ef", fontsize=10, pad=4)
    ax_v.tick_params(colors="#8b95a8", labelsize=8)
    ax_v.legend(loc="upper right", fontsize=8, facecolor="#1a1d24", labelcolor="#e6e9ef")
    ax_v.grid(True, alpha=0.2, color="#2d3748")
    for spine in ax_v.spines.values():
        spine.set_edgecolor("#2d3748")

    ax_i = fig.add_subplot(gs[1])
    ax_i.plot(t, i_a, color="#f97316", linewidth=1.0, label="I_a")
    ax_i.plot(t, i_b, color="#3b82f6", linewidth=1.0, label="I_b")
    ax_i.plot(t, i_c, color="#22c55e", linewidth=1.0, label="I_c")
    ax_i.set_facecolor("#1a1d24")
    ax_i.set_ylabel("Current (A)", color="#e6e9ef", fontsize=9)
    ax_i.set_title("Three-Phase Current", color="#e6e9ef", fontsize=10, pad=4)
    ax_i.tick_params(colors="#8b95a8", labelsize=8)
    ax_i.legend(loc="upper right", fontsize=8, facecolor="#1a1d24", labelcolor="#e6e9ef")
    ax_i.grid(True, alpha=0.2, color="#2d3748")
    for spine in ax_i.spines.values():
        spine.set_edgecolor("#2d3748")

    ax_f = fig.add_subplot(gs[2])
    ax_f.plot(t, freq, color="#a78bfa", linewidth=1.2, label="Frequency")
    ax_f.axhline(59.5, color="#ef4444", linewidth=0.8, linestyle="--", alpha=0.7, label="±0.5 Hz band")
    ax_f.axhline(60.5, color="#ef4444", linewidth=0.8, linestyle="--", alpha=0.7)
    ax_f.set_facecolor("#1a1d24")
    ax_f.set_xlabel("Time (s)", color="#e6e9ef", fontsize=9)
    ax_f.set_ylabel("Frequency (Hz)", color="#e6e9ef", fontsize=9)
    ax_f.set_title("Grid Frequency", color="#e6e9ef", fontsize=10, pad=4)
    ax_f.tick_params(colors="#8b95a8", labelsize=8)
    ax_f.legend(loc="upper right", fontsize=8, facecolor="#1a1d24", labelcolor="#e6e9ef")
    ax_f.grid(True, alpha=0.2, color="#2d3748")
    for spine in ax_f.spines.values():
        spine.set_edgecolor("#2d3748")

    fig.patch.set_facecolor("#0f1115")
    plot_path = output / "waveform_plot.png"
    plt.savefig(plot_path, dpi=120, bbox_inches="tight", facecolor="#0f1115")
    plt.close()

    # ── Insights ─────────────────────────────────────────────────────────────
    insights = []
    if os.path.exists(insights_path):
        try:
            with open(insights_path, "r") as f:
                insights = json.load(f).get("insights", [])
        except Exception:
            insights = []

    # Also include session events from Data Capsule
    for ev in events:
        insights.append({
            "ts": ev.get("ts", 0),
            "type": ev.get("type", "Event"),
            "description": ev.get("data", {}).get("description", str(ev.get("data", ""))),
        })

    insights.sort(key=lambda x: x.get("ts", 0))

    insight_rows = "".join([
        f"<tr><td>{i.get('ts', 0):.3f}</td>"
        f"<td><span style='color:#f97316;font-weight:bold'>{i.get('type','')}</span></td>"
        f"<td>{i.get('description','')}</td></tr>"
        for i in insights
    ]) or "<tr><td colspan='3' style='color:#6b7280;text-align:center'>No insight events recorded</td></tr>"

    compliance_rows = "".join([
        f"<tr>"
        f"<td>{c['name']}</td>"
        f"<td style='text-align:center'>{_pass_badge(c['passed'])}</td>"
        f"<td style='font-size:0.85em;color:#9ca3af'>{c['details']}</td>"
        f"</tr>"
        for c in compliance
    ])

    # ── Session metadata table ────────────────────────────────────────────────
    session_id = meta.get("session_id", "—")
    start_time = _fmt_ts(meta.get("start_time", ts0))
    frame_count = meta.get("frame_count", len(frames))

    overall_badge = _pass_badge(overall_pass)

    # ── HTML ─────────────────────────────────────────────────────────────────
    css = """
      :root { --bg: #0f1115; --surface: #161b24; --border: #1f2b3e; --text: #e6e9ef;
              --muted: #8b95a8; --accent: #3b82f6; }
      * { box-sizing: border-box; margin: 0; padding: 0; }
      body { font-family: 'Segoe UI', Arial, sans-serif; background: var(--bg);
             color: var(--text); padding: 24px; font-size: 14px; line-height: 1.6; }
      h1 { font-size: 1.6em; margin-bottom: 4px; color: #f8fafc; }
      h2 { font-size: 1.1em; margin: 20px 0 8px; color: #cbd5e1; border-bottom: 1px solid var(--border); padding-bottom: 4px; }
      .badge-overall { font-size: 1em; margin-left: 12px; vertical-align: middle; }
      .subtitle { color: var(--muted); font-size: 0.9em; margin-bottom: 16px; }
      .meta-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 10px; margin-bottom: 18px; }
      .meta-card { background: var(--surface); border: 1px solid var(--border); border-radius: 6px; padding: 10px 14px; }
      .meta-card .label { font-size: 0.75em; color: var(--muted); text-transform: uppercase; letter-spacing: 0.05em; }
      .meta-card .value { font-size: 1.05em; font-weight: 600; color: var(--text); margin-top: 2px; }
      .rms-grid { display: grid; grid-template-columns: repeat(6, 1fr); gap: 8px; margin-bottom: 18px; }
      .rms-card { background: var(--surface); border: 1px solid var(--border); border-radius: 6px; padding: 8px 10px; text-align: center; }
      .rms-card .ch { font-size: 0.75em; color: var(--muted); }
      .rms-card .val { font-size: 1.1em; font-weight: bold; }
      img.plot { width: 100%; max-width: 1100px; border: 1px solid var(--border); border-radius: 6px; margin-bottom: 18px; }
      table { width: 100%; border-collapse: collapse; margin-bottom: 18px; }
      th { background: #1a2236; color: var(--muted); font-size: 0.8em; text-transform: uppercase;
           letter-spacing: 0.05em; padding: 8px 10px; text-align: left; border-bottom: 2px solid var(--border); }
      td { padding: 8px 10px; border-bottom: 1px solid var(--border); vertical-align: top; }
      tr:last-child td { border-bottom: none; }
      tr:hover td { background: #1c2333; }
      .footer { color: var(--muted); font-size: 0.78em; margin-top: 24px; padding-top: 10px;
                border-top: 1px solid var(--border); }
    """

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>VSM Session Report — {session_id}</title>
  <style>{css}</style>
</head>
<body>
  <h1>VSM Evidence Workbench — Session Report
    <span class="badge-overall">{overall_badge}</span>
  </h1>
  <p class="subtitle">VSM / Grid-Forming Inverter · IEEE 2800-inspired subset (engineering evidence, not certified compliance)</p>

  <h2>HIL Session Report</h2>

  <h2>Session Metadata</h2>
  <div class="meta-grid">
    <div class="meta-card"><div class="label">Session ID</div><div class="value">{session_id}</div></div>
    <div class="meta-card"><div class="label">Start Time</div><div class="value">{start_time}</div></div>
    <div class="meta-card"><div class="label">Duration</div><div class="value">{duration_s:.2f} s</div></div>
    <div class="meta-card"><div class="label">Frames</div><div class="value">{frame_count:,}</div></div>
    <div class="meta-card"><div class="label">Acquisition Rate</div><div class="value">{acq_rate:.1f} Hz</div></div>
    <div class="meta-card"><div class="label">THD (V_an)</div><div class="value">{thd_van:.2f} %</div></div>
    <div class="meta-card"><div class="label">Freq Range</div><div class="value">{min(freq):.3f} – {max(freq):.3f} Hz</div></div>
    <div class="meta-card"><div class="label">Events Logged</div><div class="value">{len(events)}</div></div>
  </div>

  <h2>Per-Channel RMS</h2>
  <div class="rms-grid">
    <div class="rms-card"><div class="ch">V_an</div><div class="val" style="color:#f97316">{rms_van:.2f} V</div></div>
    <div class="rms-card"><div class="ch">V_bn</div><div class="val" style="color:#3b82f6">{rms_vbn:.2f} V</div></div>
    <div class="rms-card"><div class="ch">V_cn</div><div class="val" style="color:#22c55e">{rms_vcn:.2f} V</div></div>
    <div class="rms-card"><div class="ch">I_a</div><div class="val" style="color:#f97316">{rms_ia:.3f} A</div></div>
    <div class="rms-card"><div class="ch">I_b</div><div class="val" style="color:#3b82f6">{rms_ib:.3f} A</div></div>
    <div class="rms-card"><div class="ch">I_c</div><div class="val" style="color:#22c55e">{rms_ic:.3f} A</div></div>
  </div>

  <h2>Waveforms</h2>
  <img class="plot" src="waveform_plot.png" alt="Three-phase voltage, current, and frequency plots"/>

  <h2>IEEE 2800-2022 Compliance (Informative Subset)</h2>
  <table>
    <tr><th>Rule</th><th style="width:80px;text-align:center">Result</th><th>Details</th></tr>
    {compliance_rows}
  </table>

  <h2>Insight &amp; Event Timeline</h2>
  <table>
    <tr><th style="width:90px">Time (s)</th><th style="width:180px">Type</th><th>Description</th></tr>
    {insight_rows}
  </table>

  <div class="footer">
    Generated by VSM Evidence Workbench · Gannon University Senior Design 2025–2026 ·
    IEEE 2800-2022 checks are an informative subset for HIL evaluation purposes only.
  </div>
</body>
</html>"""

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    html_path = output / f"session_report_{stamp}.html"
    html_path.write_text(html, encoding="utf-8")
    return str(html_path)


# ==========================================================================
# Evidence package (Stage 6) — HTML + CSV + JSON, optional run comparison
# ==========================================================================
def _scorecard_rows(compliance):
    rows = []
    for c in compliance:
        rows.append(
            f"<tr>"
            f"<td>{c['name']}</td>"
            f"<td style='text-align:center'>{_pass_badge(c['passed'])}</td>"
            f"<td style='font-family:monospace'>{c.get('measured','—')}</td>"
            f"<td style='font-family:monospace;color:#94a3b8'>{c.get('threshold','—')} {c.get('units','')}</td>"
            f"<td style='font-size:0.82em;color:#9ca3af'>{c.get('rule','')}</td>"
            f"<td style='font-size:0.75em;color:#64748b'>{c.get('source','')}</td>"
            f"</tr>"
        )
    return "\n".join(rows)


def _event_rows(events):
    if not events:
        return "<tr><td colspan='4' style='text-align:center;color:#6b7280'>No events auto-detected.</td></tr>"
    rows = []
    for e in events:
        rows.append(
            f"<tr>"
            f"<td style='font-family:monospace'>{e.get('t_rel',0):.3f}</td>"
            f"<td><span style='color:#f97316;font-weight:bold'>{e.get('type','')}</span></td>"
            f"<td style='font-size:0.88em'>{e.get('details','')}</td>"
            f"<td style='font-family:monospace;color:#94a3b8;font-size:0.8em'>{json.dumps(e.get('meta',{}))}</td>"
            f"</tr>"
        )
    return "\n".join(rows)


def _comparison_section(compare_path, session_path, output_dir):
    """If a comparison path is provided, build a scorecard block and write comparison CSV."""
    from src.analysis import AnalysisEngine
    try:
        ref = AnalysisEngine.load_session(compare_path)
        test = AnalysisEngine.load_session(session_path)
        scorecard = AnalysisEngine.comparison_scorecard(ref, test)
    except Exception as e:
        return f"<p style='color:#ef4444'>Comparison failed: {e}</p>", None

    # write a comparison CSV into output
    csv_path = os.path.join(output_dir, "comparison_scorecard.csv")
    try:
        AnalysisEngine.scorecard_to_csv(scorecard, csv_path)
    except Exception:
        csv_path = None

    rows = []
    for metric, d in scorecard["deltas"].items():
        delta = d["delta"]
        color = "#22c55e" if (delta == 0) else ("#eab308" if abs(delta) < 0.1 else "#f97316")
        rows.append(
            f"<tr><td>{metric}</td>"
            f"<td style='font-family:monospace'>{d['ref']:.4g}</td>"
            f"<td style='font-family:monospace'>{d['test']:.4g}</td>"
            f"<td style='font-family:monospace;color:{color}'>{delta:+.4g}</td></tr>"
        )

    sig_rows = []
    for sig, d in scorecard["per_signal"].items():
        sig_rows.append(
            f"<tr><td>{sig}</td>"
            f"<td style='font-family:monospace'>{d['rmse']:.4g}</td>"
            f"<td style='font-family:monospace'>{d['max_delta']:.4g}</td>"
            f"<td style='font-family:monospace'>{d['mean_delta']:.4g}</td></tr>"
        )

    verdict_color = "#22c55e"
    if "reference" in scorecard["verdict"].lower():
        verdict_color = "#f97316"
    elif "equivalent" in scorecard["verdict"].lower():
        verdict_color = "#eab308"

    html = f"""
    <h2>Run Comparison</h2>
    <p style='color:#94a3b8'>Reference: <code>{os.path.basename(compare_path)}</code> vs Test: <code>{os.path.basename(session_path)}</code></p>
    <div style='background:#1a2236;border:1px solid #1f2b3e;border-radius:6px;padding:10px 14px;margin:6px 0;'>
      <div style='color:{verdict_color};font-size:1.1em;font-weight:700'>{scorecard['verdict']}</div>
      <div style='color:#94a3b8;font-size:0.9em;margin-top:4px'>
        Improvements: {scorecard['improvements']} &nbsp; | &nbsp;
        Regressions: {scorecard['regressions']}
      </div>
    </div>

    <h3 style='margin-top:14px;color:#cbd5e1'>Per-Metric Deltas</h3>
    <table>
      <tr><th>Metric</th><th>Reference</th><th>Test</th><th>Δ (Test − Ref)</th></tr>
      {''.join(rows)}
    </table>

    <h3 style='margin-top:14px;color:#cbd5e1'>Time-Aligned Signal Errors</h3>
    <table>
      <tr><th>Signal</th><th>RMSE</th><th>max |Δ|</th><th>mean Δ</th></tr>
      {''.join(sig_rows)}
    </table>
    """
    return html, csv_path


def generate_evidence_package(
    session_path: str,
    output_dir: str = "exports",
    profile: str = "project_demo",
    thresholds: dict = None,
    compare_path: str = None,
    insights_path: str = "data/insights_log.json",
):
    """
    Generate a polished evidence package for a session.

    Produces:
      - evidence_report.html
      - waveform_plot.png
      - session_frames.csv
      - session_capsule.json          (copy of the source capsule)
      - compliance_scorecard.json     (machine-readable compliance results)
      - event_log.json                (auto-detected events)
      - run_summary.json              (derived metrics)
      - comparison_scorecard.csv      (only if compare_path provided)

    Returns
    -------
    dict
        Absolute paths to every artifact written.
    """
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    with open(session_path, "r") as f:
        data = json.load(f)

    meta = data.get("meta", {})
    frames = data.get("frames", [])
    if not frames:
        raise RuntimeError("No frames in session data capsule.")

    # ---- core analytics ----
    compliance = evaluate_session(data, profile=profile, thresholds=thresholds)
    events = detect_events(data)
    summary = run_summary(data)

    # ---- time / channel arrays for the plot ----
    ts0 = frames[0].get("ts", 0)
    ts_end = frames[-1].get("ts", ts0)
    t = [f.get("ts", ts0) - ts0 for f in frames]
    duration_s = ts_end - ts0
    acq_rate = len(frames) / duration_s if duration_s > 0 else 0.0

    v_an = [f.get("v_an", 0.0) for f in frames]
    v_bn = [f.get("v_bn", 0.0) for f in frames]
    v_cn = [f.get("v_cn", 0.0) for f in frames]
    i_a  = [f.get("i_a", 0.0) for f in frames]
    i_b  = [f.get("i_b", 0.0) for f in frames]
    i_c  = [f.get("i_c", 0.0) for f in frames]
    freq = [f.get("freq", 60.0) for f in frames]

    # ---- waveform plot ----
    fig = plt.figure(figsize=(12, 8), facecolor="#0f1115")
    gs = gridspec.GridSpec(3, 1, hspace=0.45, figure=fig)

    ax_v = fig.add_subplot(gs[0])
    ax_v.plot(t, v_an, color="#f97316", lw=1.0, label="V_an")
    ax_v.plot(t, v_bn, color="#3b82f6", lw=1.0, label="V_bn")
    ax_v.plot(t, v_cn, color="#22c55e", lw=1.0, label="V_cn")
    ax_v.set_title("Three-Phase Voltage", color="#e6e9ef", fontsize=10)
    for ev in events:
        if "sag" in ev["type"] or "overshoot" in ev["type"]:
            ax_v.axvline(ev["t_rel"], color="#ef4444", alpha=0.4, ls="--", lw=0.8)

    ax_i = fig.add_subplot(gs[1])
    ax_i.plot(t, i_a, color="#f97316", lw=1.0, label="I_a")
    ax_i.plot(t, i_b, color="#3b82f6", lw=1.0, label="I_b")
    ax_i.plot(t, i_c, color="#22c55e", lw=1.0, label="I_c")
    ax_i.set_title("Three-Phase Current", color="#e6e9ef", fontsize=10)

    ax_f = fig.add_subplot(gs[2])
    ax_f.plot(t, freq, color="#a78bfa", lw=1.2, label="Freq")
    ax_f.axhline(59.5, color="#ef4444", lw=0.8, ls="--", alpha=0.7)
    ax_f.axhline(60.5, color="#ef4444", lw=0.8, ls="--", alpha=0.7)
    ax_f.set_title("Grid Frequency", color="#e6e9ef", fontsize=10)

    for ax, ylabel in ((ax_v, "V"), (ax_i, "A"), (ax_f, "Hz")):
        ax.set_facecolor("#1a1d24")
        ax.set_ylabel(ylabel, color="#e6e9ef", fontsize=9)
        ax.tick_params(colors="#8b95a8", labelsize=8)
        ax.grid(True, alpha=0.2, color="#2d3748")
        ax.legend(loc="upper right", fontsize=8, facecolor="#1a1d24", labelcolor="#e6e9ef")
        for sp in ax.spines.values():
            sp.set_edgecolor("#2d3748")
    ax_f.set_xlabel("Time (s)", color="#e6e9ef", fontsize=9)

    fig.patch.set_facecolor("#0f1115")
    plot_path = output / "waveform_plot.png"
    plt.savefig(plot_path, dpi=120, bbox_inches="tight", facecolor="#0f1115")
    plt.close()

    # ---- CSV (per-frame) ----
    csv_path = output / "session_frames.csv"
    with open(csv_path, "w") as f:
        f.write("t_rel,ts,v_an,v_bn,v_cn,i_a,i_b,i_c,freq\n")
        for idx, fr in enumerate(frames):
            f.write(",".join(str(x) for x in [
                t[idx], fr.get("ts", ""), fr.get("v_an", 0.0), fr.get("v_bn", 0.0),
                fr.get("v_cn", 0.0), fr.get("i_a", 0.0), fr.get("i_b", 0.0),
                fr.get("i_c", 0.0), fr.get("freq", 0.0),
            ]) + "\n")

    # ---- JSON artifacts ----
    capsule_copy = output / "session_capsule.json"
    with open(capsule_copy, "w") as f:
        json.dump(data, f, indent=2)

    scorecard_json = output / "compliance_scorecard.json"
    with open(scorecard_json, "w") as f:
        json.dump({
            "profile": profile,
            "checks": compliance,
            "overall_passed": all(c["passed"] for c in compliance),
        }, f, indent=2)

    event_json = output / "event_log.json"
    with open(event_json, "w") as f:
        json.dump({"events": events, "count": len(events)}, f, indent=2)

    summary_json = output / "run_summary.json"
    with open(summary_json, "w") as f:
        # largest_disturbance may contain np types → cast
        def _safe(o):
            try:
                import numpy as _np
                if isinstance(o, _np.generic):
                    return o.item()
            except Exception:
                pass
            return str(o)
        json.dump(summary, f, indent=2, default=_safe)

    # ---- Optional comparison section ----
    comparison_html = ""
    comparison_csv = None
    if compare_path:
        comparison_html, comparison_csv = _comparison_section(
            compare_path, session_path, str(output)
        )

    # ---- HTML ----
    overall_pass = all(c["passed"] for c in compliance)
    overall_badge = _pass_badge(overall_pass)
    src_info = meta.get("source", {})
    import_info = meta.get("import", {})
    mapping = import_info.get("column_map", {})
    warnings = import_info.get("warnings", [])

    src_rows = ""
    if src_info:
        src_rows = "".join([
            f"<tr><td>{k}</td><td><code>{v}</code></td></tr>"
            for k, v in src_info.items() if v is not None
        ])
    if import_info:
        src_rows += "".join([
            f"<tr><td>mapping: {k}</td><td><code>{v}</code></td></tr>"
            for k, v in mapping.items()
        ])

    warnings_html = ""
    if warnings:
        warnings_html = "<ul style='color:#eab308'>" + \
            "".join([f"<li>{w}</li>" for w in warnings]) + "</ul>"

    profile_label = next(
        (p["label"] for p in available_profiles() if p["id"] == profile),
        profile,
    )

    css = """
      :root { --bg:#0f1115; --surface:#161b24; --border:#1f2b3e; --text:#e6e9ef; --muted:#8b95a8; }
      * { box-sizing: border-box; margin:0; padding:0; }
      body { font-family:'Segoe UI',Arial,sans-serif; background:var(--bg); color:var(--text);
             padding:24px; font-size:14px; line-height:1.6; }
      h1 { font-size:1.7em; margin-bottom:4px; color:#f8fafc; }
      h2 { font-size:1.15em; margin:22px 0 8px; color:#cbd5e1;
           border-bottom:1px solid var(--border); padding-bottom:4px; }
      h3 { font-size:1em; margin:12px 0 6px; color:#cbd5e1; }
      .subtitle { color:var(--muted); font-size:0.9em; margin-bottom:16px; }
      table { width:100%; border-collapse:collapse; margin-bottom:18px; }
      th { background:#1a2236; color:var(--muted); font-size:0.8em; text-transform:uppercase;
           letter-spacing:0.05em; padding:8px 10px; text-align:left;
           border-bottom:2px solid var(--border); }
      td { padding:8px 10px; border-bottom:1px solid var(--border); vertical-align:top; }
      tr:last-child td { border-bottom:none; }
      tr:hover td { background:#1c2333; }
      img.plot { width:100%; max-width:1100px; border:1px solid var(--border);
                 border-radius:6px; margin-bottom:18px; }
      .meta-grid { display:grid; grid-template-columns:repeat(auto-fill, minmax(220px, 1fr));
                   gap:10px; margin-bottom:18px; }
      .meta-card { background:var(--surface); border:1px solid var(--border); border-radius:6px;
                   padding:10px 14px; }
      .meta-card .label { font-size:0.75em; color:var(--muted); text-transform:uppercase;
                          letter-spacing:0.05em; }
      .meta-card .value { font-size:1.05em; font-weight:600; color:var(--text); margin-top:2px; }
      .footer { color:var(--muted); font-size:0.78em; margin-top:24px; padding-top:10px;
                border-top:1px solid var(--border); }
      code { background:#1a2236; padding:1px 6px; border-radius:3px; font-size:0.88em; }
    """

    html = f"""<!DOCTYPE html>
<html lang='en'>
<head><meta charset='UTF-8'><title>VSM Evidence Report — {meta.get('session_id','session')}</title>
<style>{css}</style></head>
<body>
  <h1>VSM Evidence Report {overall_badge}</h1>
  <p class='subtitle'>Local engineering analysis · Profile: <b>{profile_label}</b> · Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}</p>

  <h2>Run Summary</h2>
  <div class='meta-grid'>
    <div class='meta-card'><div class='label'>Session</div><div class='value'>{meta.get('session_id','—')}</div></div>
    <div class='meta-card'><div class='label'>Duration</div><div class='value'>{duration_s:.2f} s</div></div>
    <div class='meta-card'><div class='label'>Frames</div><div class='value'>{len(frames):,}</div></div>
    <div class='meta-card'><div class='label'>Sample Rate</div><div class='value'>{acq_rate:.1f} Hz</div></div>
    <div class='meta-card'><div class='label'>Nominal V_rms</div><div class='value'>{summary.get('nominal_v_estimate',0):.2f} V</div></div>
    <div class='meta-card'><div class='label'>Nominal Freq</div><div class='value'>{summary.get('nominal_freq_estimate',0):.3f} Hz</div></div>
    <div class='meta-card'><div class='label'>THD V_an</div><div class='value'>{summary.get('thd_van_pct',0):.2f} %</div></div>
    <div class='meta-card'><div class='label'>Events detected</div><div class='value'>{summary.get('event_count',0)}</div></div>
  </div>

  <h2>Source &amp; Provenance</h2>
  <table>
    <tr><th>Field</th><th>Value</th></tr>
    {src_rows or '<tr><td colspan=2 style="color:#6b7280">No import metadata (session not imported via wizard).</td></tr>'}
  </table>
  {warnings_html}

  <h2>Waveforms</h2>
  <img class='plot' src='waveform_plot.png' alt='Three-phase voltage, current, frequency'/>

  <h2>Standards Evidence — {profile_label}</h2>
  <table>
    <tr><th>Rule</th><th style='width:70px;text-align:center'>Result</th><th style='width:90px'>Measured</th><th style='width:100px'>Threshold</th><th>Rule text</th><th>Source</th></tr>
    {_scorecard_rows(compliance)}
  </table>
  <p style='color:#94a3b8;font-size:0.85em'>
    This is an engineering evaluation against a clearly labeled rule set.
    It is <b>not</b> a certified standards compliance test and should not be cited as one.
  </p>

  <h2>Auto-Detected Events</h2>
  <table>
    <tr><th style='width:80px'>t (s)</th><th style='width:200px'>Type</th><th>Details</th><th style='width:180px'>Meta</th></tr>
    {_event_rows(events)}
  </table>

  {comparison_html}

  <div class='footer'>
    Generated by the VSM Evidence Workbench · Senior Design Deliverable ·
    Rule profiles are clearly labeled "inspired subset" or "project engineering threshold".
    Full certification testing remains the province of accredited laboratories.
  </div>
</body>
</html>"""

    html_path = output / "evidence_report.html"
    html_path.write_text(html, encoding="utf-8")

    result = {
        "html": str(html_path.resolve()),
        "plot": str(plot_path.resolve()),
        "csv": str(csv_path.resolve()),
        "capsule_json": str(capsule_copy.resolve()),
        "compliance_json": str(scorecard_json.resolve()),
        "events_json": str(event_json.resolve()),
        "summary_json": str(summary_json.resolve()),
    }
    if comparison_csv:
        result["comparison_csv"] = os.path.abspath(comparison_csv)
    return result
