"""Checks the example ESP32 code against the laptop code, on this PC (needs g++).

It compiles firmware/example_receiver/panel_protocol.h with a stand-in for the Arduino
core, feeds it the exact bytes the laptop sends during a drawing session, and checks:
  1. the LEDs end up exactly as the laptop's picture;
  2. junk, damaged and out-of-range messages change nothing and crash nothing;
  3. with a third of the pixel messages thrown away, the picture still repairs itself.
It does not compile the .ino sketch itself; the Arduino IDE does that when you upload.
Run from anywhere:  python tools/check_firmware.py
"""
import os
import shutil
import subprocess
import sys
import tempfile

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FW = os.path.join(ROOT, "firmware", "example_receiver")
sys.path.insert(0, os.path.join(ROOT, "laptop"))
import protocol                    # noqa: E402
from drawing import Drawing        # noqa: E402
from panel import PanelSender      # noqa: E402

# Minimal stand-ins for the Arduino core, just enough for the header.
ARDUINO_SHIM = r"""
#pragma once
#include <stdint.h>
#include <stddef.h>
#include <string>
struct Stream {
  std::string in; size_t pos = 0;
  int available() { return (int)(in.size() - pos); }
  int read() { return (unsigned char)in[pos++]; }
};
static Stream Serial;
"""

# Reads a file of laptop messages a few bytes at a time (as they trickle in over USB),
# then prints every LED.
TEST_CPP = r"""
#include "panel_protocol.h"
#include <fstream>
#include <sstream>
#include <stdio.h>

struct Panel {
  uint16_t px[32][32];
  int outOfRange = 0;
  Panel() { for (auto &row : px) for (auto &p : row) p = 0x1234; }   // leftovers from before
  void drawPixel(int x, int y, uint16_t c) {
    if (x < 0 || x > 31 || y < 0 || y > 31) { outOfRange++; return; }
    px[y][x] = c;
  }
  void fillScreen(uint16_t c) { for (auto &row : px) for (auto &p : row) p = c; }
};

int main(int argc, char **argv) {
  std::ifstream f(argv[1], std::ios::binary);
  std::stringstream ss; ss << f.rdbuf();
  std::string all = ss.str();
  Stream s;
  PanelProtocol laptop;
  Panel panel;
  int shows = 0;
  for (size_t i = 0; i < all.size(); i += 7) {       // 7 bytes per loop(): lines arrive in pieces
    s.in += all.substr(i, 7);
    if (laptop.poll(panel, s)) shows++;
  }
  printf("%d %d ", panel.outOfRange, shows);
  for (int y = 0; y < 32; y++) for (int x = 0; x < 32; x++) printf("%04x", panel.px[y][x]);
  printf("\n");
}
"""

JUNK = [b"Ready!\r\n", b"G OPEN 1 2\n", b"P\n", b"P 1 2 3\n", b"P 1 2 3 4 5 6\n", b"P 40 3 9 9 9\n",
        b"P -1 3 9 9 9\n", b"P 3 3 256 0 0\n", b"P 3 x 1 1 1\n", b"Px 1 2 3 4 5\n", b"C 1\n", b"CC\n",
        b"R 3 zz\n", b"R 32 " + b"f" * 128 + b"\n", b"R 3 " + b"f" * 127 + b"\n",
        b"R 3 " + b"g" * 128 + b"\n", b"x" * 500 + b"\n", b"\n", b"D 12.5\n"]


class Capture:
    def __init__(self):
        self.lines = []

    def write(self, data):
        self.lines.append(data)


def session(seed=7, frames=600, quiet_frames=150):
    """A random drawing session, then a few seconds of holding still.
    Returns (final picture, every message sent in order)."""
    rng = np.random.default_rng(seed)
    art, cap = Drawing(), Capture()
    sender = PanelSender(cap, resync_row_s=0.1)
    t, x, y = 0.0, 16, 16
    for i in range(frames + quiet_frames):
        t += 1 / 30
        if i < frames:
            x = int(np.clip(x + rng.integers(-4, 5), 0, 31))
            y = int(np.clip(y + rng.integers(-4, 5), 0, 31))
            roll = rng.random()
            if roll < 0.03:
                art.apply("next_color")
            elif roll < 0.035:
                art.clear()
            elif roll < 0.05:
                art.apply("next_brush")
            if roll > 0.92:
                art.hide_cursor()
            else:
                art.move(x, y, pen_down=(i // 25) % 2 == 0)
        else:
            art.hide_cursor()                       # holding still: only repair rows go out
        image = art.render(t)
        sender.show(image, t)
        if i % 50 == 0:
            cap.write(JUNK[(i // 50) % len(JUNK)])  # junk sprinkled between real messages
    return image, cap.lines


def run(exe, tmp, lines):
    path = os.path.join(tmp, "session.txt")
    with open(path, "wb") as f:
        f.write(b"".join(lines))
    out_of_range, shows, pixels = subprocess.run(
        [exe, path], check=True, capture_output=True, text=True).stdout.split()
    return int(out_of_range), int(shows), pixels


def hex565(img):
    return "".join(f"{protocol.rgb565(img[r, c]):04x}" for r in range(32) for c in range(32))


def report(ok, text, detail=""):
    print(("PASS " if ok else "FAIL ") + text + ("" if ok or not detail else f": {detail}"))
    return 0 if ok else 1


def main():
    if not shutil.which("g++"):
        print("g++ not found; this check needs a C++ compiler (skip it on Windows).")
        return 0
    fails = 0
    with tempfile.TemporaryDirectory() as tmp:
        with open(os.path.join(tmp, "Arduino.h"), "w") as f:
            f.write(ARDUINO_SHIM)
        src = os.path.join(tmp, "t.cpp")
        with open(src, "w") as f:
            f.write(TEST_CPP)
        exe = os.path.join(tmp, "t")
        subprocess.run(["g++", "-std=c++17", "-Wall", "-Werror", "-I", tmp, "-I", FW, src, "-o", exe],
                       check=True)

        image, lines = session()
        assert image.any(), "the test session drew nothing"
        want = hex565(image)
        oor, shows, pixels = run(exe, tmp, lines)
        diff = sum(pixels[i:i + 4] != want[i:i + 4] for i in range(0, len(want), 4))
        fails += report(diff == 0, "the example receiver shows exactly the laptop's picture",
                        f"{diff} LEDs differ")
        fails += report(oor == 0, "it never paints outside the panel", f"{oor} out-of-range writes")

        # Junk only: after a clear, nothing may light up.
        _, _, pixels = run(exe, tmp, [protocol.encode_clear()] + JUNK * 3)
        lit = sum(pixels[i:i + 4] != "0000" for i in range(0, len(pixels), 4))
        fails += report(lit == 0, "junk, damaged and out-of-range messages change nothing",
                        f"{lit} LEDs lit by junk")

        kept, n = [], 0
        for l in lines:
            if l[:1] == b"P":
                n += 1
                if n % 3 == 0:
                    continue
            kept.append(l)
        assert len(lines) - len(kept) > 50, "test dropped too few messages to mean anything"
        _, _, pixels = run(exe, tmp, kept)
        diff = sum(pixels[i:i + 4] != want[i:i + 4] for i in range(0, len(want), 4))
        fails += report(diff == 0, "with 1 in 3 pixel messages lost, the picture repairs itself",
                        f"{diff} LEDs still wrong")

        no_repair = [l for l in kept if l[:1] != b"R"]          # the check must be able to fail
        _, _, pixels = run(exe, tmp, no_repair)
        diff = sum(pixels[i:i + 4] != want[i:i + 4] for i in range(0, len(want), 4))
        fails += report(diff > 0, "(sanity) without row messages, lost pixels do stay wrong",
                        "the loss test isn't testing anything")

    print("\nAll firmware checks passed." if not fails else f"\n{fails} firmware check(s) FAILED.")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
