"""Turns 21 hand landmarks into a gesture name. Pure maths, no camera, so it's easy to test.

Landmarks are MediaPipe's numbering: 0 wrist, 4 thumb tip, 8 index tip, 12 middle tip,
16 ring tip, 20 pinky tip. Each point needs .x and .y in 0..1 (y grows downwards).

To add a gesture: add its name to protocol.GESTURES, add a rule in classify(),
and draw it in frames.py + firmware/gesture_led/gesture_frames.h.
"""
import math

WRIST = 0
THUMB = (1, 2, 3, 4)            # cmc, mcp, ip, tip
FINGERS = {                      # name: (mcp, pip, tip)
    "index": (5, 6, 8),
    "middle": (9, 10, 12),
    "ring": (13, 14, 16),
    "pinky": (17, 18, 20),
}


def _dist(a, b):
    return math.hypot(a.x - b.x, a.y - b.y)


def finger_states(lm):
    """Dict finger -> True if extended. Uses distances from the wrist, so it works at any hand angle."""
    w = lm[WRIST]
    states = {name: _dist(lm[tip], w) > _dist(lm[pip], w) * 1.15
              for name, (_mcp, pip, tip) in FINGERS.items()}
    # Thumb: extended if its tip is well away from the index knuckle.
    hand_size = _dist(w, lm[9])
    states["thumb"] = _dist(lm[4], lm[5]) > hand_size * 0.55
    return states


def classify(lm) -> str:
    s = finger_states(lm)
    up = [s["index"], s["middle"], s["ring"], s["pinky"]]
    if all(up):
        return "OPEN"
    if not any(up):
        # Thumbs up: thumb out AND thumb tip clearly above the other knuckles.
        hand_size = _dist(lm[WRIST], lm[9])
        if s["thumb"] and lm[4].y < lm[5].y - hand_size * 0.3:
            return "THUMBS_UP"
        return "FIST"
    if up == [True, False, False, False]:
        return "POINT"
    if up == [True, True, False, False]:
        return "PEACE"
    return "NONE"


def pointer(lm, gesture):
    """The (x, y) in 0..1 that drives the LED position: fingertip for POINT, palm centre otherwise."""
    p = lm[8] if gesture == "POINT" else lm[9]
    return p.x, p.y


class GestureFilter:
    """Only accepts a new gesture after it's been seen `stable_frames` times in a row,
    and smooths the position. Stops the board flickering between gestures."""

    def __init__(self, stable_frames=3, smoothing=0.4):
        self.stable_frames = stable_frames
        self.smoothing = smoothing
        self.current = "NONE"
        self._candidate = "NONE"
        self._count = 0
        self.x = self.y = None

    def update(self, gesture, x=None, y=None):
        if gesture == self._candidate:
            self._count += 1
        else:
            self._candidate, self._count = gesture, 1
        if self._count >= self.stable_frames:
            self.current = gesture
        if x is not None:
            if self.x is None:
                self.x, self.y = x, y
            else:
                a = self.smoothing
                self.x += a * (x - self.x)
                self.y += a * (y - self.y)
        return self.current


def to_led(x, y, w=32, h=32):
    """0..1 coordinates -> integer LED coordinates, clamped to the panel."""
    lx = min(w - 1, max(0, int(round(x * (w - 1)))))
    ly = min(h - 1, max(0, int(round(y * (h - 1)))))
    return lx, ly
