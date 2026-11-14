// gesture_led.ino - 32x32 RGB panel driven by hand gestures from the laptop,
// with an HC-SR04 ultrasonic sensor whose distance sets the circle size and is sent back.
//
// Panel pins are the same as hackathon_rgbbox.ino. The ultrasonic moved off pins 5 and 18
// (used by the panel) to TRIG=22, ECHO=23. HC-SR04 ECHO is 5 V: put a divider on it
// (e.g. 1k from ECHO to pin 23, 2k from pin 23 to GND) or it can damage the ESP32 pin.
//
// Libraries: "Adafruit Protomatter" (+ Adafruit GFX) from the Library Manager.
#include <Adafruit_Protomatter.h>
#include "laptop_link.h"
#include "gesture_frames.h"

uint8_t rgbPins[]  = {16, 17, 18, 19, 27, 14};
uint8_t addrPins[] = {33, 26, 32, 25};
uint8_t clockPin   = 21;
uint8_t latchPin   = 15;
uint8_t oePin      = 5;
Adafruit_Protomatter matrix(32, 5, 1, rgbPins, 4, addrPins, clockPin, latchPin, oePin, true);

const int TRIG_PIN = 22;
const int ECHO_PIN = 23;
const unsigned long SONAR_EVERY_MS = 100;
const unsigned long ECHO_TIMEOUT_US = 25000;   // ~4 m; stops pulseIn blocking for 1 s

LaptopLink laptop;
float distCm = -1;
unsigned long lastSonarMs = 0;
bool redraw = true;

float readDistanceCm() {
  digitalWrite(TRIG_PIN, LOW);
  delayMicroseconds(2);
  digitalWrite(TRIG_PIN, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG_PIN, LOW);
  unsigned long us = pulseIn(ECHO_PIN, HIGH, ECHO_TIMEOUT_US);
  if (us == 0) return -1;                        // nothing in range
  return us * 0.034f / 2.0f;
}

void setup() {
  Serial.begin(115200);
  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);
  ProtomatterStatus status = matrix.begin();
  if (status != PROTOMATTER_OK) {
    while (true) {                               // panel failed: say why, forever
      Serial.print("Panel error, Protomatter status ");
      Serial.println((int)status);
      delay(1000);
    }
  }
}

void loop() {
  laptop.poll();
  if (laptop.changed()) redraw = true;

  if (millis() - lastSonarMs >= SONAR_EVERY_MS) {
    lastSonarMs = millis();
    float d = readDistanceCm();
    if (distanceRadius(d) != distanceRadius(distCm)) redraw = true;
    distCm = d;
    laptop.sendDistance(distCm);
  }

  if (redraw) {
    redraw = false;
    matrix.fillScreen(0);
    drawGestureFrame(matrix, laptop.gesture, laptop.x, laptop.y, distCm);
    matrix.show();
  }
}
