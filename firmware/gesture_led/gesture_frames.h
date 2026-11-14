// gesture_frames.h - draws one 32x32 frame for a gesture.
//
// Line-by-line twin of laptop/frames.py, so the on-screen board on the laptop shows the
// same picture as the real panel. Change both together, then run tools/check_firmware.py.
//
// G is anything with drawPixel(x, y, color) and color565(r, g, b), e.g. Adafruit_Protomatter.
#pragma once
#include <string.h>

static const int FRAME_W = 32;
static const int FRAME_H = 32;

// Closer hand -> bigger circle. Unknown distance (<= 0) -> 5.
inline int distanceRadius(float distCm) {
  if (distCm <= 0) return 5;
  int d = (int)distCm;
  if (d < 5) d = 5;
  if (d > 100) d = 100;
  return 10 - (d - 5) * 8 / 95;   // 5 cm -> 10, 100 cm -> 2
}

template <typename G>
void framePixel(G &g, int x, int y, uint16_t c) {
  if (x >= 0 && x < FRAME_W && y >= 0 && y < FRAME_H) g.drawPixel(x, y, c);
}

template <typename G>
void frameRect(G &g, int x0, int y0, int w, int h, uint16_t c) {
  for (int yy = y0; yy < y0 + h; yy++)
    for (int xx = x0; xx < x0 + w; xx++) framePixel(g, xx, yy, c);
}

// Caller clears the screen first (fillScreen(0)) and calls show() after.
template <typename G>
void drawGestureFrame(G &g, const char *gesture, int x, int y, float distCm) {
  if (strcmp(gesture, "OPEN") == 0) {              // green disc, size from ultrasonic
    int r = distanceRadius(distCm);
    uint16_t c = g.color565(0, 255, 0);
    for (int dy = -r; dy <= r; dy++)
      for (int dx = -r; dx <= r; dx++)
        if (dx * dx + dy * dy <= r * r + r) framePixel(g, x + dx, y + dy, c);
  } else if (strcmp(gesture, "FIST") == 0) {       // red 7x7 block
    frameRect(g, x - 3, y - 3, 7, 7, g.color565(255, 0, 0));
  } else if (strcmp(gesture, "POINT") == 0) {      // white 3x3 dot
    frameRect(g, x - 1, y - 1, 3, 3, g.color565(255, 255, 255));
  } else if (strcmp(gesture, "PEACE") == 0) {      // two yellow bars
    uint16_t c = g.color565(255, 255, 0);
    frameRect(g, x - 3, y - 5, 1, 11, c);
    frameRect(g, x + 3, y - 5, 1, 11, c);
  } else if (strcmp(gesture, "THUMBS_UP") == 0) {  // magenta plus sign
    uint16_t c = g.color565(255, 0, 255);
    frameRect(g, x - 6, y, 13, 1, c);
    frameRect(g, x, y - 6, 1, 13, c);
  } else {                                         // NONE: dim blue border
    uint16_t c = g.color565(0, 0, 64);
    frameRect(g, 0, 0, FRAME_W, 1, c);
    frameRect(g, 0, FRAME_H - 1, FRAME_W, 1, c);
    frameRect(g, 0, 0, 1, FRAME_H, c);
    frameRect(g, FRAME_W - 1, 0, 1, FRAME_H, c);
  }
}
