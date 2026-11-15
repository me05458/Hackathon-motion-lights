"""Turns 21 hand landmarks into a gesture name. Pure maths, no camera, so it's easy to test.

Landmarks are MediaPipe's numbering: 0 wrist, 4 thumb tip, 8 index tip, 12 middle tip,
16 ring tip, 20 pinky tip. Each point needs .x and .y in 0..1 (y grows downwards).

To add a gesture: add a rule in classify(). To make it do something, add it to
GESTURE_COMMANDS in config.py.
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


class GestureFilter:
    """Only accepts a new gesture (or ASL letter) after it's been seen `stable_frames`
    times in a row. Stops one odd camera frame from counting as a sign."""

    def __init__(self, stable_frames=3, start="NONE"):
        self.stable_frames = stable_frames
        self.current = start
        self._candidate = start
        self._count = 0

    def update(self, gesture):
        if gesture == self._candidate:
            self._count += 1
        else:
            self._candidate, self._count = gesture, 1
        if self._count >= self.stable_frames:
            self.current = gesture
        return self.current
