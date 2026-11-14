"""Talks to the ESP32 over USB serial. NullLink is a stand-in for --no-serial mode."""
import time

import config
import protocol


class NullLink:
    """Does nothing. Used when the ESP32 isn't plugged in."""
    distance_cm = -1.0
    connected = False

    def send(self, gesture, x, y):
        pass

    def poll(self):
        pass

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
        self.distance_cm = -1.0
        self._buf = b""
        self._last = None
        self._last_sent_at = 0.0

    def send(self, gesture, x, y):
        """Sends only when something changed, plus a heartbeat every HEARTBEAT_S."""
        now = time.monotonic()
        msg = (gesture, x, y)
        if msg != self._last or now - self._last_sent_at >= config.HEARTBEAT_S:
            self.ser.write(protocol.encode_gesture(gesture, x, y))
            self._last, self._last_sent_at = msg, now

    def poll(self):
        """Reads whatever the ESP32 sent, without blocking. Updates distance_cm."""
        n = self.ser.in_waiting
        if n:
            self._buf += self.ser.read(n)
        while b"\n" in self._buf:
            line, self._buf = self._buf.split(b"\n", 1)
            d = protocol.parse_distance(line.decode("ascii", "replace"))
            if d is not None:
                self.distance_cm = d
        if len(self._buf) > 256:                 # junk with no newline: drop it
            self._buf = b""

    def close(self):
        try:
            self.ser.write(protocol.encode_gesture("NONE", 0, 0))
            self.ser.close()
        except Exception:
            pass
