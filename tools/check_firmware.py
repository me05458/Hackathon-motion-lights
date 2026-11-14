"""Compiles the firmware headers on this PC (needs g++) and checks that:
  1. laptop_link.h parses messages the way laptop/protocol.py writes them, and rejects junk;
  2. gesture_frames.h draws exactly the same pixels as laptop/frames.py.
Run from anywhere:  python tools/check_firmware.py
"""
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FW = os.path.join(ROOT, "firmware", "gesture_led")
sys.path.insert(0, os.path.join(ROOT, "laptop"))
import frames      # noqa: E402
import protocol    # noqa: E402

# Minimal stand-ins for the Arduino core, just enough for the two headers.
ARDUINO_SHIM = r"""
#pragma once
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <string>
static unsigned long fake_ms = 1000;
inline unsigned long millis() { return fake_ms; }
struct Print {
  std::string out;
  void print(const char *s) { out += s; }
  void println(float v, int d) { char b[32]; snprintf(b, sizeof b, "%.*f\n", d, v); out += b; }
};
struct Stream : Print {
  std::string in; size_t pos = 0;
  int available() { return (int)(in.size() - pos); }
  int read() { return (unsigned char)in[pos++]; }
};
static Stream Serial;
"""

TEST_CPP = r"""
#include "laptop_link.h"
#include "gesture_frames.h"
#include <map>

struct Canvas {
  uint16_t px[32][32] = {};
  uint16_t color565(uint8_t r, uint8_t g, uint8_t b) {
    return ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3);
  }
  void drawPixel(int x, int y, uint16_t c) { px[y][x] = c; }
};

int main(int argc, char **argv) {
  // --- parser ---
  Stream s;
  LaptopLink L;
  s.in = INPUT_LINES;
  L.poll(s);
  printf("parsed %s %d %d %d\n", L.gesture, L.x, L.y, (int)L.changed());
  fake_ms += 5000; L.poll(s);
  printf("timeout %s\n", L.gesture);
  L.sendDistance(42.25f, s);
  printf("sent %s", s.out.c_str());

  // --- frames ---
  const char *gs[] = {"NONE", "OPEN", "FIST", "POINT", "PEACE", "THUMBS_UP"};
  const int pos[][2] = {{0, 0}, {16, 16}, {31, 31}, {2, 29}, {30, 3}};
  const float dists[] = {-1, 3, 10, 47.9f, 100, 400};
  for (auto g : gs) for (auto &p : pos) for (float d : dists) {
    Canvas c;
    drawGestureFrame(c, g, p[0], p[1], d);
    printf("frame %s %d %d %g ", g, p[0], p[1], d);
    for (int y = 0; y < 32; y++) for (int x = 0; x < 32; x++) printf("%04x", c.px[y][x]);
    printf("\n");
  }
}
"""


def rgb565(c):
    r, g, b = (int(v) for v in c)
    return ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)


def main():
    if not shutil.which("g++"):
        print("g++ not found; this check needs a C++ compiler (skip it on Windows).")
        return 0
    # Good message last; junk lines before it must be ignored, not crash or change state.
    lines = ["Object detected", "G WAVE 1 2", "G OPEN 1", "G OPEN a 2", "G OPEN 1 2 3",
             "x" * 200, "D 12.0", protocol.encode_gesture("PEACE", 4, 40).decode().strip()]
    c_lines = "".join(l.replace('"', '\\"') + "\\r\\n" for l in lines)
    with tempfile.TemporaryDirectory() as tmp:
        with open(os.path.join(tmp, "Arduino.h"), "w") as f:
            f.write(ARDUINO_SHIM)
        src = os.path.join(tmp, "t.cpp")
        with open(src, "w") as f:
            f.write(f'#define INPUT_LINES "{c_lines}"\n' + TEST_CPP)
        exe = os.path.join(tmp, "t")
        subprocess.run(["g++", "-std=c++17", "-Wall", "-Werror", "-I", tmp, "-I", FW, src, "-o", exe],
                       check=True)
        out = subprocess.run([exe], check=True, capture_output=True, text=True).stdout.splitlines()

    fails = 0
    # y=40 is clamped to 31; the distance reply must parse with protocol.parse_distance.
    want = ["parsed PEACE 4 31 1", "timeout NONE", "sent D 42.2"]
    for w, g in zip(want, out[:3]):
        if w.startswith("sent"):
            d = protocol.parse_distance(g[len("sent "):])
            ok = d is not None and abs(d - 42.25) <= 0.05
        else:
            ok = g == w
        print(("PASS " if ok else "FAIL ") + g + ("" if ok else f"   (expected {w})"))
        fails += not ok
    frames_checked = 0
    for line in out[3:]:
        _, g, x, y, d, hexpx = line.split()
        x, y, d = int(x), int(y), float(d)
        img = frames.render(g, x, y, d)
        py = "".join(f"{rgb565(img[r, c]):04x}" for r in range(32) for c in range(32))
        if py != hexpx:
            print(f"FAIL frame {g} at {x},{y} dist {d}: firmware and laptop board differ")
            fails += 1
        frames_checked += 1
    print(f"{'PASS' if not fails else 'FAIL'} {frames_checked} frames compared, firmware == laptop board"
          if not fails else f"{fails} failures")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
