"""Tests an ESP32 sketch against the plain-text protocol, with no camera needed.

    python panel_test.py              auto-detect the port
    python panel_test.py --port COM5

It sends a test picture and then listens to the distance readings for a few seconds.
What you should see on the panel:
  - a white dot in each corner
  - a red line across the top half, a green one down the left half, a blue diagonal
  - one full yellow row near the bottom (sent as a single "R" row message)
  - a white dot crossing the middle row from left to right (speed test), which then
    disappears, leaving the rest of the picture untouched
Then it prints how many distance readings per second the ESP32 sends. Aim for 20 or more.
"""
import argparse
import sys
import time

import config
import protocol
from link import SerialLink

WHITE, RED, GREEN, BLUE, YELLOW, BLACK = ((255, 255, 255), (255, 0, 0), (0, 255, 0),
                                          (0, 0, 255), (255, 255, 0), (0, 0, 0))


def main():
    p = argparse.ArgumentParser(description="Send a test picture to the ESP32 and check its distance readings")
    p.add_argument("--port", help="serial port, e.g. COM5 (default: auto-detect)")
    p.add_argument("--baud", type=int, default=config.BAUD)
    p.add_argument("--listen", type=float, default=5.0, help="seconds to listen for distance readings")
    args = p.parse_args()
    try:
        link = SerialLink(port=args.port, baud=args.baud)
    except Exception as e:
        print(f"Serial error: {e}\nClose the Arduino Serial Monitor first: only one program can use the port.")
        return 1
    print(f"Connected on {link.port} at {args.baud} baud. Sending the test picture...")

    link.write(protocol.encode_clear())
    for x, y in ((0, 0), (31, 0), (0, 31), (31, 31)):
        link.write(protocol.encode_pixel(x, y, WHITE))
    for i in range(4, 16):
        link.write(protocol.encode_pixel(i, 4, RED))            # across
        link.write(protocol.encode_pixel(4, i, GREEN))          # down
    for i in range(8, 24):
        link.write(protocol.encode_pixel(i, i, BLUE))           # diagonal
    link.write(protocol.encode_row(27, [YELLOW] * 32))          # one whole row in one message

    print("Moving a dot across row 20: it should look smooth, with no trail left behind...")
    for x in range(32):
        link.write(protocol.encode_pixel(x, 20, WHITE))
        if x:
            link.write(protocol.encode_pixel(x - 1, 20, BLACK))
        time.sleep(1 / 30)                                       # one step per camera frame
    link.write(protocol.encode_pixel(31, 20, BLACK))

    print(f"Listening for distance readings for {args.listen:.0f} s. Move your hand over the sensor...")
    link.poll()                                   # throw away readings that piled up meanwhile
    readings, gaps, last = [], [], None
    start = time.monotonic()
    while time.monotonic() - start < args.listen:
        for cm, at in link.poll():
            readings.append(cm)
            if last is not None:
                gaps.append(at - last)
            last = at
        time.sleep(0.005)
    link.close()

    if not readings:
        print('\nNo distance readings arrived. The sketch should print lines like "D 23.4" '
              f"(capital D, a space, centimetres, then a newline) at {args.baud} baud.")
        return 1
    valid = [r for r in readings if r > 0]
    rate = len(readings) / args.listen
    print(f"\n{len(readings)} readings = {rate:.0f} per second "
          f"({'good' if rate >= 20 else 'slow: aim for 20 or more, see PROTOCOL.md'}).")
    if gaps:
        print(f"Longest gap between readings: {max(gaps) * 1000:.0f} ms "
              f"(the pen goes IDLE after {config.PEN_DROPOUT_S * 1000:.0f} ms without one).")
    if valid:
        print(f"Distances seen: {min(valid):.1f} to {max(valid):.1f} cm. "
              f"No echo (D -1): {len(readings) - len(valid)} of {len(readings)}.")
        print(f"Pen settings now: DOWN below {config.PEN_DOWN_CM} cm, IDLE above {config.PEN_IDLE_CM} cm.")
    else:
        print("Every reading was 'no echo' (D -1). Check the sensor wiring and that something is in range.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
