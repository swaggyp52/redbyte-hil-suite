import json
import time

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QApplication

from ui.phasor_view import PhasorView
from ui.replay_studio import ReplayStudio
from src.recorder import Recorder


class FakeSerialMgr(QObject):
    frame_received = pyqtSignal(dict)


def _ensure_app():
    app = QApplication.instance()
    if not app:
        app = QApplication([])
    return app


def test_phasor_and_replay_smoke(tmp_path):
    _ensure_app()

    serial_mgr = FakeSerialMgr()
    recorder = Recorder()

    phasor = PhasorView(serial_mgr)
    replay = ReplayStudio(recorder, serial_mgr)

    # Emit a few frames to populate buffers
    frames = []
    base_ts = time.time()
    for i in range(60):
        t = base_ts + i * 0.02
        frames.append({
            "ts": t,
            "v_an": 120.0,
            "v_bn": -60.0,
            "v_cn": -60.0,
            "i_a": 5.0,
            "i_b": -2.5,
            "i_c": -2.5,
            "freq": 60.0,
            "p_mech": 1000.0,
        })
        serial_mgr.frame_received.emit(frames[-1])

    # Build a session file for replay
    session_path = tmp_path / "session.json"
    session_path.write_text(json.dumps({"frames": frames, "events": []}))

    # Load into replay studio
    replay._load_session(str(session_path), is_primary=True)

    # Ensure internal state updated
    assert replay.sessions
    assert replay.active_session == 0
    assert len(replay.sessions[0]["frames"]) == len(frames)

    # Ensure phasor buffer filled
    assert len(phasor._buf["v_a"]) > 0
