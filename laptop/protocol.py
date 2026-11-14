"""The text protocol between laptop and ESP32. Must match firmware/gesture_led/laptop_link.h.

Laptop -> ESP32, one line:   G <GESTURE> <x> <y>\\n     e.g.  "G OPEN 12 20"
ESP32 -> laptop, one line:   D <centimetres>\\n          e.g.  "D 42.5"

x and y are LED coordinates, 0..31. Any other line is ignored by both sides,
so debug prints from the ESP32 don't break anything.
"""

GESTURES = ("NONE", "OPEN", "FIST", "POINT", "PEACE", "THUMBS_UP")


def encode_gesture(gesture: str, x: int, y: int) -> bytes:
    if gesture not in GESTURES:
        raise ValueError(f"unknown gesture {gesture!r}")
    return f"G {gesture} {int(x)} {int(y)}\n".encode("ascii")


def parse_gesture(line: str):
    """Returns (gesture, x, y) or None. Used by the self-test and fake ESP32."""
    parts = line.strip().split()
    if len(parts) != 4 or parts[0] != "G" or parts[1] not in GESTURES:
        return None
    try:
        return parts[1], int(parts[2]), int(parts[3])
    except ValueError:
        return None


def encode_distance(cm: float) -> bytes:
    return f"D {cm:.1f}\n".encode("ascii")


def parse_distance(line: str):
    """Returns distance in cm (float) or None if the line isn't a distance message."""
    parts = line.strip().split()
    if len(parts) != 2 or parts[0] != "D":
        return None
    try:
        return float(parts[1])
    except ValueError:
        return None
