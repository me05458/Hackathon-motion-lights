"""Draws one 32x32 frame for a gesture.

This is a line-by-line copy of firmware/gesture_led/gesture_frames.h, so the on-screen
board shows exactly what the real panel shows. If you change one, change the other,
then run  python ../tools/check_firmware.py  to confirm they still match.
"""
import numpy as np

W = H = 32


def distance_radius(dist_cm):
    """Closer hand (smaller distance) -> bigger circle. Unknown distance (<= 0) -> 5."""
    if dist_cm <= 0:
        return 5
    d = min(100, max(5, int(dist_cm)))
    return 10 - (d - 5) * 8 // 95          # 5 cm -> 10, 100 cm -> 2


def render(gesture, x, y, dist_cm=-1.0):
    """Returns an (H, W, 3) uint8 RGB array."""
    img = np.zeros((H, W, 3), np.uint8)

    def px(px_, py_, c):
        if 0 <= px_ < W and 0 <= py_ < H:
            img[py_, px_] = c

    def fill_rect(x0, y0, w, h, c):
        for yy in range(y0, y0 + h):
            for xx in range(x0, x0 + w):
                px(xx, yy, c)

    if gesture == "OPEN":                       # green disc, size from ultrasonic distance
        r = distance_radius(dist_cm)
        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                if dx * dx + dy * dy <= r * r + r:     # "+ r" rounds off single-pixel spikes
                    px(x + dx, y + dy, (0, 255, 0))
    elif gesture == "FIST":                     # red 7x7 block
        fill_rect(x - 3, y - 3, 7, 7, (255, 0, 0))
    elif gesture == "POINT":                    # white 3x3 dot
        fill_rect(x - 1, y - 1, 3, 3, (255, 255, 255))
    elif gesture == "PEACE":                    # two yellow bars
        fill_rect(x - 3, y - 5, 1, 11, (255, 255, 0))
        fill_rect(x + 3, y - 5, 1, 11, (255, 255, 0))
    elif gesture == "THUMBS_UP":                # magenta plus sign
        fill_rect(x - 6, y, 13, 1, (255, 0, 255))
        fill_rect(x, y - 6, 1, 13, (255, 0, 255))
    else:                                       # NONE: dim blue border = "waiting for a hand"
        fill_rect(0, 0, W, 1, (0, 0, 64))
        fill_rect(0, H - 1, W, 1, (0, 0, 64))
        fill_rect(0, 0, 1, H, (0, 0, 64))
        fill_rect(W - 1, 0, 1, H, (0, 0, 64))
    return img
