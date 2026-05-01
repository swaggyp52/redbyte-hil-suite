"""
Screenshot capture script for VSM Evidence Workbench slideshow.

Run from the gfm_hil_suite directory:
    .venv/Scripts/python.exe scripts/capture_screenshots.py

Saves 14 .png files to:
    artifacts/final_screenshots/
"""
from __future__ import annotations

import logging
import os
import sys
import time

# Ensure project root on path
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from PyQt6.QtCore import QEventLoop, QTimer, Qt
from PyQt6.QtWidgets import QApplication, QPushButton

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("capture")

# ── Paths ──────────────────────────────────────────────────────────────────
DATA_DIR = r"C:\Users\conno\OneDrive - Gannon University\Spring 2026\Senior Design"
OUT_DIR = os.path.join(ROOT, "artifacts", "final_screenshots")
os.makedirs(OUT_DIR, exist_ok=True)

RIGOL0  = os.path.join(DATA_DIR, "RigolDS0.csv")
RIGOL1  = os.path.join(DATA_DIR, "RigolDS1.csv")
POWER   = os.path.join(DATA_DIR, "InverterPower_Simulation.xlsx")
FREQ_S  = os.path.join(DATA_DIR, "VSGFrequency_Simulation.xlsx")


# ── Qt helpers ─────────────────────────────────────────────────────────────

def pump(ms: int = 600) -> None:
    """Pump the Qt event loop for *ms* milliseconds."""
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def wait_until(condition_fn, timeout_ms: int = 15_000, poll_ms: int = 200) -> bool:
    """Pump events until condition_fn() returns True or timeout."""
    deadline = time.monotonic() + timeout_ms / 1000
    while time.monotonic() < deadline:
        pump(poll_ms)
        if condition_fn():
            return True
    log.warning("wait_until timed out after %d ms", timeout_ms)
    return False


def save(widget, filename: str) -> bool:
    """Grab *widget* and save to OUT_DIR/filename."""
    path = os.path.join(OUT_DIR, filename)
    px = widget.grab()
    ok = px.save(path, "PNG")
    if ok:
        log.info("  SAVED %s  (%dx%d px)", filename, px.width(), px.height())
    else:
        log.error("  FAILED to save %s", filename)
    return ok


# ── Import helpers ─────────────────────────────────────────────────────────

def open_and_ingest(filepath: str, parent=None, timeout_ms: int = 25_000):
    """
    Create an ImportDialog, show it (non-modal), and load *filepath*.
    Waits for ingestion to complete.
    Returns the dialog.
    """
    from ui.import_dialog import ImportDialog
    dlg = ImportDialog(parent=parent)
    dlg.setWindowTitle(f"Import — {os.path.basename(filepath)}")
    dlg.show()
    pump(200)

    dlg._load_file(filepath)
    log.info("  Ingesting %s …", os.path.basename(filepath))

    # Wait until ingestion finishes (dataset populated)
    ok = wait_until(
        lambda: dlg._dataset is not None,
        timeout_ms=timeout_ms,
    )
    pump(300)
    if not ok:
        log.warning("  Ingestion wait timed out for %s", filepath)
    return dlg


def do_import_to_shell(dlg, shell) -> None:
    """Wire dlg -> shell and trigger the import programmatically."""
    dlg.session_imported.connect(shell._on_session_imported)
    dlg._do_import()
    pump(2000)  # Let the session load into the app


def apply_rigol_mapping(dlg) -> None:
    """Apply CH1(V)->v_an, CH2(V)->v_bn, CH3(V)->v_cn mapping."""
    if dlg._dataset is None:
        return
    dlg._apply_rigol_mapping()
    pump(200)


# ── Conversion helper for overlay (without going through dialog import flow) ──

def ingest_and_convert(
    filepath: str,
    mapping: dict | None = None,
    scale_factors: dict | None = None,
):
    """
    Ingest a file and convert to capsule dict for direct studio loading.
    Returns (capsule_dict, mapped_dataset).
    """
    from src.file_ingestion import ingest_file
    from src.channel_mapping import ChannelMapper, UNMAPPED
    from src.dataset_converter import dataset_to_session
    import numpy as _np

    ds = ingest_file(filepath)
    mapper = ChannelMapper()
    suggested = mapper.auto_suggest(ds.raw_headers)
    if mapping:
        suggested.update(mapping)

    # Auto-detect ×100 probe attenuation for Rigol CSV voltage channels
    if scale_factors is None and ds.source_type == "rigol_csv":
        _VOLTAGE_CANONICAL = {"v_an", "v_bn", "v_cn", "v_ab", "v_bc", "v_ca"}
        mapped_voltage = {
            tgt: src for src, tgt in suggested.items()
            if tgt in _VOLTAGE_CANONICAL and src in ds.channels
        }
        if mapped_voltage:
            first_src = next(iter(mapped_voltage.values()))
            rms = float(_np.sqrt(_np.mean(ds.channels[first_src].astype(_np.float64) ** 2)))
            if 0.0 < rms < 5.0:
                scale_factors = {ch: 100.0 for ch in mapped_voltage}
                log.info("  Auto scale ×100 for %s (raw RMS=%.3f V)", list(mapped_voltage), rms)

    mapped_ds = mapper.apply(ds, suggested, scale_factors=scale_factors)
    capsule = dataset_to_session(mapped_ds)
    capsule["_dataset"] = mapped_ds
    return capsule, mapped_ds


# ── Main capture sequence ──────────────────────────────────────────────────

def main() -> None:
    app = QApplication(sys.argv)

    log.info("Launching AppShell ...")
    from ui.app_shell import AppShell
    shell = AppShell(enable_3d=False)  # disable OpenGL 3D for speed
    shell.showMaximized()
    pump(800)

    studio = shell._replay.studio

    # ── SHOT 1 - Empty home/overview ───────────────────────────────────────
    log.info("=== Shot 01: home_overview_empty ===")
    shell._navigate("overview")
    pump(400)
    save(shell, "01_home_overview_empty.png")

    # ── Open ImportDialog for RigolDS0 ─────────────────────────────────────
    log.info("=== Shot 02 + 03: import_dialog_rigol ===")
    dlg0 = open_and_ingest(RIGOL0, parent=shell, timeout_ms=30_000)

    # SHOT 2 — dialog with file loaded, before mapping
    save(dlg0, "02_import_dialog_rigol_ds0.png")

    # Apply the 3-phase mapping
    apply_rigol_mapping(dlg0)

    # SHOT 3 — dialog with mapping applied
    save(dlg0, "03_import_dialog_rigol_mapped.png")

    # Import into app
    log.info("  Importing RigolDS0 into app ...")
    do_import_to_shell(dlg0, shell)
    dlg0.close()

    # ── SHOT 4 - Dataset overview post-import ──────────────────────────────
    log.info("=== Shot 04: dataset_overview ===")
    shell._navigate("overview")
    pump(600)
    save(shell, "04_dataset_overview_rigol_ds0.png")

    # ── Navigate to Replay, wait for waveforms ─────────────────────────────
    log.info("=== Shots 05-06: replay waveforms ===")
    shell._navigate("replay")
    studio.tabs.setCurrentIndex(0)  # "Replay" tab
    pump(1500)
    # Force autoRange again after initial render — headless Qt can defer it
    studio._reset_zoom()
    pump(800)

    # Explicitly force the viewport to the actual data bounds.
    # autoRange() can silently fail when called before the tab's plots have
    # had their first paint (we were on the overview page during import).
    primary_s = next((s for s in studio.sessions if s.get("is_primary")), None)
    if primary_s:
        frames = primary_s["frames"]
        t0_frame = frames[0]["ts"]
        t_end_frame = frames[-1]["ts"] - t0_frame
        log.info("  Forcing x-range [0, %.4f] on waveform plots", t_end_frame)
        for p in (studio.plot_wave, studio.plot_line,
                  studio.plot_current, studio.plot_aux):
            p.getViewBox().setAutoVisible(y=True)
        studio.plot_wave.setXRange(t0_frame, t0_frame + t_end_frame, padding=0.05)
        pump(600)

    # SHOT 5 — Full replay tab (shows phase + line-to-line + current plots)
    save(shell, "05_replay_phase_voltages.png")

    # SHOT 6 — Line-to-line fills the window (hide other plots temporarily)
    studio.plot_wave.hide()
    studio.plot_current.hide()
    studio.plot_aux.hide()
    pump(400)
    # Re-apply x-range on plot_line (now the only visible linked plot)
    if primary_s:
        studio.plot_line.setXRange(t0_frame, t0_frame + t_end_frame, padding=0.05)
        studio.plot_line.getViewBox().setAutoVisible(y=True)
        pump(300)
    save(shell, "06_replay_line_to_line.png")
    studio.plot_wave.show()
    studio.plot_current.show()
    studio.plot_aux.show()
    pump(200)

    # ── SHOT 7 - Metrics ───────────────────────────────────────────────────
    log.info("=== Shot 07: metrics ===")
    studio.tabs.setCurrentIndex(1)  # "Metrics" tab
    # Wait for background analysis to complete (metrics table will have rows)
    wait_until(
        lambda: studio._metrics_table.rowCount() > 0,
        timeout_ms=20_000,
    )
    pump(500)
    save(shell, "07_metrics_summary.png")

    # ── SHOT 8 - Compliance ─────────────────────────────────────────────────
    log.info("=== Shot 08: compliance ===")
    shell._navigate("compliance")
    pump(600)

    compliance_page = shell._compliance
    # Try clicking "Run Tests" / "Run Checks" button if present
    for btn in compliance_page.findChildren(QPushButton):
        txt = btn.text().lower()
        if any(k in txt for k in ("run", "test", "check", "evaluate")):
            if btn.isEnabled() and btn.isVisible():
                log.info("  Clicking compliance button: %r", btn.text())
                btn.click()
                pump(3000)
                break
    save(shell, "08_compliance_table.png")

    # ── SHOT 9 - Comparison (DS0 vs DS1) ───────────────────────────────────
    log.info("=== Shot 09: comparison ===")
    shell._navigate("replay")
    pump(400)

    # Import DS1 as overlay directly into the studio (background thread)
    log.info("  Ingesting RigolDS1 for comparison overlay ...")
    try:
        rigol_mapping = {"CH1(V)": "v_an", "CH2(V)": "v_bn", "CH3(V)": "v_cn"}
        capsule1, _ = ingest_and_convert(RIGOL1, mapping=rigol_mapping)
        studio.load_session_from_dict(
            capsule1,
            label=os.path.splitext(os.path.basename(RIGOL1))[0],
            is_primary=False,
        )
        pump(1500)
        studio.tabs.setCurrentIndex(3)  # "Compare" tab
        pump(400)

        # Click the Compare button to populate overlay + delta plots
        cp = studio._comparison_tab
        if cp._btn_compare.isEnabled():
            log.info("  Clicking Compare button ...")
            cp._btn_compare.click()
            pump(1200)
            # Set x-range on comparison plots based on DS0 time range
            if primary_s:
                t0_c = primary_s["frames"][0]["ts"]
                t_end_c = primary_s["frames"][-1]["ts"] - t0_c
                cp._plot_overlay.setXRange(t0_c, t0_c + t_end_c, padding=0.05)
                cp._plot_delta.setXRange(t0_c, t0_c + t_end_c, padding=0.05)
                pump(400)
        else:
            log.warning("  Compare button not enabled — skipping comparison click")
    except Exception as e:
        log.error("  Could not load DS1 overlay: %s", e)
    save(shell, "09_comparison_normal_vs_fault.png")

    # ── SHOT 10 - Quick Export (no dialog, no blocking QMessageBox) ────────────
    log.info("=== Shot 10: export_complete ===")
    shell._navigate("replay")
    pump(300)
    studio.tabs.setCurrentIndex(0)

    export_result = None
    try:
        from src.session_exporter import quick_export as _quick_export
        primary = next((s for s in studio.sessions if s.get('is_primary')), None)
        if primary:
            capsule = primary.get('data', {})
            events  = primary.get('_events', [])
            export_result = _quick_export(
                capsule,
                events=events,
                base_dir="artifacts/evidence_exports",
            )
            log.info("  Quick export complete: %s", export_result['export_dir'])
        else:
            log.warning("  No primary session found for export")
    except Exception as exc:
        log.error("  Quick export failed: %s", exc)

    # Build a result display widget — no blocking dialog
    from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame
    from PyQt6.QtCore import Qt as _Qt

    result_widget = QWidget()
    result_widget.setWindowTitle("Evidence Package — Export Complete")
    result_widget.setFixedSize(960, 580)
    result_widget.setStyleSheet(
        "QWidget { background: #0b0f14; color: #e2e8f0; font-family: 'Segoe UI', sans-serif; }"
    )
    vlayout = QVBoxLayout(result_widget)
    vlayout.setContentsMargins(30, 25, 30, 25)
    vlayout.setSpacing(4)

    if export_result:
        title = QLabel("✓  Evidence Package Exported")
        title.setStyleSheet(
            "font-size: 17pt; font-weight: bold; color: #22c55e; padding-bottom: 4px;"
        )
        vlayout.addWidget(title)

        path_lbl = QLabel(export_result['export_dir'])
        path_lbl.setStyleSheet("color: #94a3b8; font-size: 8pt; padding-bottom: 10px;")
        path_lbl.setWordWrap(True)
        vlayout.addWidget(path_lbl)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #1e293b;")
        vlayout.addWidget(sep)
        vlayout.addSpacing(6)

        for a in export_result['artifacts']:
            size_kb = a['size_bytes'] // 1024 or 1
            row_lbl = QLabel(
                f"  ✓   {a['name']:<30}  {size_kb:>5} KB   —   {a['description']}"
            )
            row_lbl.setStyleSheet(
                "color: #cbd5e1; font-family: 'Consolas', monospace; font-size: 9pt;"
                " padding: 2px 0;"
            )
            vlayout.addWidget(row_lbl)

        vlayout.addSpacing(10)
        total_kb = export_result['total_bytes'] // 1024
        total_lbl = QLabel(
            f"Total: {total_kb:,} KB  ·  {len(export_result['artifacts'])} artifacts"
        )
        total_lbl.setStyleSheet("color: #64748b; font-size: 8pt;")
        vlayout.addWidget(total_lbl)
    else:
        vlayout.addWidget(QLabel("Export failed — see log"))

    result_widget.show()
    pump(600)
    save(result_widget, "10_export_complete.png")
    result_widget.close()

    # ── SHOTS 11-14 - Simulation datasets ──────────────────────────────────
    for shot_num, filepath, prefix in [
        (11, POWER,  "11_simulation_import_power"),
        (12, POWER,  "12_simulation_analysis_power"),
        (13, FREQ_S, "13_simulation_import_frequency"),
        (14, FREQ_S, "14_simulation_analysis_frequency"),
    ]:
        log.info("=== Shot %02d: %s ===", shot_num, prefix)
        if not os.path.exists(filepath):
            log.warning("  File missing: %s -- skipping", filepath)
            continue

        if shot_num in (11, 13):
            # Import dialog shot
            dlg_s = open_and_ingest(filepath, parent=shell, timeout_ms=15_000)
            save(dlg_s, prefix + ".png")
            # Import into the app for the analysis shots
            log.info("  Importing %s into app ...", os.path.basename(filepath))
            do_import_to_shell(dlg_s, shell)
            dlg_s.close()
        else:
            # Analysis shot — navigate to replay
            shell._navigate("replay")
            studio.tabs.setCurrentIndex(0)  # "Replay" tab
            pump(1200)
            studio._reset_zoom()
            pump(500)
            # Force viewport after tab switch (same headless issue as shots 05-06)
            sim_primary = next((s for s in studio.sessions if s.get("is_primary")), None)
            if sim_primary:
                sim_frames = sim_primary["frames"]
                st0 = sim_frames[0]["ts"]
                st_end = sim_frames[-1]["ts"] - st0
                for p in (studio.plot_wave, studio.plot_line,
                          studio.plot_current, studio.plot_aux):
                    p.getViewBox().setAutoVisible(y=True)
                studio.plot_wave.setXRange(st0, st0 + st_end, padding=0.05)
                pump(500)
            save(shell, prefix + ".png")

    # ── Done ───────────────────────────────────────────────────────────────
    log.info("=== All captures complete ===")
    saved = sorted(f for f in os.listdir(OUT_DIR) if f.endswith(".png"))
    log.info("Output folder: %s", OUT_DIR)
    for fname in saved:
        size_kb = os.path.getsize(os.path.join(OUT_DIR, fname)) // 1024
        log.info("  %-50s  %4d KB", fname, size_kb)

    app.quit()


if __name__ == "__main__":
    main()
