"""Small maths helpers that make noisy sensor values usable. No camera or serial here."""
import math
from collections import deque


class OneEuro:
    """Smooths a jittery value without making fast movement lag (the "One Euro" filter).

    A plain smoothing filter has to choose: steady but laggy, or quick but shaky. This
    one watches how fast the value is changing: when it's nearly still it smooths hard
    (no jitter), and when it moves fast it smooths very little (no lag).
    """

    def __init__(self, min_cutoff=1.5, beta=0.3, d_cutoff=1.0):
        self.min_cutoff, self.beta, self.d_cutoff = min_cutoff, beta, d_cutoff
        self.reset()

    def reset(self):
        self._x = self._speed = self._t = None

    @staticmethod
    def _alpha(dt, cutoff):
        tau = 1.0 / (2 * math.pi * cutoff)
        return 1.0 / (1.0 + tau / dt)

    def __call__(self, x, t):
        if self._x is None or t <= self._t:
            self._x, self._speed, self._t = x, 0.0, t
            return x
        dt = t - self._t
        speed = (x - self._x) / dt
        a = self._alpha(dt, self.d_cutoff)
        self._speed = a * speed + (1 - a) * self._speed
        cutoff = self.min_cutoff + self.beta * abs(self._speed)
        a = self._alpha(dt, cutoff)
        self._x = a * x + (1 - a) * self._x
        self._t = t
        return self._x


class Median:
    """The middle value of the last n readings. One wild reading can't move it."""

    def __init__(self, n=3):
        self._values = deque(maxlen=max(1, n))

    def add(self, value):
        self._values.append(value)

    def clear(self):
        self._values.clear()

    @property
    def value(self):
        if not self._values:
            return None
        ordered = sorted(self._values)
        return ordered[len(ordered) // 2]


def sticky_cell(current, position, n, stickiness):
    """Which of n cells (LEDs) a position 0..n falls in. Once in a cell, it stays there
    until the position goes `stickiness` cells past its edge, so a finger resting on the
    border between two LEDs doesn't make the cursor flicker between them."""
    target = min(n - 1, max(0, int(math.floor(position))))
    if current is None or abs(position - (current + 0.5)) > 0.5 + stickiness:
        return target
    return current
