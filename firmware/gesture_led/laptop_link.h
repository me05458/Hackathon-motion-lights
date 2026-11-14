// laptop_link.h - reads gesture messages from the laptop over USB serial.
//
// Drop this file next to any .ino and add three lines:
//
//   #include "laptop_link.h"     // top of the sketch
//   LaptopLink laptop;           // global, under the #include
//   laptop.poll();               // first line of loop()
//
// Then read  laptop.gesture  ("NONE", "OPEN", "FIST", "POINT", "PEACE", "THUMBS_UP"),
//            laptop.x, laptop.y  (LED coordinates 0..31),
//            laptop.is("OPEN")   (true/false),
//            laptop.changed()    (true once after each new message).
// Optional:  laptop.sendDistance(cm);   sends the ultrasonic reading back to the laptop.
//
// Serial.begin(115200) must already be in setup(). poll() never blocks, but long delay()s
// in loop() make the board react late, so keep delays short.
// Note: the variable is called `laptop`, not `link`, because link() already exists on ESP32.
//
// Protocol (must match laptop/protocol.py):
//   laptop -> ESP32:  "G <GESTURE> <x> <y>\n"
//   ESP32 -> laptop:  "D <cm>\n"
#pragma once
#include <Arduino.h>
#include <string.h>
#include <stdlib.h>

class LaptopLink {
 public:
  char gesture[12] = "NONE";
  int x = 16;
  int y = 16;
  unsigned long timeoutMs = 2000;   // no message for this long -> gesture goes back to NONE

  // Call every loop(). Reads all waiting bytes without blocking.
  void poll(Stream &port = Serial) {
    while (port.available()) {
      char c = (char)port.read();
      if (c == '\r') continue;
      if (c == '\n') {
        buf_[len_] = '\0';
        handleLine(buf_);
        len_ = 0;
      } else if (len_ < sizeof(buf_) - 1) {
        buf_[len_++] = c;
      } else {
        len_ = 0;                      // line too long: junk, start over
      }
    }
    if (lastMsgMs_ != 0 && millis() - lastMsgMs_ > timeoutMs && strcmp(gesture, "NONE") != 0) {
      strcpy(gesture, "NONE");
      changed_ = true;
    }
  }

  bool is(const char *name) const { return strcmp(gesture, name) == 0; }

  // True once after a message that changed something.
  bool changed() {
    bool c = changed_;
    changed_ = false;
    return c;
  }

  bool connected() const { return lastMsgMs_ != 0 && millis() - lastMsgMs_ <= timeoutMs; }

  void sendDistance(float cm, Print &port = Serial) {
    port.print("D ");
    port.println(cm, 1);
  }

  // Public so it can be unit-tested on a PC; normally poll() calls it.
  bool handleLine(char *line) {
    char *save = nullptr;
    char *tag = strtok_r(line, " ", &save);
    char *g = strtok_r(nullptr, " ", &save);
    char *sx = strtok_r(nullptr, " ", &save);
    char *sy = strtok_r(nullptr, " ", &save);
    if (!tag || !g || !sx || !sy || strcmp(tag, "G") != 0) return false;
    if (strtok_r(nullptr, " ", &save) != nullptr) return false;
    if (!known(g) || strlen(g) >= sizeof(gesture)) return false;
    char *end;
    long nx = strtol(sx, &end, 10);
    if (*end) return false;
    long ny = strtol(sy, &end, 10);
    if (*end) return false;
    nx = nx < 0 ? 0 : (nx > 31 ? 31 : nx);
    ny = ny < 0 ? 0 : (ny > 31 ? 31 : ny);
    if (strcmp(g, gesture) != 0 || nx != x || ny != y) changed_ = true;
    strcpy(gesture, g);
    x = (int)nx;
    y = (int)ny;
    lastMsgMs_ = millis();
    if (lastMsgMs_ == 0) lastMsgMs_ = 1;
    return true;
  }

 private:
  char buf_[48];
  size_t len_ = 0;
  unsigned long lastMsgMs_ = 0;
  bool changed_ = false;

  static bool known(const char *g) {
    static const char *const names[] = {"NONE", "OPEN", "FIST", "POINT", "PEACE", "THUMBS_UP"};
    for (const char *n : names)
      if (strcmp(g, n) == 0) return true;
    return false;
  }
};
