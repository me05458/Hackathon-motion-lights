"""Turns the fingertip's place in the camera picture into an LED on the 32x32 panel.

The camera picture is wide (640x480) and the panel is square (32x32), and nobody wants
to reach the corners of the camera view. So a square box inside the picture is "the
panel": the box's top-left corner is LED (0, 0) and its bottom-right is LED (31, 31).
"""
import config
from filters import OneEuro, sticky_cell


class ActiveBox:
    def __init__(self, center=config.DRAW_BOX_CENTER, size=config.DRAW_BOX_SIZE):
        self.cx, self.cy = center
        self.size = size                 # side length as a fraction of the picture's height

    def rect(self, frame_w, frame_h):
        """The box in picture pixels: (left, top, side)."""
        side = self.size * frame_h
        return self.cx * frame_w - side / 2, self.cy * frame_h - side / 2, side

    def to_unit(self, x, y, frame_w, frame_h):
        """Picture position (0..1, 0..1) -> position in the box: (0, 0) is its top-left
        corner and (1, 1) its bottom-right. Values outside 0..1 are outside the box."""
        left, top, side = self.rect(frame_w, frame_h)
        return (x * frame_w - left) / side, (y * frame_h - top) / side

    def resize(self, factor):
        self.size = min(1.0, max(0.2, self.size * factor))


class Pointer:
    """Fingertip -> steady LED position. Call update() each frame the hand is visible,
    and reset() when it disappears."""

    def __init__(self, box=None, w=config.PANEL_W, h=config.PANEL_H,
                 min_cutoff=config.POINTER_MIN_CUTOFF, beta=config.POINTER_BETA,
                 stickiness=config.POINTER_STICKINESS, edge_tolerance=0.03):
        self.box = box or ActiveBox()
        self.w, self.h = w, h
        self.stickiness = stickiness
        self.edge_tolerance = edge_tolerance
        self._fx = OneEuro(min_cutoff, beta)
        self._fy = OneEuro(min_cutoff, beta)
        self.led = None                  # current (x, y) LED, or None if no hand

    def reset(self):
        self._fx.reset()
        self._fy.reset()
        self.led = None

    def update(self, x, y, frame_w, frame_h, now):
        """x, y: fingertip in the picture, 0..1. Returns (led_x, led_y, inside_box)."""
        u, v = self.box.to_unit(x, y, frame_w, frame_h)
        tol = self.edge_tolerance
        inside = -tol <= u <= 1 + tol and -tol <= v <= 1 + tol
        fx = self._fx(u * self.w, now)   # smooth in LED units
        fy = self._fy(v * self.h, now)
        old = self.led or (None, None)
        self.led = (sticky_cell(old[0], fx, self.w, self.stickiness),
                    sticky_cell(old[1], fy, self.h, self.stickiness))
        return self.led[0], self.led[1], inside
