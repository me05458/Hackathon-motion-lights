"""The plain-text messages between the laptop and the ESP32. See PROTOCOL.md for the
full description written for whoever programs the ESP32.

Every message is one line of plain text ending in "\\n". 115200 baud unless changed.

Laptop -> ESP32 (the panel only does what it's told):
  P <x> <y> <r> <g> <b>    set one LED. x, y: 0..31 (0, 0 = top-left). r, g, b: 0..255
  C                        clear: all LEDs off
  R <y> <128 hex digits>   set a whole row: 32 LEDs, 4 hex digits each, RGB565

ESP32 -> laptop:
  D <cm>                   ultrasonic distance in centimetres, e.g. "D 23.4". "D -1" = no echo
  READY                    (optional) printed once when the ESP32 starts

Any other line is ignored by both sides, so debug prints don't break anything.
"""


def rgb565(color):
    """(r, g, b) 0..255 -> the 16-bit colour LED panels use: 5 bits red, 6 green, 5 blue."""
    r, g, b = (int(v) for v in color)
    return ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)


def encode_pixel(x, y, color) -> bytes:
    r, g, b = (int(v) for v in color)
    return f"P {int(x)} {int(y)} {r} {g} {b}\n".encode("ascii")


def encode_clear() -> bytes:
    return b"C\n"


def encode_row(y, row) -> bytes:
    """row: 32 colours (r, g, b)."""
    return (f"R {int(y)} " + "".join(f"{rgb565(c):04x}" for c in row) + "\n").encode("ascii")


def encode_distance(cm: float) -> bytes:
    """What the ESP32 sends. Used by the fake ESP32 in the tests."""
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


def is_ready(line: str) -> bool:
    return line.strip() == "READY"
