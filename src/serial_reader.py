import time
import logging
import threading
from dataclasses import dataclass, field
from collections import deque
from PyQt6.QtCore import QObject, pyqtSignal
from src.io_adapter import SerialAdapter, DemoAdapter, OpalRTAdapter
from src.models import normalize_frame, present_canonical_keys

logger = logging.getLogger(__name__)

# Keep the most recent N frame timestamps for rolling fps estimate
_FPS_WINDOW = 20


@dataclass
class LiveStats:
    """Snapshot of live telemetry session statistics.

    Attributes:
        source:           Adapter label — 'DEMO', 'SERIAL', 'OPAL-RT', etc.
        connected:        Whether the adapter is currently running.
        fps:              Rolling frames-per-second estimate.
        frame_count:      Total frames received in the current session.
        present_channels: Canonical channel names that had real source data
                          (not zero-filled by normalize_frame).
        last_frame_age:   Seconds since the last frame was received (0 if none).
        session_start_ts: Unix timestamp when the session started.
        warnings:         Human-readable warnings (e.g. "DC bus only").
    """
    source:           str              = "—"
    connected:        bool             = False
    fps:              float            = 0.0
    frame_count:      int              = 0
    present_channels: frozenset        = field(default_factory=frozenset)
    last_frame_age:   float            = 0.0
    session_start_ts: float            = 0.0
    warnings:         list[str]        = field(default_factory=list)


class SerialManager(QObject):
    frame_received = pyqtSignal(dict)
    connection_status = pyqtSignal(bool, str)
    # Emitted ~every second while connected, carrying a LiveStats snapshot.
    live_stats_updated = pyqtSignal(object)

    def __init__(self):
        super().__init__()
        self.adapter = None
        self.running = False
        self.thread = None
        self.lock = threading.Lock()

        # Live session stats (reset each connect)
        self._source_label: str = "—"
        self._frame_count: int = 0
        self._ts_window: deque = deque(maxlen=_FPS_WINDOW)
        self._present_channels: set = set()
        self._last_frame_wall: float = 0.0
        self._session_start: float = 0.0
        self._warnings: list[str] = []

    # ──────────────────────────────────────────────────────────────
    # Connection management
    # ──────────────────────────────────────────────────────────────

    def connect_serial(self, port_name="COM3"):
        """Connects using the specified port. If MOCK, uses DemoAdapter."""
        with self.lock:
            if self.running:
                self._stop_internal()

            self._reset_stats()

            if port_name == "MOCK":
                self.adapter = DemoAdapter()
                config = {}
                self._source_label = "DEMO"
            elif port_name == "OPAL":
                self.adapter = OpalRTAdapter()
                config = {}
                self._source_label = "OPAL-RT"
            else:
                self.adapter = SerialAdapter()
                config = {"port": port_name, "baud": 115200}
                self._source_label = f"SERIAL:{port_name}"

            if self.adapter.connect(config):
                self.running = True
                self._session_start = time.time()
                self.thread = threading.Thread(target=self._reader_loop, daemon=True)
                self.thread.start()
                self.connection_status.emit(True, port_name)
            else:
                logger.error(f"Failed to connect adapter: {port_name}")
                self.adapter = None
                self.connection_status.emit(False, port_name)

    def start_mock_mode(self):
        self.connect_serial("MOCK")

    def stop_mock_mode(self):
        """Stops mock mode without attempting to reconnect to hardware."""
        self.stop()

    def disconnect_serial(self):
        self.stop()

    def stop(self):
        with self.lock:
            self._stop_internal()

    def _stop_internal(self):
        """Must be called with self.lock held or from within lock context."""
        self.running = False
        thread = self.thread
        self.thread = None
        if thread:
            # Release lock briefly to allow reader thread to exit
            self.lock.release()
            thread.join(timeout=1.0)
            self.lock.acquire()
        if self.adapter:
            self.adapter.disconnect()
            self.adapter = None

    def write_command(self, command_type, payload=None):
        """Sends a command to the current adapter."""
        with self.lock:
            if self.adapter:
                return self.adapter.write_command(command_type, payload)
        logger.warning("write_command called with no active adapter")
        return False

    # ──────────────────────────────────────────────────────────────
    # Stats
    # ──────────────────────────────────────────────────────────────

    def get_live_stats(self) -> LiveStats:
        """Return a snapshot of live session statistics (thread-safe copy)."""
        now = time.time()
        age = (now - self._last_frame_wall) if self._last_frame_wall > 0 else 0.0
        return LiveStats(
            source=self._source_label,
            connected=self.running,
            fps=self._compute_fps(),
            frame_count=self._frame_count,
            present_channels=frozenset(self._present_channels),
            last_frame_age=age,
            session_start_ts=self._session_start,
            warnings=list(self._warnings),
        )

    def _reset_stats(self) -> None:
        self._frame_count = 0
        self._ts_window.clear()
        self._present_channels = set()
        self._last_frame_wall = 0.0
        self._session_start = 0.0
        self._warnings = []

    def _compute_fps(self) -> float:
        if len(self._ts_window) < 2:
            return 0.0
        span = self._ts_window[-1] - self._ts_window[0]
        if span <= 0:
            return 0.0
        return round((len(self._ts_window) - 1) / span, 1)

    def _update_stats(self, raw_frame: dict, normalized: dict) -> None:
        """Update internal stats from a freshly-read raw+normalized frame pair."""
        self._frame_count += 1
        self._last_frame_wall = time.time()
        ts = normalized.get("ts", 0.0)
        if ts > 0:
            self._ts_window.append(ts)

        # Track which canonical channels had real source data in this raw frame
        new_channels = present_canonical_keys(raw_frame)
        self._present_channels.update(new_channels)

        # Warn once if only DC-bus channels present (no 3-phase voltages/currents)
        if not self._warnings and new_channels:
            three_phase_v = {"v_an", "v_bn", "v_cn"}
            three_phase_i = {"i_a", "i_b", "i_c"}
            has_v = bool(new_channels & three_phase_v)
            has_i = bool(new_channels & three_phase_i)
            has_dc = "v_dc" in new_channels
            if has_dc and not has_v and not has_i:
                self._warnings.append(
                    "DC bus only — phase voltages/currents are 0-filled (breadboard hardware)"
                )
            elif not has_v and not has_i:
                self._warnings.append(
                    "No phase voltages or currents detected — check hardware connection"
                )

    # ──────────────────────────────────────────────────────────────
    # Reader thread
    # ──────────────────────────────────────────────────────────────

    def _reader_loop(self):
        last_stats_emit = time.time()
        while self.running:
            with self.lock:
                adapter = self.adapter
            if adapter:
                raw_frame = adapter.read_frame()
                if raw_frame:
                    # Normalize raw frames from all adapters to canonical keys.
                    # DemoAdapter already emits canonical keys; SerialAdapter
                    # and OpalRTAdapter return raw hardware JSON that may use
                    # non-canonical field names (e.g. t_ms, vdc, p_kw).
                    normalized = normalize_frame(raw_frame)
                    self._update_stats(raw_frame, normalized)
                    self.frame_received.emit(normalized)

                    # Emit stats snapshot ~once per second
                    now = time.time()
                    if now - last_stats_emit >= 1.0:
                        self.live_stats_updated.emit(self.get_live_stats())
                        last_stats_emit = now
                else:
                    time.sleep(0.001)
            else:
                break
