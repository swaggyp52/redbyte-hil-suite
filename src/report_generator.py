import json
import logging
import os
import warnings
from datetime import datetime
from pathlib import Path

# Temporary suppression for third-party dateutil deprecation emitted during matplotlib import.
# Remove when upstream dependency no longer calls utcfromtimestamp.
warnings.filterwarnings(
    "ignore",
    message=r"datetime\.datetime\.utcfromtimestamp\(\) is deprecated and scheduled for removal in a future version.*",
    category=DeprecationWarning,
    module=r"dateutil\.tz\.tz",
)

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

logger = logging.getLogger(__name__)

try:
    from compliance_checker import evaluate_ieee_2800
    from signal_processing import compute_rms, compute_thd
except ImportError:
    from src.compliance_checker import evaluate_ieee_2800
    from src.signal_processing import compute_rms, compute_thd


def generate_report(session_path: str, output_dir: str = "reports", insights_path: str = "data/insights_log.json"):
    session_file = Path(session_path)
    if not session_file.exists():
        raise FileNotFoundError(f"Session file not found: {session_file}")

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    with open(session_file, "r") as f:
        data = json.load(f)

    frames = data.get("frames", [])
    if not frames:
        raise RuntimeError("No frames in session")

    ts0 = frames[0]["ts"]
    t = [f["ts"] - ts0 for f in frames]
    v_an = [f.get("v_an", 0) for f in frames]
    freq = [f.get("freq", 60.0) for f in frames]

    rms = compute_rms(v_an)
    thd = compute_thd(v_an, time_data=[f["ts"] for f in frames])
    compliance = evaluate_ieee_2800(data)

    # Plot
    plt.figure(figsize=(10, 4))
    plt.plot(t, v_an, label="V_an")
    plt.title("Voltage (V_an)")
    plt.xlabel("Time (s)")
    plt.ylabel("Voltage (V)")
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plot_path = output / "voltage_plot.png"
    plt.savefig(plot_path)
    plt.close()

    # Insights
    insights = []
    if os.path.exists(insights_path):
        try:
            with open(insights_path, "r") as f:
                payload = json.load(f)
                insights = payload.get("insights", []) if isinstance(payload, dict) else []
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
            logger.warning("Could not load insights from %s: %s", insights_path, exc)
            insights = []

    insight_rows = "".join([
        f"<tr><td>{i.get('ts', 0):.2f}</td><td>{i.get('type','')}</td><td>{i.get('description','')}</td></tr>"
        for i in insights
    ])

    compliance_rows = "".join([
        f"<tr><td>{c['name']}</td><td>{'PASS' if c['passed'] else 'FAIL'}</td><td>{c['details']}</td></tr>"
        for c in compliance
    ])

    html = f"""
    <html>
    <head><title>HIL Session Report</title></head>
    <body style='font-family:Segoe UI, Arial; background:#0f1115; color:#e6e9ef;'>
      <h2>HIL Session Report</h2>
      <p><b>RMS:</b> {rms:.2f} V</p>
      <p><b>THD:</b> {thd:.2f}%</p>
      <p><b>Freq range:</b> {min(freq):.2f}–{max(freq):.2f} Hz</p>
      <img src='voltage_plot.png' style='width:100%; max-width:900px; border:1px solid #1f2633;'/>
      <h3>Compliance</h3>
      <table border='1' cellpadding='6' cellspacing='0' style='border-color:#1f2633;'>
        <tr><th>Rule</th><th>Result</th><th>Details</th></tr>
        {compliance_rows}
      </table>
      <h3>Insight Timeline</h3>
      <table border='1' cellpadding='6' cellspacing='0' style='border-color:#1f2633;'>
        <tr><th>Time</th><th>Insight</th><th>Description</th></tr>
        {insight_rows}
      </table>
    </body>
    </html>
    """

    ts_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    html_path = output / f"session_report_{ts_str}.html"
    html_path.write_text(html)
    return str(html_path)
