import abc
import time
import math
import random
import json
import socket
import struct
import logging

logger = logging.getLogger(__name__)


class IOAdapter(abc.ABC):
    @abc.abstractmethod
    def connect(self, config):
        pass

    @abc.abstractmethod
    def disconnect(self):
        pass

    @abc.abstractmethod
    def read_frame(self):
        """Returns a dict frame or None."""
        pass

    def write_command(self, command_type, payload=None):
        """
        Sends a command to the connected hardware.

        Args:
            command_type: String command identifier (e.g. 'fault_sag', 'set_freq').
            payload: Optional dict of parameters.

        Returns:
            bool: True if command was sent successfully.
        """
        logger.warning(f"write_command not supported by {self.__class__.__name__}")
        return False


class DemoAdapter(IOAdapter):
    def __init__(self):
        self.start_time = 0
        self._fault_active = False
        self._fault_type = None
        self._fault_start = 0
        self._fault_duration = 0.5
        self._freq_offset = 0.0
        self._angle = 0.0
        self._phase_offsets = {'a': 0.0, 'b': -2.0944, 'c': 2.0944}
        self._phase_jump = 0.0
        self._unbalance = {'a': 1.0, 'b': 1.0, 'c': 1.0}
        self._waveform_override = None
        self._fault_timeline = []
        self.command_log = []

    def connect(self, config):
        logger.info("DemoAdapter connected.")
        self.start_time = time.time()
        self._fault_active = False
        self._freq_offset = 0.0
        self._angle = 0.0
        self._phase_jump = 0.0
        self._unbalance = {'a': 1.0, 'b': 1.0, 'c': 1.0}
        self._waveform_override = None
        self._fault_timeline = []
        self.command_log = []
        return True

    def disconnect(self):
        logger.info("DemoAdapter disconnected.")

    def write_command(self, command_type, payload=None):
        """DemoAdapter handles commands by modifying its internal signal generation."""
        payload = payload or {}
        self.command_log.append({"ts": time.time(), "cmd": command_type, "params": payload})
        if command_type in ('fault_sag', 'inject_sag'):
            self._fault_active = True
            self._fault_type = 'sag'
            self._fault_start = time.time()
            self._fault_duration = payload.get('duration', 0.5)
            logger.info(f"DemoAdapter: Injecting voltage sag for {self._fault_duration}s")
            self._fault_timeline.append({"ts": self._fault_start, "type": "sag", "duration": self._fault_duration})
            return True
        elif command_type in ('fault_drift', 'inject_drift'):
            self._fault_active = True
            self._fault_type = 'drift'
            self._fault_start = time.time()
            self._fault_duration = payload.get('duration', 2.0)
            self._freq_offset = payload.get('offset', 2.0)
            logger.info(f"DemoAdapter: Injecting freq drift {self._freq_offset}Hz")
            self._fault_timeline.append({"ts": self._fault_start, "type": "drift", "duration": self._fault_duration, "offset": self._freq_offset})
            return True
        elif command_type in ('fault_phase_jump', 'inject_phase_jump'):
            self._phase_jump = math.radians(payload.get('degrees', 15.0))
            logger.info(f"DemoAdapter: Phase jump {payload.get('degrees', 15.0)} deg")
            self._fault_timeline.append({"ts": time.time(), "type": "phase_jump", "degrees": payload.get('degrees', 15.0)})
            return True
        elif command_type in ('fault_unbalance', 'inject_unbalance'):
            self._unbalance['a'] = float(payload.get('a', 1.0))
            self._unbalance['b'] = float(payload.get('b', 0.9))
            self._unbalance['c'] = float(payload.get('c', 1.1))
            logger.info("DemoAdapter: Unbalance applied")
            self._fault_timeline.append({"ts": time.time(), "type": "unbalance", "params": self._unbalance.copy()})
            return True
        elif command_type == 'clear_fault':
            self._fault_active = False
            self._fault_type = None
            self._freq_offset = 0.0
            self._phase_jump = 0.0
            self._unbalance = {'a': 1.0, 'b': 1.0, 'c': 1.0}
            self._waveform_override = None
            logger.info("DemoAdapter: Faults cleared")
            return True
        elif command_type == 'inject_waveform':
            self._waveform_override = {
                "start": time.time(),
                "duration": float(payload.get('duration', 1.0)),
                "freq": float(payload.get('freq', 60.0)),
                "amplitude": float(payload.get('amplitude', 170.0)),
                "noise": float(payload.get('noise', 0.0)),
            }
            self._fault_timeline.append({"ts": time.time(), "type": "waveform", "params": self._waveform_override.copy()})
            return True
        else:
            logger.warning(f"DemoAdapter: Unknown command '{command_type}'")
            return False

    def read_frame(self):
        t = time.time()
        ts = t - self.start_time
        freq = 60.0 + 0.1 * math.sin(t * 0.5)

        # Demo profile: periodic drift and sag even without manual commands
        auto_drift = 2.0 if 4.0 <= ts <= 6.0 else 0.0
        auto_sag = 0.6 if 7.0 <= ts <= 8.0 else 1.0

        # Apply active fault effects
        v_scale = 1.0
        if self._fault_active:
            elapsed = t - self._fault_start
            if elapsed > self._fault_duration:
                self._fault_active = False
                self._fault_type = None
                self._freq_offset = 0.0
            elif self._fault_type == 'sag':
                v_scale = 0.5
            elif self._fault_type == 'drift':
                # gradual drift ramp
                ramp = min(1.0, elapsed / max(self._fault_duration, 0.1))
                freq += self._freq_offset * ramp
        else:
            freq += auto_drift
            v_scale *= auto_sag

        omega = 2 * math.pi * freq

        # Integrate rotor angle for 3D visualization
        self._angle = (self._angle + omega * 0.02) % (2 * math.pi)

        # Waveform override (from Signal Sculptor)
        if self._waveform_override:
            ovr = self._waveform_override
            if t - ovr["start"] > ovr["duration"]:
                self._waveform_override = None
            else:
                freq = ovr["freq"]
                omega = 2 * math.pi * freq
                v_scale = 1.0

        # 3-Phase Voltages (120V RMS -> 169.7V peak)
        v_peak = 120.0 * math.sqrt(2) * v_scale
        phase_jump = self._phase_jump
        v_an = v_peak * self._unbalance['a'] * math.sin(omega * ts + phase_jump)
        v_bn = v_peak * self._unbalance['b'] * math.sin(omega * ts + self._phase_offsets['b'] + phase_jump)
        v_cn = v_peak * self._unbalance['c'] * math.sin(omega * ts + self._phase_offsets['c'] + phase_jump)

        # 3-Phase Currents (5A RMS -> 7.07A peak, slight lag)
        i_peak = 5.0 * math.sqrt(2)
        i_a = i_peak * math.sin(omega * ts - 0.1 + phase_jump)
        i_b = i_peak * math.sin(omega * ts - 2.0944 - 0.1 + phase_jump)
        i_c = i_peak * math.sin(omega * ts + 2.0944 - 0.1 + phase_jump)

        # Realistic noise on all channels
        noise_v = 0.3
        if self._waveform_override:
            noise_v = float(self._waveform_override.get("noise", 0.0))

        v_an += random.gauss(0, noise_v)
        v_bn += random.gauss(0, noise_v)
        v_cn += random.gauss(0, noise_v)
        i_a += random.gauss(0, 0.02)
        i_b += random.gauss(0, 0.02)
        i_c += random.gauss(0, 0.02)

        # 5th harmonic distortion (~3% of fundamental)
        v_an += v_peak * 0.03 * math.sin(5 * omega * ts)
        v_bn += v_peak * 0.03 * math.sin(5 * (omega * ts - 2.0944))
        v_cn += v_peak * 0.03 * math.sin(5 * (omega * ts + 2.0944))
        # 7th harmonic distortion (~2% of fundamental)
        v_an += v_peak * 0.02 * math.sin(7 * omega * ts)
        v_bn += v_peak * 0.02 * math.sin(7 * (omega * ts - 2.0944))
        v_cn += v_peak * 0.02 * math.sin(7 * (omega * ts + 2.0944))

        frame = {
            "ts": t,
            "v_an": v_an, "v_bn": v_bn, "v_cn": v_cn,
            "i_a": i_a, "i_b": i_b, "i_c": i_c,
            "freq": freq,
            "angle": math.degrees(self._angle),
            "p_mech": 1000.0 + 10 * math.sin(t * 0.3),
            "status": 1 if self._fault_active else 0,
            "fault_type": self._fault_type if self._fault_active else None,
        }
        time.sleep(0.02)  # 50Hz throttle
        return frame


class SerialAdapter(IOAdapter):
    COMMAND_PREFIX = b"CMD:"

    def __init__(self):
        self.conn = None

    def connect(self, config):
        import serial
        port = config.get("port", "COM3")
        baud = config.get("baud", 115200)
        try:
            self.conn = serial.Serial(port, baud, timeout=0.1)
            logger.info(f"SerialAdapter connected to {port}")
            return True
        except Exception as e:
            logger.error(f"Serial connect failed: {e}")
            return False

    def disconnect(self):
        if self.conn:
            self.conn.close()
            self.conn = None

    def read_frame(self):
        if not self.conn:
            return None
        try:
            line = self.conn.readline()
            if not line:
                return None
            return json.loads(line.decode('utf-8').strip())
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None
        except Exception:
            return None

    def write_command(self, command_type, payload=None):
        """
        Sends a command over serial as JSON.
        Protocol: CMD:{json}\n
        """
        if not self.conn:
            logger.error("SerialAdapter: Not connected, cannot send command")
            return False
        try:
            cmd = {"cmd": command_type}
            if payload:
                cmd.update(payload)
            raw = self.COMMAND_PREFIX + json.dumps(cmd).encode('utf-8') + b"\n"
            self.conn.write(raw)
            self.conn.flush()
            logger.info(f"SerialAdapter: Sent command '{command_type}'")
            return True
        except Exception as e:
            logger.error(f"SerialAdapter: write_command failed: {e}")
            return False


class OpalRTAdapter(IOAdapter):
    """
    TCP-based adapter for OPAL-RT real-time simulator.
    Connects to OPAL-RT's asynchronous data server which streams
    signal values as length-prefixed JSON over TCP.
    """

    HEADER_FMT = '>I'  # 4-byte big-endian message length
    HEADER_SIZE = struct.calcsize(HEADER_FMT)

    def __init__(self):
        self.sock = None
        self.host = "127.0.0.1"
        self.port = 5100
        self.timeout = 1.0
        self._buffer = b""
        self._connected = False

    def connect(self, config):
        self.host = config.get("host", "127.0.0.1")
        self.port = config.get("port", 5100)
        self.timeout = config.get("timeout", 1.0)
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(self.timeout)
            self.sock.connect((self.host, self.port))
            self._connected = True
            logger.info(f"OpalRTAdapter connected to {self.host}:{self.port}")
            return True
        except ConnectionRefusedError:
            logger.warning(f"OpalRTAdapter: Connection refused at {self.host}:{self.port} (is OPAL-RT running?)")
            self._connected = False
            return False
        except socket.timeout:
            logger.warning(f"OpalRTAdapter: Connection timed out to {self.host}:{self.port}")
            self._connected = False
            return False
        except Exception as e:
            logger.error(f"OpalRTAdapter connect error: {e}")
            self._connected = False
            return False

    def disconnect(self):
        self._connected = False
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None

    def read_frame(self):
        """
        Reads a length-prefixed JSON frame from the TCP stream.
        Protocol: [4-byte big-endian length][JSON payload bytes]
        """
        if not self._connected or not self.sock:
            return None
        try:
            while len(self._buffer) < self.HEADER_SIZE:
                chunk = self.sock.recv(4096)
                if not chunk:
                    self._connected = False
                    return None
                self._buffer += chunk

            msg_len = struct.unpack(self.HEADER_FMT, self._buffer[:self.HEADER_SIZE])[0]
            self._buffer = self._buffer[self.HEADER_SIZE:]

            while len(self._buffer) < msg_len:
                chunk = self.sock.recv(4096)
                if not chunk:
                    self._connected = False
                    return None
                self._buffer += chunk

            payload = self._buffer[:msg_len]
            self._buffer = self._buffer[msg_len:]

            frame = json.loads(payload.decode('utf-8'))
            return frame

        except socket.timeout:
            return None
        except (json.JSONDecodeError, struct.error) as e:
            logger.warning(f"OpalRTAdapter: Malformed frame: {e}")
            self._buffer = b""
            return None
        except Exception as e:
            logger.error(f"OpalRTAdapter read error: {e}")
            self._connected = False
            return None

    def write_command(self, command_type, payload=None):
        """Sends a length-prefixed JSON command to OPAL-RT."""
        if not self._connected or not self.sock:
            logger.error("OpalRTAdapter: Not connected")
            return False
        try:
            cmd = {"cmd": command_type}
            if payload:
                cmd.update(payload)
            data = json.dumps(cmd).encode('utf-8')
            header = struct.pack(self.HEADER_FMT, len(data))
            self.sock.sendall(header + data)
            logger.info(f"OpalRTAdapter: Sent command '{command_type}'")
            return True
        except Exception as e:
            logger.error(f"OpalRTAdapter write_command failed: {e}")
            return False
