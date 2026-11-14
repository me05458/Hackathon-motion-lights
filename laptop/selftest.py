"""Checks everything that doesn't need a camera or an ESP32.  Run:  python selftest.py"""
import os
import sys
import threading
import time
import traceback
from types import SimpleNamespace as P

import numpy as np

import config
import frames
import gestures
import protocol
from link import SerialLink

results = []


def check(name):
    def wrap(fn):
        try:
            out = fn()
            if out == "skip":
                results.append(("SKIP", name, ""))
            else:
                results.append(("PASS", name, ""))
        except Exception as e:
            results.append(("FAIL", name, f"{type(e).__name__}: {e}"))
            traceback.print_exc()
        return fn
    return wrap


# ---------- a fake hand: 21 points, wrist at the bottom, fingers pointing up ----------
def fake_hand(index=False, middle=False, ring=False, pinky=False, thumb="in"):
    pts = [P(x=0.5, y=0.8) for _ in range(21)]
    pts[0] = P(x=0.5, y=0.8)
    for name, ext, fx in (("index", index, 0.42), ("middle", middle, 0.48),
                          ("ring", ring, 0.54), ("pinky", pinky, 0.60)):
        mcp, pip, tip = gestures.FINGERS[name]
        pts[mcp] = P(x=fx, y=0.60)
        pts[pip] = P(x=fx, y=0.50)
        pts[pip + 1] = P(x=fx, y=0.45 if ext else 0.58)
        pts[tip] = P(x=fx, y=0.40 if ext else 0.66)
    pts[1] = P(x=0.42, y=0.75)
    pts[2] = P(x=0.38, y=0.70)
    pts[3], pts[4] = {
        "in": (P(x=0.41, y=0.67), P(x=0.44, y=0.65)),      # tucked against the palm
        "side": (P(x=0.32, y=0.64), P(x=0.25, y=0.60)),    # sticking out sideways
        "up": (P(x=0.36, y=0.52), P(x=0.35, y=0.40)),      # pointing up
    }[thumb]
    return pts


def expect(lm, want):
    got = gestures.classify(lm)
    assert got == want, f"expected {want}, got {got}"


@check("open hand -> OPEN")
def _():
    expect(fake_hand(True, True, True, True, thumb="side"), "OPEN")


@check("fist -> FIST")
def _():
    expect(fake_hand(), "FIST")


@check("index finger -> POINT")
def _():
    expect(fake_hand(index=True), "POINT")


@check("two fingers -> PEACE")
def _():
    expect(fake_hand(index=True, middle=True), "PEACE")


@check("thumb up -> THUMBS_UP")
def _():
    expect(fake_hand(thumb="up"), "THUMBS_UP")


@check("gesture filter ignores one-frame flickers and smooths position")
def _():
    f = gestures.GestureFilter(stable_frames=3, smoothing=0.5)
    for _ in range(3):
        f.update("OPEN", 0.0, 0.0)
    assert f.current == "OPEN"
    f.update("FIST", 1.0, 1.0)                 # single odd frame
    assert f.current == "OPEN"
    assert abs(f.x - 0.5) < 1e-9               # moved halfway, not jumped
    for _ in range(3):
        f.update("FIST")
    assert f.current == "FIST"


@check("0..1 position maps onto the 32x32 panel and is clamped")
def _():
    assert gestures.to_led(0, 0) == (0, 0)
    assert gestures.to_led(1, 1) == (31, 31)
    assert gestures.to_led(0.5, 0.5) == (16, 16)
    assert gestures.to_led(-0.2, 1.4) == (0, 31)


@check("protocol: messages round-trip and junk is ignored")
def _():
    for g in protocol.GESTURES:
        assert protocol.parse_gesture(protocol.encode_gesture(g, 3, 29).decode()) == (g, 3, 29)
    assert protocol.parse_distance(protocol.encode_distance(42.26).decode()) == 42.3
    for junk in ("", "hello", "G WAVE 1 2", "G OPEN x 2", "D", "D far", "Object detected"):
        assert protocol.parse_gesture(junk) is None
        assert protocol.parse_distance(junk) is None


@check("board frames: every gesture draws something, and stays on the panel")
def _():
    seen = set()
    for g in protocol.GESTURES:
        for x, y in ((0, 0), (16, 16), (31, 31)):
            img = frames.render(g, x, y, 30.0)
            assert img.shape == (32, 32, 3)
            assert img.any(), f"{g} at {x},{y} drew nothing"
        seen.add(frames.render(g, 16, 16).tobytes())
    assert len(seen) == len(protocol.GESTURES), "two gestures look identical"


@check("ultrasonic distance sets circle size (closer = bigger)")
def _():
    assert frames.distance_radius(-1) == 5
    assert frames.distance_radius(5) == 10
    assert frames.distance_radius(100) == 2
    assert frames.distance_radius(500) == 2
    sizes = [frames.distance_radius(d) for d in range(5, 101)]
    assert sizes == sorted(sizes, reverse=True)
    near = np.count_nonzero(frames.render("OPEN", 16, 16, 10).any(axis=2))
    far = np.count_nonzero(frames.render("OPEN", 16, 16, 90).any(axis=2))
    assert near > far


class FakeESP32Port:
    """Pretends to be the ESP32's serial port: parses what the laptop sends,
    answers every gesture message with a distance, and prints debug noise too."""
    port = "fake"

    def __init__(self):
        self.received = []
        self._out = b"Ready!\nObject detected\n"
        self._in = b""

    def write(self, data):
        self._in += data
        while b"\n" in self._in:
            line, self._in = self._in.split(b"\n", 1)
            msg = protocol.parse_gesture(line.decode())
            if msg:
                self.received.append(msg)
                self._out += protocol.encode_distance(37.0)

    @property
    def in_waiting(self):
        return len(self._out)

    def read(self, n):
        data, self._out = self._out[:n], self._out[n:]
        return data

    def close(self):
        pass


@check("laptop link: sends only on change + heartbeat, reads distance back")
def _():
    fake = FakeESP32Port()
    link = SerialLink(serial_obj=fake)
    link.send("OPEN", 10, 10)
    link.send("OPEN", 10, 10)                   # same again: not resent
    link.send("FIST", 10, 10)
    assert fake.received == [("OPEN", 10, 10), ("FIST", 10, 10)], fake.received
    time.sleep(config.HEARTBEAT_S + 0.05)
    link.send("FIST", 10, 10)                   # heartbeat
    assert len(fake.received) == 3
    link.poll()
    assert link.distance_cm == 37.0


@check("fake ESP32 on a real virtual serial port (pyserial)")
def _():
    if os.name == "nt":
        return "skip"                           # pty virtual ports are Linux/macOS only
    import pty
    import serial
    master, slave = pty.openpty()
    import tty
    tty.setraw(slave)
    got = []

    def esp32():                                # reads gesture lines, replies with distance
        buf = b""
        deadline = time.time() + 3
        while time.time() < deadline and len(got) < 2:
            buf += os.read(master, 256)
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                msg = protocol.parse_gesture(line.decode())
                if msg:
                    got.append(msg)
                    os.write(master, b"debug text\r\n" + protocol.encode_distance(55.5))

    t = threading.Thread(target=esp32, daemon=True)
    t.start()
    ser = serial.Serial(os.ttyname(slave), config.BAUD, timeout=0)
    link = SerialLink(serial_obj=ser)
    link.send("PEACE", 4, 27)
    link.send("POINT", 5, 26)
    deadline = time.time() + 3
    while link.distance_cm != 55.5 and time.time() < deadline:
        link.poll()
        time.sleep(0.01)
    t.join(1)
    ser.close()
    os.close(master)
    assert got == [("PEACE", 4, 27), ("POINT", 5, 26)], got
    assert link.distance_cm == 55.5


@check("MediaPipe hand model loads and runs")
def _():
    try:
        import tracker
    except ImportError as e:
        raise AssertionError(f"install requirements first: {e}")
    t = tracker.HandTracker()
    try:
        g, x, y, lm = t.process(np.zeros((240, 320, 3), np.uint8))
        assert (g, lm) == ("NONE", None)        # blank image: no hand
    finally:
        t.close()


if __name__ == "__main__":
    print()
    for status, name, err in results:
        print(f"[{status}] {name}" + (f"\n        {err}" if err else ""))
    failed = sum(s == "FAIL" for s, _, _ in results)
    passed = sum(s == "PASS" for s, _, _ in results)
    print(f"\n{passed} passed, {failed} failed, {len(results) - passed - failed} skipped")
    sys.exit(1 if failed else 0)
