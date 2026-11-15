"""MediaPipe hand tracking. Gives back (gesture, landmarks) for each camera frame.

Swapping the vision model (e.g. an Intel Neural Compute Stick) only means
replacing this file; everything else just needs the 21 hand points.
"""
import os
import time
import urllib.request

import cv2
import mediapipe as mp
from mediapipe.tasks.python import BaseOptions, vision

import config
import gestures

# Pairs of landmark indices to draw the hand skeleton.
_BONES = [(0, 1), (1, 2), (2, 3), (3, 4), (0, 5), (5, 6), (6, 7), (7, 8), (5, 9), (9, 10),
          (10, 11), (11, 12), (9, 13), (13, 14), (14, 15), (15, 16), (13, 17), (0, 17),
          (17, 18), (18, 19), (19, 20)]


def ensure_model(path=config.MODEL_PATH):
    if not os.path.exists(path):
        print(f"Downloading hand model to {path} (about 8 MB, first run only)...")
        urllib.request.urlretrieve(config.MODEL_URL, path)
    return path


class HandTracker:
    def __init__(self):
        opts = vision.HandLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=ensure_model()),
            running_mode=vision.RunningMode.VIDEO,
            num_hands=1,
            min_hand_detection_confidence=config.MIN_DETECTION_CONFIDENCE,
            min_tracking_confidence=config.MIN_TRACKING_CONFIDENCE,
        )
        self.landmarker = vision.HandLandmarker.create_from_options(opts)
        self._t0 = time.monotonic()
        self._last_ts = -1

    def process(self, frame_bgr):
        """Returns (gesture, landmarks). No hand: ("NONE", None).
        landmarks: 21 points with .x and .y in 0..1 of the picture; number 8 is the index fingertip."""
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        ts = int((time.monotonic() - self._t0) * 1000)
        ts = max(ts, self._last_ts + 1)          # MediaPipe needs strictly increasing timestamps
        self._last_ts = ts
        result = self.landmarker.detect_for_video(image, ts)
        if not result.hand_landmarks:
            return "NONE", None
        lm = result.hand_landmarks[0]
        return gestures.classify(lm), lm

    def close(self):
        self.landmarker.close()


def draw_hand(frame, lm):
    h, w = frame.shape[:2]
    pts = [(int(p.x * w), int(p.y * h)) for p in lm]
    for a, b in _BONES:
        cv2.line(frame, pts[a], pts[b], (0, 200, 255), 2)
    for p in pts:
        cv2.circle(frame, p, 3, (255, 255, 255), -1)
