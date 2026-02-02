import time
import logging
import threading
from PyQt6.QtCore import QObject, pyqtSignal
from src.io_adapter import SerialAdapter, DemoAdapter, OpalRTAdapter

logger = logging.getLogger(__name__)


class SerialManager(QObject):
    frame_received = pyqtSignal(dict)
    connection_status = pyqtSignal(bool, str)

    def __init__(self):
        super().__init__()
        self.adapter = None
        self.running = False
        self.thread = None
        self.lock = threading.Lock()

    def connect_serial(self, port_name="COM3"):
        """Connects using the specified port. If MOCK, uses DemoAdapter."""
        with self.lock:
            if self.running:
                self._stop_internal()

            if port_name == "MOCK":
                self.adapter = DemoAdapter()
                config = {}
            elif port_name == "OPAL":
                self.adapter = OpalRTAdapter()
                config = {}
            else:
                self.adapter = SerialAdapter()
                config = {"port": port_name, "baud": 115200}

            if self.adapter.connect(config):
                self.running = True
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

    def _reader_loop(self):
        while self.running:
            with self.lock:
                adapter = self.adapter
            if adapter:
                frame = adapter.read_frame()
                if frame:
                    self.frame_received.emit(frame)
                else:
                    time.sleep(0.001)
            else:
                break
