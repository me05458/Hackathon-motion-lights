"""The drawing itself: canvas, pen colour, brush and cursor.

Pure logic: no camera, no serial, no windows. main.py tells it where the pen is and
whether it's down; panel.py sends the resulting picture to the LED panel.

  canvas   a 32x32 grid of colours that remembers everything drawn so far
  cursor   where the fingertip is right now (a blinking LED), or None if hidden
  move()   pen down: leaves a line from the last position.  pen up: just moves the cursor
"""
import numpy as np

import config


def line_points(x0, y0, x1, y1):
    """Every grid point on the straight line from (x0, y0) to (x1, y1), both ends included
    (Bresenham's line algorithm). Used so a fast-moving finger leaves no gaps."""
    points = []
    dx, dy = abs(x1 - x0), -abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx + dy
    while True:
        points.append((x0, y0))
        if (x0, y0) == (x1, y1):
            return points
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x0 += sx
        if e2 <= dx:
            err += dx
            y0 += sy


class Drawing:
    def __init__(self, w=config.PANEL_W, h=config.PANEL_H, palette=None):
        self.w, self.h = w, h
        self.palette = list(palette or config.DRAW_PALETTE)     # [(name, (r, g, b)), ...]
        self.canvas = np.zeros((h, w, 3), np.uint8)
        self.color_index = 0
        self.brush = 1
        self.cursor = None               # (x, y), or None = hidden
        self.pen_down = False
        self._last_point = None          # where the line continues from; None = pen was up

    @property
    def color(self):
        return self.palette[self.color_index][1]

    @property
    def color_name(self):
        return self.palette[self.color_index][0]

    # ---- the pen -------------------------------------------------------------------
    def _stamp(self, x, y):
        """Paint the brush at one point: brush 1 = one LED, 2 = 2x2, 3 = 3x3 centred."""
        x0, y0 = x - (self.brush - 1) // 2, y - (self.brush - 1) // 2
        xa, xb = max(0, x0), min(self.w, x0 + self.brush)
        ya, yb = max(0, y0), min(self.h, y0 + self.brush)
        if xa < xb and ya < yb:
            self.canvas[ya:yb, xa:xb] = self.color

    def move(self, x, y, pen_down):
        """Call every frame the cursor should be visible."""
        self.cursor = (x, y)
        self.pen_down = pen_down
        if pen_down:
            start = self._last_point or (x, y)
            for px, py in line_points(start[0], start[1], x, y):
                self._stamp(px, py)
            self._last_point = (x, y)
        else:
            self._last_point = None      # next stroke starts fresh

    def hide_cursor(self):
        """No hand, or the pen is idle: nothing to show, and the stroke ends."""
        self.cursor = None
        self.pen_down = False
        self._last_point = None

    # ---- commands ------------------------------------------------------------------
    def clear(self):
        self.canvas[:] = 0
        self._last_point = None

    def set_color(self, name):
        for i, (n, _) in enumerate(self.palette):
            if n == name:
                self.color_index = i
                return True
        return False

    def step_color(self, step):
        self.color_index = (self.color_index + step) % len(self.palette)

    def set_brush(self, size):
        self.brush = min(config.MAX_BRUSH, max(1, int(size)))

    def apply(self, action):
        """Runs an action string from config (e.g. "color:blue"). Returns a short
        description for the screen, or None if the action is unknown."""
        name, _, arg = action.partition(":")
        if name == "color" and self.set_color(arg):
            return self.color_name
        if name in ("next_color", "prev_color"):
            self.step_color(1 if name == "next_color" else -1)
            return self.color_name
        if name == "clear":
            self.clear()
            return "cleared"
        if name == "brush" and arg.isdigit():
            self.set_brush(int(arg))
            return f"brush {self.brush}"
        if name == "next_brush":
            self.set_brush(self.brush % config.MAX_BRUSH + 1)
            return f"brush {self.brush}"
        return None

    # ---- what the panel shows ------------------------------------------------------
    def render(self, now):
        """The canvas with the cursor blinking on top."""
        img = self.canvas.copy()
        if self.cursor is not None and int(now * config.CURSOR_BLINK_HZ * 2) % 2 == 0:
            cx, cy = self.cursor
            # Blink in the pen colour; white where that wouldn't show (the eraser, or
            # an LED that already has the pen colour, such as the ink just drawn).
            visible = self.color != (0, 0, 0) and tuple(img[cy, cx]) != self.color
            img[cy, cx] = self.color if visible else (255, 255, 255)
        return img
