"""On-screen copy of the 32x32 LED board, so you can work without the hardware."""
import cv2
import numpy as np

import config
from frames import render

WINDOW = "LED board (simulated)"


def board_image(gesture, x, y, dist_cm):
    rgb = render(gesture, x, y, dist_cm)
    s = config.SIM_SCALE
    big = np.repeat(np.repeat(rgb, s, axis=0), s, axis=1)
    big[::s, :] = 20            # grid lines so individual LEDs are visible
    big[:, ::s] = 20
    return cv2.cvtColor(big, cv2.COLOR_RGB2BGR)


def show(gesture, x, y, dist_cm):
    cv2.imshow(WINDOW, board_image(gesture, x, y, dist_cm))
