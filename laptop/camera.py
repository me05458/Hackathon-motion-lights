"""Opens the webcam.

Uses OpenCV's default camera driver first, exactly like the original main.py did, and
gives the camera a few seconds to send its first picture (Windows cameras can be slow
to start). Only if that fails does it try DirectShow on Windows as a fallback.
"""
import sys
import time

import cv2

import config


def open_camera(index=config.CAMERA_INDEX):
    """Returns an opened cv2.VideoCapture that has delivered at least one frame, or None."""
    attempts = [("default", None)]
    if sys.platform == "win32":
        attempts.append(("DirectShow", cv2.CAP_DSHOW))
    for name, backend in attempts:
        cap = cv2.VideoCapture(index) if backend is None else cv2.VideoCapture(index, backend)
        if cap.isOpened():
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.CAMERA_WIDTH)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.CAMERA_HEIGHT)
            if config.CAMERA_FPS:
                cap.set(cv2.CAP_PROP_FPS, config.CAMERA_FPS)
            ok, _ = read_frame(cap, retries=150)  # up to ~5 s for the first picture
            if ok:
                print(f"Camera {index} opened ({name} driver)")
                return cap
            print(f"Camera {index} opened with the {name} driver but sent no picture.")
        else:
            print(f"Camera {index} could not be opened with the {name} driver.")
        cap.release()
    return None


def read_frame(cap, retries=30):
    """Like cap.read(), but tolerates a few dropped frames before giving up."""
    for _ in range(retries):
        ok, frame = cap.read()
        if ok and frame is not None:
            return True, frame
        time.sleep(0.03)
    return False, None


CAMERA_HELP = """Could not get a picture from camera {index}. Check:
  - the camera privacy switch / key (often F10 or a key with a crossed-out camera) is ON
  - no other app is using the camera: Teams, Zoom, the Camera app, a browser tab,
    or another copy of main.py / record_asl.py still running in another window
  - Settings > Privacy & security > Camera: 'Let desktop apps access your camera' is on
  - or try another camera number, e.g. --camera {other}"""


def camera_help(index):
    return CAMERA_HELP.format(index=index, other=0 if index else 1)
