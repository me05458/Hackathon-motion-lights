"""Checks everything that doesn't need a camera or an ESP32.  Run:  python selftest.py"""
import os
import sys
import threading
import time
import traceback
from types import SimpleNamespace as P

import numpy as np

import config
import gestures
import protocol
from commands import HoldTrigger
from drawing import Drawing, line_points
from filters import Median, OneEuro, sticky_cell
from link import NullLink, SerialLink
from panel import PanelSender
from pen import DOWN, HOVER, IDLE, DistancePen, combine
from pointer import ActiveBox, Pointer

results = []


def check(name):
    def wrap(fn):
        try:
            out = fn()
            results.append(("SKIP" if out == "skip" else "PASS", name, ""))
        except Exception as e:
            results.append(("FAIL", name, f"{type(e).__name__}: {e}"))
            traceback.print_exc()
        return fn
    return wrap


# =============================== hand shapes ===============================
def fake_hand(index=False, middle=False, ring=False, pinky=False, thumb="in"):
    """A fake hand: 21 points, wrist at the bottom, fingers pointing up."""
    pts = [P(x=0.5, y=0.8) for _ in range(21)]
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


def moved(lm, dx=0.0, dy=0.0, scale=1.0, noise=0.0, rng=None):
    """The same hand shifted, resized and jittered, like a real hand moving in front of the camera."""
    out = []
    for p in lm:
        jx, jy = (rng.normal(0, noise, 2) if rng is not None else (0, 0))
        out.append(P(x=0.5 + (p.x - 0.5) * scale + dx + jx, y=0.5 + (p.y - 0.5) * scale + dy + jy))
    return out


@check("gestures: open hand, fist, point, peace and thumbs up are told apart")
def _():
    for hand, want in ((fake_hand(True, True, True, True, thumb="side"), "OPEN"),
                       (fake_hand(), "FIST"), (fake_hand(index=True), "POINT"),
                       (fake_hand(index=True, middle=True), "PEACE"),
                       (fake_hand(thumb="up"), "THUMBS_UP")):
        got = gestures.classify(hand)
        assert got == want, f"expected {want}, got {got}"


@check("gestures: one odd camera frame doesn't count as a new gesture")
def _():
    f = gestures.GestureFilter(stable_frames=3)
    for _ in range(3):
        f.update("OPEN")
    assert f.update("FIST") == "OPEN"            # single odd frame
    f.update("FIST")
    assert f.update("FIST") == "FIST"


# =============================== the pen (ultrasonic) ===============================
def feed(pen, readings, t0=0.0, dt=0.03):
    """Feeds readings 30 ms apart; returns the state after each one."""
    states = []
    for i, cm in enumerate(readings):
        t = t0 + i * dt
        pen.add(cm, t)
        states.append(pen.update(t))
    return states


@check("pen: near = DOWN, middle = HOVER, far = IDLE")
def _():
    pen = DistancePen(down_cm=15, idle_cm=40, margin_cm=2, median_n=1)
    assert feed(pen, [60]) == [IDLE]
    assert feed(pen, [30], t0=1) == [HOVER]
    assert feed(pen, [10], t0=2) == [DOWN]
    assert feed(pen, [30], t0=3) == [HOVER]
    assert feed(pen, [60], t0=4) == [IDLE]
    assert feed(pen, [10], t0=5) == [DOWN], "should go straight from idle to down"


@check("pen: a hand sitting right on a limit doesn't flicker between states")
def _():
    pen = DistancePen(down_cm=15, idle_cm=40, margin_cm=2, median_n=1)
    feed(pen, [10])
    wobble = [14.5, 15.5, 14.8, 16.2, 15.1, 16.9]              # jitter around the 15 cm limit
    assert set(feed(pen, wobble, t0=1)) == {DOWN}
    assert feed(pen, [17.5], t0=2) == [HOVER]                  # clearly past it: pen lifts
    assert set(feed(pen, [16.0, 15.2, 16.5], t0=3)) == {HOVER}, "should need < 15 to go down again"
    feed(pen, [30], t0=4)
    assert set(feed(pen, [39.5, 40.5, 41.5, 39.8], t0=5)) == {HOVER}
    assert feed(pen, [43], t0=6) == [IDLE]
    assert set(feed(pen, [41, 40.5], t0=7)) == {IDLE}


@check("pen: one wild sensor reading is ignored")
def _():
    pen = DistancePen(down_cm=15, idle_cm=40, median_n=3)
    states = feed(pen, [30, 30, 30, 4, 30, 30, 250, 30])       # a spike near and a spike far
    assert set(states) == {HOVER}, states
    m = Median(3)
    for v in (10, 11, 99):
        m.add(v)
    assert m.value == 11


@check("pen: missed echoes are tolerated briefly, then the pen lifts; no sensor = idle")
def _():
    pen = DistancePen(down_cm=15, idle_cm=40, median_n=3, dropout_s=0.25)
    assert pen.update(0.0) == IDLE and pen.distance is None    # nothing ever received
    feed(pen, [10, 10, 10], t0=1.0)
    pen.add(-1, 1.10)                                          # "no echo" readings...
    pen.add(-1, 1.13)
    assert pen.update(1.15) == DOWN                            # ...for 90 ms: keep drawing
    assert pen.update(1.40) == IDLE, "pen stayed down with no reading for 340 ms"
    assert pen.distance is None
    feed(pen, [30], t0=2.0)                                    # old readings must be forgotten
    assert pen.state == HOVER


@check("fusion: ink needs the sensor AND the camera to agree")
def _():
    assert combine(DOWN, hand_visible=True, inside_box=True) == (True, True)
    assert combine(DOWN, hand_visible=False, inside_box=False) == (False, False), \
        "something near the sensor drew with no hand in view"
    assert combine(DOWN, hand_visible=True, inside_box=False) == (True, False)
    assert combine(HOVER, hand_visible=True, inside_box=True) == (True, False)
    assert combine(IDLE, hand_visible=True, inside_box=True) == (False, False)


# =============================== camera -> LED ===============================
@check("pointer: the drawing box maps onto the 32x32 panel, square, any camera shape")
def _():
    for fw, fh in ((640, 480), (1280, 720)):
        box = ActiveBox(center=(0.5, 0.5), size=0.7)
        left, top, side = box.rect(fw, fh)
        assert abs(side - 0.7 * fh) < 1e-6
        px = lambda x, y: Pointer(box).update(x / fw, y / fh, fw, fh, 0.0)     # noqa: E731
        assert px(left + 1, top + 1) == (0, 0, True)
        assert px(left + side - 1, top + side - 1) == (31, 31, True)
        assert px(fw / 2, fh / 2)[:2] == (16, 16)
        one_led = side / 32                                    # same distance in x and y...
        assert px(left + 10.5 * one_led, top + 3.5 * one_led)[:2] == (10, 3)   # ...same LED steps
        assert px(left - 50, fh / 2) == (0, 16, False)         # outside: clamped, flagged
        assert px(fw / 2, top + side + 50) == (16, 31, False)


@check("pointer: a shaky finger keeps the cursor still; a fast stroke isn't left behind")
def _():
    rng = np.random.default_rng(1)
    fw, fh = 640, 480
    p = Pointer(ActiveBox(size=0.7))
    left, top, side = p.box.rect(fw, fh)
    at = lambda lx, ly: ((left + lx * side / 32) / fw, (top + ly * side / 32) / fh)   # noqa: E731
    seen, t = set(), 0.0
    for _ in range(90):                                        # 3 s holding still, 0.25 LED of shake
        t += 1 / 30
        x, y = at(10.5 + rng.normal(0, 0.25), 20.5 + rng.normal(0, 0.25))
        seen.add(p.update(x, y, fw, fh, t)[:2])
    assert seen == {(10, 20)}, f"cursor wandered while holding still: {seen}"
    for i in range(1, 11):                                     # sweep 20 LEDs in 1/3 s
        t += 1 / 30
        got = p.update(*at(10.5 + 2 * i, 20.5), fw, fh, t)
    assert got[0] >= 28, f"cursor lags a fast stroke: at {got[0]}, finger at 30"
    for _ in range(6):
        t += 1 / 30
        got = p.update(*at(30.5, 20.5), fw, fh, t)
    assert got[:2] == (30, 20)
    f = OneEuro()
    assert f(5.0, 0.0) == 5.0 and f(5.0, 0.1) == 5.0
    assert sticky_cell(4, 5.1, 32, 0.15) == 4 and sticky_cell(4, 5.2, 32, 0.15) == 5


# =============================== drawing ===============================
def lit(art):
    """Set of (x, y) LEDs that are not black."""
    ys, xs = np.nonzero(art.canvas.any(axis=2))
    return set(zip(xs.tolist(), ys.tolist()))


@check("drawing: a fast finger still leaves a line with no gaps")
def _():
    art = Drawing()
    art.move(2, 2, pen_down=True)
    art.move(20, 9, pen_down=True)                 # jumped 18 LEDs in one frame
    pts = line_points(2, 2, 20, 9)
    assert lit(art) == set(pts)
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):   # every LED touches the next one
        assert max(abs(x1 - x0), abs(y1 - y0)) == 1


@check("drawing: lifting the pen ends the stroke; hover leaves no ink")
def _():
    art = Drawing()
    art.move(1, 1, pen_down=True)
    art.move(15, 15, pen_down=False)               # hover
    assert art.cursor == (15, 15) and not art.pen_down
    art.move(30, 30, pen_down=True)
    assert lit(art) == {(1, 1), (30, 30)}, "hover movement was joined into a line"
    art.hide_cursor()                              # idle: cursor gone, stroke ended
    assert art.cursor is None
    art.move(30, 20, pen_down=True)
    assert lit(art) == {(1, 1), (30, 30), (30, 20)}


@check("drawing: colours, eraser, brush sizes and clear")
def _():
    art = Drawing()
    assert art.apply("color:blue") == "blue" and art.color == (0, 0, 255)
    art.move(5, 5, pen_down=True)
    assert tuple(art.canvas[5, 5]) == (0, 0, 255)
    assert art.apply("color:nosuchcolour") is None and art.color_name == "blue"
    art.apply("color:eraser")
    art.move(5, 5, pen_down=True)
    assert not lit(art), "eraser didn't erase"
    n = len(art.palette)
    for _ in range(n):
        art.apply("next_color")
    assert art.color_name == "eraser"              # all the way round
    art.apply("prev_color")
    assert art.color_name == "white"
    art.apply("brush:2")
    art.hide_cursor()
    art.move(10, 10, pen_down=True)
    assert lit(art) == {(10, 10), (11, 10), (10, 11), (11, 11)}
    art.apply("brush:3")
    art.hide_cursor()
    art.move(0, 31, pen_down=True)                 # a corner: must stay on the panel
    assert all(0 <= x < 32 and 0 <= y < 32 for x, y in lit(art)) and (1, 30) in lit(art)
    assert art.apply("next_brush") == "brush 1"    # wraps after MAX_BRUSH
    assert art.apply("clear") == "cleared" and not lit(art)
    assert art.apply("fly") is None


@check("drawing: the hover cursor blinks on top of the picture without marking it")
def _():
    art = Drawing()
    art.move(8, 8, pen_down=False)
    on, off = art.render(0.0), art.render(0.25)    # 2 blinks a second
    assert tuple(on[8, 8]) == art.color and not off.any()
    assert not art.canvas.any(), "the cursor leaked into the drawing"
    art.move(8, 8, pen_down=True)                  # sitting on its own colour: shows white
    assert tuple(art.render(0.0)[8, 8]) == (255, 255, 255)
    art.apply("color:eraser")
    art.move(20, 20, pen_down=False)
    assert tuple(art.render(0.0)[20, 20]) == (255, 255, 255)
    art.hide_cursor()
    assert np.array_equal(art.render(0.0), art.canvas)


# =============================== commands ===============================
@check("commands: a sign must be held, fires once, and clear needs a longer hold")
def _():
    t = HoldTrigger({"R": "color:red", "C": "clear", "N": "next_color"},
                    hold_s=0.5, clear_hold_s=1.0, repeat_s=1.0)
    assert t.update("R", 0.0) is None and t.update("R", 0.3) is None
    assert 0.5 < t.progress < 0.7
    assert t.update(None, 0.35) is None and t.progress == 0    # let go early: nothing
    assert t.update("R", 1.0) is None
    assert t.update("R", 1.5) == "color:red"
    assert t.update("R", 1.6) is None and t.update("R", 9.0) is None, "fired twice in one hold"
    assert t.update("C", 10.0) is None and t.update("C", 10.6) is None
    assert t.update("C", 11.0) == "clear"
    assert t.update("X", 12.0) is None and t.sign is None      # a sign with no action
    assert t.update("N", 20.0) is None
    assert t.update("N", 20.5) == "next_color"                 # stepping actions repeat...
    assert t.update("N", 21.0) is None
    assert t.update("N", 21.5) == "next_color"                 # ...once a second while held
    assert t.update("R", 21.6) is None and t.update("R", 22.1) == "color:red"


@check("commands: every action in config.py is one the drawing understands")
def _():
    names = [n for n, _ in config.DRAW_PALETTE]
    assert len(set(names)) == len(names)
    for sign, action in {**config.ASL_COMMANDS, **config.GESTURE_COMMANDS}.items():
        assert Drawing().apply(action) is not None, f"{sign}: unknown action {action!r}"
    assert config.PEN_DOWN_CM + config.PEN_MARGIN_CM < config.PEN_IDLE_CM


# =============================== laptop -> panel ===============================
class FakePanel:
    """Does exactly what PROTOCOL.md asks of the ESP32: a pretend LED panel."""

    def __init__(self):
        self.leds = np.zeros((32, 32), np.uint16)      # RGB565, like the real panel
        self.lines = []
        self.lose = lambda line: False                 # set to drop messages on the way

    def write(self, data):
        for line in data.decode("ascii").splitlines():
            self.lines.append(line)
            if self.lose(line):
                continue
            parts = line.split()
            if parts == ["C"]:
                self.leds[:] = 0
            elif parts[0] == "P" and len(parts) == 6:
                x, y, r, g, b = (int(v) for v in parts[1:])
                assert 0 <= x < 32 and 0 <= y < 32 and all(0 <= v <= 255 for v in (r, g, b)), line
                self.leds[y, x] = protocol.rgb565((r, g, b))
            elif parts[0] == "R" and len(parts) == 3 and len(parts[2]) == 128:
                self.leds[int(parts[1])] = [int(parts[2][i:i + 4], 16) for i in range(0, 128, 4)]
            else:
                raise AssertionError(f"laptop sent a line the protocol doesn't define: {line!r}")


def as565(image):
    return np.array([[protocol.rgb565(c) for c in row] for row in image], np.uint16)


def scribble(art, sender, frames, t=0.0, seed=5, each_frame=None):
    """A random drawing session: hover, draw, change colour, clear. Returns the end time."""
    rng = np.random.default_rng(seed)
    x = y = 16
    for i in range(frames):
        t += 1 / 30
        x = int(np.clip(x + rng.integers(-3, 4), 0, 31))
        y = int(np.clip(y + rng.integers(-3, 4), 0, 31))
        roll = rng.random()
        if roll < 0.02:
            art.apply("next_color")
        elif roll < 0.03:
            art.clear()
        if roll > 0.9:
            art.hide_cursor()
        else:
            art.move(x, y, pen_down=(i // 20) % 2 == 0)
        image = art.render(t)
        sender.show(image, t)
        if each_frame:
            each_frame(image)
    return t


@check("panel: after every frame the panel shows exactly the laptop's picture")
def _():
    panel, art = FakePanel(), Drawing()
    panel.leds[:] = 0x1234                         # leftovers from before the laptop started
    sender = PanelSender(panel)

    def same(image):
        assert np.array_equal(panel.leds, as565(image)), "panel and laptop differ"
    scribble(art, sender, frames=600, each_frame=same)
    assert art.canvas.any()


@check("panel: low latency - a cursor move is two short messages, a clear is one")
def _():
    panel, art = FakePanel(), Drawing()
    sender = PanelSender(panel, resync_row_s=0)
    art.move(5, 5, pen_down=False)
    sender.show(art.render(0.0), 0.0)
    before, n = sender.bytes_sent, len(panel.lines)
    art.move(6, 5, pen_down=False)                 # hover cursor moves one LED
    sender.show(art.render(0.0), 0.0)
    assert len(panel.lines) - n == 2 and sender.bytes_sent - before <= 40
    art.move(7, 5, pen_down=True)                  # ink
    sender.show(art.render(0.0), 0.0)
    assert sender.bytes_sent - before <= 100
    for x in range(32):
        art.move(x, 9, pen_down=True)              # a full-width stroke in one frame...
    n = len(panel.lines)
    sender.show(art.render(0.0), 0.0)
    assert [l[0] for l in panel.lines[n:]].count("R") == 1, "a full row should be one R message"
    art.hide_cursor()
    art.clear()
    n = len(panel.lines)
    sender.show(art.render(0.0), 0.0)
    assert panel.lines[n:] == ["C"]
    n = len(panel.lines)
    sender.show(art.render(0.0), 0.1)              # nothing changed, repair off: silence
    assert len(panel.lines) == n


@check("panel: repairs itself after lost messages and after an ESP32 restart")
def _():
    panel, art = FakePanel(), Drawing()
    sender = PanelSender(panel, resync_row_s=0.1)
    count = [0]

    def lose_every_third(line):
        count[0] += 1
        return line[0] == "P" and count[0] % 3 == 0
    panel.lose = lose_every_third
    t = scribble(art, sender, frames=300)
    panel.lose = lambda line: False
    art.hide_cursor()
    for i in range(120):                           # 4 s of nothing happening
        t += 1 / 30
        n = len(panel.lines)
        sender.show(art.render(t), t)
        assert len(panel.lines) - n <= 1, "repair must be gentle: at most one row per frame"
    assert art.canvas.any() and np.array_equal(panel.leds, as565(art.canvas)), "lost LEDs never repaired"

    panel.leds[:] = 0                              # ESP32 unplugged and plugged back in
    sender.invalidate()                            # (the laptop sees its READY line)
    sender.show(art.render(t), t)
    assert np.array_equal(panel.leds, as565(art.canvas)), "picture not restored after a restart"


@check("panel: repair never gets in the way of drawing")
def _():
    panel, art = FakePanel(), Drawing()
    sender = PanelSender(panel, resync_row_s=0.01)     # repair as eager as possible
    art.move(0, 0, pen_down=True)
    sender.show(art.render(0.0), 0.0)
    for i in range(1, 30):                         # 29 frames of steady drawing
        n = len(panel.lines)
        art.move(i, i, pen_down=True)
        sender.show(art.render(i / 30), i / 30)
        sent = panel.lines[n:]
        assert sent and all(l[0] == "P" for l in sent), f"repair row sent while drawing: {sent}"


# =============================== ESP32 -> laptop ===============================
class FakePort:
    """A pretend serial port: `incoming` is what the ESP32 sent, `sent` what the laptop wrote."""
    port = "fake"

    def __init__(self, incoming=b""):
        self.incoming, self.sent = incoming, b""

    def write(self, data):
        self.sent += data

    @property
    def in_waiting(self):
        return len(self.incoming)

    def read(self, n):
        data, self.incoming = self.incoming[:n], self.incoming[n:]
        return data

    def close(self):
        pass


@check("link: reads distance lines, ignores debug text, notices an ESP32 restart")
def _():
    port = FakePort(b"boot junk\r\nREADY\r\nD 23.4\r\nhello D 9\nD -1\nD abc\nD 12")   # last line unfinished
    link = SerialLink(serial_obj=port)
    got = link.poll(now=5.0)
    assert got == [(23.4, 5.0), (-1.0, 5.0)], got
    assert link.restarted and link.distance_cm == -1.0
    port.incoming += b".5\n"                        # the rest of the line arrives later
    assert link.poll(now=5.1) == [(12.5, 5.1)] and not link.restarted
    link.write(protocol.encode_pixel(3, 4, (255, 128, 0)))
    assert port.sent == b"P 3 4 255 128 0\n"
    assert protocol.encode_clear() == b"C\n"
    row = protocol.encode_row(31, [(255, 0, 0)] * 32).decode()
    assert row == "R 31 " + "f800" * 32 + "\n" and len(row) < 160
    assert protocol.rgb565((255, 255, 255)) == 0xFFFF

    null = NullLink()                               # --no-serial: keys fake the sensor
    assert null.poll(1.0) == []
    null.sim_cm = 12.0
    assert null.poll(2.0) == [(12.0, 2.0)]


@check("link: two-way traffic over a real virtual serial port (pyserial)")
def _():
    if os.name == "nt":
        return "skip"                               # pty virtual ports are Linux/macOS only
    import pty
    import tty
    import serial
    master, slave = pty.openpty()
    tty.setraw(slave)
    got = []

    def esp32():                                    # collects what it's sent, then "restarts"
        buf, deadline = b"", time.time() + 3
        while time.time() < deadline and len(got) < 2:
            buf += os.read(master, 256)
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                got.append(line.decode())
        os.write(master, b"READY\r\n" + protocol.encode_distance(18.5))

    th = threading.Thread(target=esp32, daemon=True)
    th.start()
    ser = serial.Serial(os.ttyname(slave), config.BAUD, timeout=0)
    link = SerialLink(serial_obj=ser)
    link.write(protocol.encode_pixel(1, 2, (3, 4, 5)))
    link.write(protocol.encode_clear())
    readings, restarted, deadline = [], False, time.time() + 3
    while not (readings and restarted) and time.time() < deadline:
        readings += link.poll()
        restarted = restarted or link.restarted
        time.sleep(0.01)
    th.join(1)
    ser.close()
    os.close(master)
    assert got[:2] == ["P 1 2 3 4 5", "C"], got
    assert readings and readings[0][0] == 18.5 and restarted


# =============================== ASL commands ===============================
@check("ASL features ignore where the hand is and how big it looks")
def _():
    import asl
    hand = fake_hand(index=True, middle=True)
    a = asl.features(asl.raw_row(hand))
    b = asl.features(asl.raw_row(moved(hand, dx=0.2, dy=-0.1, scale=0.5)))
    assert a.shape == (42,)
    assert np.allclose(a, b), "features changed when the hand moved"
    c = asl.features(asl.raw_row(fake_hand()))
    assert not np.allclose(a, c), "different hand shapes gave the same features"


@check("ASL: record -> train -> recognise, and an untrained hand shape is rejected")
def _():
    import tempfile
    import asl
    import train_asl
    shapes = {"R": fake_hand(), "B": fake_hand(True, True, True, True),
              "L": fake_hand(index=True, thumb="side"), "Y": fake_hand(pinky=True, thumb="side"),
              "REST": fake_hand(index=True)}
    rng = np.random.default_rng(0)
    with tempfile.TemporaryDirectory() as tmp:
        data, model = os.path.join(tmp, "d.csv"), os.path.join(tmp, "m.joblib")
        rows = []
        for letter, hand in shapes.items():
            for _ in range(40):
                h = moved(hand, rng.uniform(-0.2, 0.2), rng.uniform(-0.2, 0.2),
                          rng.uniform(0.5, 1.3), noise=0.004, rng=rng)
                rows.append((letter, asl.raw_row(h)))
        asl.append_samples(rows, data)
        acc = train_asl.train(data, model, quiet=True)
        assert acc >= 0.95, f"test accuracy only {acc:.0%}"
        clf = asl.ASLClassifier(model, min_confidence=0.6)
        assert set(clf.letters) == set(shapes)
        for letter, hand in shapes.items():
            got, conf = clf.predict(moved(hand, dx=0.1, scale=0.8))
            assert got == letter, f"{letter} recognised as {got} ({conf:.0%})"
        # Shapes it never saw must come back as "?", not as the nearest trained letter.
        for stranger in (fake_hand(index=True, middle=True), fake_hand(True, True, True),
                         fake_hand(thumb="up")):
            got, _ = clf.predict(stranger)
            assert got == "?", f"an untrained hand shape was taken for {got}"
        # Not enough data must give a clear message, not a crash.
        asl.append_samples([("R", asl.raw_row(shapes["R"]))], os.path.join(tmp, "small.csv"))
        try:
            train_asl.train(os.path.join(tmp, "small.csv"), model, quiet=True)
            raise AssertionError("training on 1 sample should refuse")
        except ValueError:
            pass


@check("MediaPipe hand model loads and runs")
def _():
    try:
        import tracker
    except ImportError as e:
        raise AssertionError(f"install requirements first: {e}")
    t = tracker.HandTracker()
    try:
        assert t.process(np.zeros((240, 320, 3), np.uint8)) == ("NONE", None)   # blank image: no hand
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
