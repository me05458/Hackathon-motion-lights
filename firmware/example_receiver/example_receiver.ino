// example_receiver.ino - OPTIONAL EXAMPLE of the ESP32 side of the air-drawing project.
//
// The real firmware is whatever your team writes. This sketch is a small working example
// of the two jobs PROTOCOL.md asks of the ESP32:
//   1. paint the LEDs the laptop tells it to           (panel_protocol.h)
//   2. print the ultrasonic distance, often            ("D 23.4")
// It has not been compiled or run on a real ESP32 by its author: the message handling
// was tested on a PC against the laptop code (tools/check_firmware.py).
//
// Set the pins below to match YOUR wiring. Panel pins here are from hackathon_rgbbox.ino.
// The HC-SR04's ECHO pin is 5 V: put a divider between it and the ESP32 pin.
//
// Libraries: "Adafruit Protomatter" (+ Adafruit GFX) from the Library Manager.
#include <Adafruit_Protomatter.h>
#include "panel_protocol.h"

uint8_t rgbPins[]  = {16, 17, 18, 19, 27, 14};
uint8_t addrPins[] = {33, 26, 32, 25};
uint8_t clockPin   = 21;
uint8_t latchPin   = 15;
uint8_t oePin      = 5;
Adafruit_Protomatter matrix(32, 5, 1, rgbPins, 4, addrPins, clockPin, latchPin, oePin, true);

const int TRIG_PIN = 22;                       // must not be a pin the panel uses
const int ECHO_PIN = 23;
const unsigned long PING_EVERY_MS = 35;        // about 28 readings a second
const unsigned long ECHO_TIMEOUT_US = 8000;    // give up after 8 ms (about 1.3 m): keeps loop() fast

PanelProtocol laptop;
unsigned long lastPingMs = 0;

float readDistanceCm() {
  digitalWrite(TRIG_PIN, LOW);
  delayMicroseconds(2);
  digitalWrite(TRIG_PIN, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG_PIN, LOW);
  unsigned long us = pulseIn(ECHO_PIN, HIGH, ECHO_TIMEOUT_US);
  if (us == 0) return -1;                      // no echo in time
  return us * 0.0343f / 2.0f;
}

void setup() {
  Serial.setRxBufferSize(2048);                // room for a burst of messages; must come before begin()
  Serial.begin(115200);
  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);
  ProtomatterStatus status = matrix.begin();
  if (status != PROTOMATTER_OK) {
    while (true) {                             // panel failed: say why, forever
      Serial.print("Panel error, Protomatter status ");
      Serial.println((int)status);
      delay(1000);
    }
  }
  matrix.fillScreen(0);
  matrix.show();
  Serial.println("READY");                     // tells the laptop to send the whole picture again
}

void loop() {
  // 1. Paint whatever the laptop sent. One show() per loop, however many LEDs changed.
  if (laptop.poll(matrix)) matrix.show();

  // 2. Report the distance. No delay() anywhere: the loop must keep spinning.
  if (millis() - lastPingMs >= PING_EVERY_MS) {
    lastPingMs = millis();
    Serial.print("D ");
    Serial.println(readDistanceCm(), 1);
  }
}
