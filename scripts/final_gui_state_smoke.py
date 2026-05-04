"""
Final GUI-state smoke checks for offline analysis workflow.

This script validates replay-readiness using real import paths and catches
cases where data exists but default replay state would render blank/off-range.
"""

from __future__ import annotations

import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QApplication

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.channel_mapping import (
    ChannelMapper,
    UNMAPPED,
    apply_rigol_three_phase_defaults,
)
from src.dataset_converter import dataset_to_session
from src.file_ingestion import ingest_file
from src.recorder import Recorder
from src.session_state import ActiveSession
from ui.replay_studio import ReplayStudio


DATA_ROOT = Path(r"C:\Users\conno\OneDrive - Gannon University\Spring 2026\Senior Design")
DS0_PATH = DATA_ROOT / "RigolDS0.csv"
DS1_PATH = DATA_ROOT / "RigolDS1.csv"
INV_PWR_PATH = DATA_ROOT / "InverterPower_Simulation.xlsx"
VSG_FREQ_PATH = DATA_ROOT / "VSGFrequency_Simulation.xlsx"


class FakeSerialMgr(QObject):
    frame_received = pyqtSignal(dict)


@dataclass(frozen=True)
class CheckResult:
    ok: bool
    message: str


def _check(ok: bool, message: str) -> CheckResult:
    state = "PASS" if ok else "FAIL"
    print(f"[{state}] {message}")
    return CheckResult(ok=ok, message=message)


def _require_files() -> None:
    missing = [p for p in (DS0_PATH, DS1_PATH, INV_PWR_PATH, VSG_FREQ_PATH) if not p.exists()]
    if missing:
        joined = "\n".join(str(p) for p in missing)
        raise FileNotFoundError(f"Required smoke input file(s) missing:\n{joined}")


def _import_capsule(path: Path, mapping_overrides: dict[str, str]) -> tuple[dict, ActiveSession]:
    mapper = ChannelMapper()
    ds = ingest_file(str(path))
    mapping = mapper.auto_suggest(ds.raw_headers)
    mapping = apply_rigol_three_phase_defaults(ds.raw_headers, mapping)
    for key, value in mapping_overrides.items():
        if key in ds.raw_headers:
            mapping[key] = value

    scale_factors: dict[str, float] = {}
    if ds.source_type == "rigol_csv":
        mapped_voltage_channels = {
            target: src
            for src, target in mapping.items()
            if target in {"v_an", "v_bn", "v_cn", "v_ab", "v_bc", "v_ca"}
            and src in ds.channels
        }
        if mapped_voltage_channels:
            first_src = next(iter(mapped_voltage_channels.values()))
            first_arr = ds.channels[first_src]
            raw_rms = float(np.sqrt(np.mean(first_arr.astype(np.float64) ** 2)))
            if 0.0 < raw_rms < 5.0:
                for canonical in mapped_voltage_channels:
                    scale_factors[canonical] = 100.0

    mapped = mapper.apply(ds, mapping, scale_factors=scale_factors or None)
    capsule = dataset_to_session(mapped, session_id=path.stem)
    capsule["_dataset"] = mapped
    session = ActiveSession.from_capsule(capsule, label=path.name)
    return capsule, session


def _assert_channel_amplitude(dataset, channel: str, min_span: float) -> bool:
    arr = dataset.channels.get(channel)
    if arr is None:
        return False
    valid = arr[np.isfinite(arr)]
    if valid.size == 0:
        return False
    span = float(np.max(valid) - np.min(valid))
    return span > min_span


def _assert_replay_view_overlap(studio: ReplayStudio, session_end_s: float) -> bool:
    x_min, x_max = studio.plot_wave.viewRange()[0]
    # Must start at or near 0 and include the majority of the dataset span.
    return x_min <= 0.01 and x_max >= max(0.05, 0.8 * session_end_s)


def _drain_qt_events(duration_s: float = 0.6) -> None:
    app = QApplication.instance()
    if app is None:
        return
    deadline = time.time() + duration_s
    while time.time() < deadline:
        app.processEvents()
        time.sleep(0.02)


def _wait_for(condition, timeout_s: float = 2.0) -> bool:
    app = QApplication.instance()
    if app is None:
        return False
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            if condition():
                return True
        except Exception:
            pass
        app.processEvents()
        time.sleep(0.02)
    return False


def _visible_tab_names(tab_widget) -> list[str]:
    tab_bar = tab_widget.tabBar()
    return [
        tab_widget.tabText(i)
        for i in range(tab_widget.count())
        if tab_bar.isTabVisible(i)
    ]


def main() -> int:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    _require_files()

    app = QApplication.instance() or QApplication([])
    _ = app

    results: list[CheckResult] = []

    # 1) DS0 import and replay contract
    ds0_capsule, ds0_session = _import_capsule(DS0_PATH, {})
    ds0_dataset = ds0_capsule["_dataset"]
    ds0_time = ds0_dataset.time

    results.append(_check(ds0_session is not None, "DS0 import produces an active session"))
    results.append(_check(abs(float(ds0_time[0])) < 1e-6, "DS0 display_time starts at 0 s"))
    results.append(_check(0.095 <= float(ds0_time[-1]) <= 0.105, "DS0 display_time spans ~0.1 s"))

    ds0_channels = set(ds0_dataset.channels.keys())
    applied_map = ds0_capsule.get("import_meta", {}).get("applied_mapping", {})
    results.append(_check(applied_map.get("CH1(V)") == "v_an", "DS0 auto/default mapping applies CH1→v_an"))
    results.append(_check(applied_map.get("CH2(V)") == "v_bn", "DS0 auto/default mapping applies CH2→v_bn"))
    results.append(_check(applied_map.get("CH3(V)") == "v_cn", "DS0 auto/default mapping applies CH3→v_cn"))
    results.append(_check({"v_an", "v_bn", "v_cn"}.issubset(ds0_channels), "DS0 has mapped phase channels"))
    results.append(_check({"v_ab", "v_bc", "v_ca"}.issubset(ds0_channels), "DS0 has derived line-to-line channels"))
    results.append(_check(_assert_channel_amplitude(ds0_dataset, "v_an", min_span=10.0), "DS0 v_an waveform has nonzero amplitude"))
    results.append(_check(_assert_channel_amplitude(ds0_dataset, "v_ab", min_span=20.0), "DS0 v_ab waveform has nonzero amplitude"))

    studio = ReplayStudio(Recorder(), FakeSerialMgr())
    studio.load_session_from_dict(ds0_capsule, label=ds0_session.label, is_primary=True)
    metrics_ready = _wait_for(lambda: studio._metrics_table.rowCount() > 0, timeout_s=2.5)
    results.append(_check(_visible_tab_names(studio.tabs) == ["Replay", "Metrics", "Compare"], "Replay surface hides non-demo tabs"))
    results.append(_check(studio.chk_link_axes.isChecked(), "Replay exposes linked-axes toggle by default"))
    results.append(_check(metrics_ready, "Metrics table populated after DS0 import"))
    results.append(_check(studio.play_idx == 0 and abs(studio.scrubber.value()) < 1e-6, "Replay cursor resets to start after import"))
    results.append(_check(_assert_replay_view_overlap(studio, float(ds0_time[-1])), "Replay default view overlaps DS0 session range"))
    results.append(_check(bool(studio._metric_cards.get("phase_rms", None) and studio._metric_cards["phase_rms"].text() not in ("—", "N/A")), "Metrics summary card exposes DS0 phase RMS values"))
    results.append(_check(bool(studio._metric_cards.get("line_rms", None) and studio._metric_cards["line_rms"].text() not in ("—", "N/A")), "Metrics summary card exposes derived line-to-line RMS values"))

    # 2) Excel generic/power contract
    inv_capsule, _inv_session = _import_capsule(INV_PWR_PATH, {})
    inv_dataset = inv_capsule["_dataset"]
    has_p_mech = "p_mech" in inv_dataset.channels
    results.append(_check(has_p_mech, "InverterPower maps Pinv to p_mech"))
    results.append(_check(_assert_channel_amplitude(inv_dataset, "p_mech", min_span=1.0), "InverterPower p_mech has visible nonzero plot data"))

    vsg_capsule, _vsg_session = _import_capsule(VSG_FREQ_PATH, {})
    vsg_dataset = vsg_capsule["_dataset"]
    results.append(_check("p_mech" in vsg_dataset.channels, "VSGFrequency file still yields p_mech generic channel"))
    results.append(_check("freq" not in vsg_dataset.channels, "No false freq channel is fabricated when absent"))

    # 3) DS1 CH4 contract
    mapper = ChannelMapper()
    ds1_raw = ingest_file(str(DS1_PATH))
    ds1_suggested = mapper.auto_suggest(ds1_raw.raw_headers)
    ds1_suggested = apply_rigol_three_phase_defaults(ds1_raw.raw_headers, ds1_suggested)
    ds1_ch4_target = ds1_suggested.get("CH4(V)", UNMAPPED)
    results.append(_check(ds1_ch4_target in (UNMAPPED, "", None), "DS1 CH4 is not auto-mapped to v_dc"))

    ds1_capsule_auto, _ds1_session_auto = _import_capsule(DS1_PATH, {})
    ds1_auto_map = ds1_capsule_auto.get("import_meta", {}).get("applied_mapping", {})
    results.append(_check(ds1_auto_map.get("CH4(V)") in (UNMAPPED, "", None), "DS1 default mapping keeps CH4 unmapped"))
    results.append(_check("CH4(V)" in ds1_capsule_auto["_dataset"].channels, "DS1 preserves CH4 as generic/raw channel when unmapped"))

    ds1_capsule, _ds1_session = _import_capsule(
        DS1_PATH,
        {
            "CH1(V)": "v_an",
            "CH2(V)": "v_bn",
            "CH3(V)": "v_cn",
            "CH4(V)": "aux_ch4",
        },
    )
    ds1_dataset = ds1_capsule["_dataset"]
    results.append(_check("aux_ch4" in ds1_dataset.channels, "DS1 supports explicit aux_ch4 mapping for CH4"))

    # 4) Compare contract (A baseline + B overlay should auto-render)
    studio.load_session_from_dict(ds1_capsule, label="RigolDS1-overlay", is_primary=False)
    compare_ready = _wait_for(lambda: studio._comparison_tab._last_result is not None, timeout_s=3.0)
    results.append(_check(compare_ready, "Compare result populated after DS1 overlay load"))
    cmp_result = studio._comparison_tab._last_result
    results.append(_check(cmp_result is not None, "Compare state is populated when DS0 and DS1 are loaded"))
    if cmp_result is not None:
        first_channel = next(iter(cmp_result.channels.keys()), None)
        delta_x, delta_y = studio._comparison_tab._delta_curve.getData()
        results.append(_check(first_channel is not None, "Compare has at least one overlapping channel"))
        results.append(_check(delta_x is not None and len(delta_x) > 0 and delta_y is not None and len(delta_y) > 0, "Compare delta trace contains data"))

    failed = [r for r in results if not r.ok]
    if failed:
        print("\nRESULT: FAIL — one or more GUI-state smoke checks failed.")
        return 1

    print("\nRESULT: PASS — GUI-state smoke checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
