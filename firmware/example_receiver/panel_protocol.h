// panel_protocol.h - reads the laptop's plain-text messages and paints them on the panel.
//
// OPTIONAL EXAMPLE. The real firmware is whatever your team writes; this file only shows
// one tested way to read the messages described in PROTOCOL.md. Use it, copy from it, or
// ignore it.
//
//   #include "panel_protocol.h"
//   PanelProtocol laptop;
//   ...
//   if (laptop.poll(matrix)) matrix.show();     // in loop(): never blocks
//
// "matrix" can be anything with drawPixel(x, y, color565) and fillScreen(color565),
// such as Adafruit_Protomatter.
//
// Messages (one per line, ending in '\n'):
//   P <x> <y> <r> <g> <b>    set one LED. x, y: 0..31. r, g, b: 0..255
//   C                        all LEDs off
//   R <y> <128 hex digits>   set a whole row: 32 LEDs x 4 hex digits of RGB565
// Anything else, or anything damaged, is ignored.
#pragma once
#include <Arduino.h>
#include <string.h>
#include <stdlib.h>

class PanelProtocol {
 public:
  static const int W = 32;
  static const int H = 32;

  static uint16_t rgb565(long r, long g, long b) {
    return (uint16_t)(((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3));
  }

  // Reads every byte that has arrived, without waiting for more.
  // Returns true if any LED changed, so the caller knows to call show().
  template <typename G>
  bool poll(G &panel, Stream &port = Serial) {
    bool changed = false;
    while (port.available()) {
      char c = (char)port.read();
      if (c == '\r') continue;
      if (c == '\n') {
        if (!tooLong_) {
          buf_[len_] = '\0';
          if (handleLine(panel, buf_)) changed = true;
        }
        len_ = 0;
        tooLong_ = false;
      } else if (len_ < sizeof(buf_) - 1) {
        buf_[len_++] = c;
      } else {
        tooLong_ = true;            // junk: skip everything up to the next newline
      }
    }
    return changed;
  }

  // Handles one complete line. Returns true if it changed an LED.
  template <typename G>
  bool handleLine(G &panel, const char *line) {
    char tag = line[0];
    if (tag == 'C' && line[1] == '\0') {
      panel.fillScreen(0);
      return true;
    }
    if (line[1] != ' ') return false;
    const char *p = line + 2;

    if (tag == 'P') {
      long v[5];
      for (int i = 0; i < 5; i++) {
        char *end;
        v[i] = strtol(p, &end, 10);
        if (end == p) return false;                 // not a number
        p = end;
        if (i < 4 && *p != ' ') return false;
      }
      if (*p != '\0') return false;                 // something extra on the line
      if (v[0] < 0 || v[0] >= W || v[1] < 0 || v[1] >= H) return false;
      for (int i = 2; i < 5; i++)
        if (v[i] < 0 || v[i] > 255) return false;
      panel.drawPixel((int)v[0], (int)v[1], rgb565(v[2], v[3], v[4]));
      return true;
    }

    if (tag == 'R') {
      char *end;
      long y = strtol(p, &end, 10);
      if (end == p || *end != ' ' || y < 0 || y >= H) return false;
      p = end + 1;
      if (strlen(p) != (size_t)W * 4) return false;
      uint16_t row[W];                              // decode fully first, so a damaged
      for (int x = 0; x < W; x++) {                 // row changes nothing
        uint16_t value = 0;
        for (int i = 0; i < 4; i++) {
          int d = hexDigit(p[x * 4 + i]);
          if (d < 0) return false;
          value = (uint16_t)((value << 4) | d);
        }
        row[x] = value;
      }
      for (int x = 0; x < W; x++) panel.drawPixel(x, (int)y, row[x]);
      return true;
    }
    return false;
  }

 private:
  char buf_[160];                   // longest message is a row: "R 31 " + 128 hex digits
  size_t len_ = 0;
  bool tooLong_ = false;

  static int hexDigit(char c) {
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'a' && c <= 'f') return c - 'a' + 10;
    if (c >= 'A' && c <= 'F') return c - 'A' + 10;
    return -1;
  }
};
