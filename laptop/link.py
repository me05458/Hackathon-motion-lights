"""Talks to the ESP32 over USB serial. NullLink is a stand-in for --no-serial mode."""
import time

import config
import protocol


class NullLink:
    """Stands in for the ESP32 when it isn't plugged in (--no-serial). Sends nothing.
    Number keys in main.py can set a pretend distance, so the pen can still be tried."""
    connected = False
    port = None

    def __init__(self):
        self.distance_cm = -1.0
        self.sim_cm = None               # pretend sensor reading, or None
        self.restarted = False
        self.readings_per_s = 0.0

    def write(self, data):
        pass

    def poll(self, now=None):
        """Returns new distance readings as [(cm, time), ...]."""
        if self.sim_cm is None:
            return []
        self.distance_cm = self.sim_cm
        return [(self.sim_cm, now if now is not None else time.monotonic())]

    def close(self):
        pass


def find_port():
    """Picks the most likely ESP32 port (CP210x / CH340 / FTDI USB-serial chips)."""
    from serial.tools import list_ports
    ports = list(list_ports.comports())
    hints = ("cp210", "ch340", "ch910", "usb-serial", "usb serial", "uart", "ftdi", "esp")
    for p in ports:
        text = f"{p.description} {p.manufacturer} {p.hwid}".lower()
        if any(h in text for h in hints):
            return p.device
    return ports[0].device if ports else None


class SerialLink:
    def __init__(self, port=None, baud=config.BAUD, serial_obj=None):
        import serial
        if serial_obj is not None:               # lets the self-test pass in a fake port
            self.ser = serial_obj
        else:
            port = port or config.SERIAL_PORT or find_port()
            if port is None:
                raise RuntimeError("No serial port found. Plug in the ESP32, or run with --no-serial.")
            # Opening the port resets most ESP32 boards; give it a moment to boot.
            self.ser = serial.Serial(port, baud, timeout=0)
            time.sleep(2.0)
            self.ser.reset_input_buffer()
        self.port = getattr(self.ser, "port", port)
        self.connected = True
        self.distance_cm = -1.0          # latest reading (-1 = none / no echo)
        self.restarted = False           # True for one poll() after the ESP32 prints READY
        self.readings_per_s = 0.0        # how many distance readings arrive each second
        self._buf = b""
        self._count, self._count_since = 0, time.monotonic()

    def write(self, data):
        """Sends ready-made message bytes."""
        self.ser.write(data)

    def poll(self, now=None):
        """Reads whatever the ESP32 sent, without blocking.
        Returns the new distance readings as [(cm, time), ...], oldest first."""
        now = time.monotonic() if now is None else now
        self.restarted = False
        readings = []
        n = self.ser.in_waiting
        if n:
            self._buf += self.ser.read(n)
        while b"\n" in self._buf:
            line, self._buf = self._buf.split(b"\n", 1)
            text = line.decode("ascii", "replace")
            d = protocol.parse_distance(text)
            if d is not None:
                self.distance_cm = d
                readings.append((d, now))
            elif protocol.is_ready(text):
                self.restarted = True
        if len(self._buf) > 256:                 # junk with no newline: drop it
            self._buf = b""
        self._count += len(readings)
        elapsed = time.monotonic() - self._count_since
        if elapsed >= 1.0:
            self.readings_per_s = self._count / elapsed
            self._count, self._count_since = 0, time.monotonic()
        return readings

    def close(self):
        try:
            self.ser.close()
        except Exception:
            pass
