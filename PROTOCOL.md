# Laptop ↔ ESP32 protocol

This is the whole contract between the Python program on the laptop and the ESP32
sketch. If the sketch follows this page, the two work together, whatever else the
sketch does.

**The split:** the laptop does the thinking (hand tracking, pen up/down, colours, the
picture). The ESP32 has two jobs:

1. **Paint the LEDs it is told to paint.**
2. **Print the ultrasonic distance, as often as it can.**

The ESP32 does not need to know about pens, cursors, colours or modes. The blinking
hover cursor is just the laptop turning one LED on and off.

## Serial settings

- USB serial, **115200 baud**, 8 data bits, no parity, 1 stop bit (the Arduino default).
- Plain text (ASCII). **One message per line, ending in `\n`.** A `\r` before it is fine.
- A line that isn't one of the messages below must be **ignored**, by both sides. So
  debug prints are safe, as long as they don't start with `D ` or equal `READY`.

To use a faster speed, change `Serial.begin(...)` in the sketch and `BAUD` in
`laptop/config.py` (or run `python main.py --baud 921600`) to the same number.

## Laptop → ESP32

Coordinates: `x` is the column and `y` is the row, both **0 to 31**. `(0, 0)` is the
**top-left** LED; `x` grows to the right and `y` grows downwards.

| Message | Meaning | Example |
|---|---|---|
| `P <x> <y> <r> <g> <b>` | Set one LED. `r g b` are 0–255. Black (`0 0 0`) turns it off. | `P 12 20 255 0 0` |
| `C` | Clear: every LED off. | `C` |
| `R <y> <hex>` | Set a whole row at once. `<hex>` is exactly 128 hex digits: 32 LEDs, left to right, 4 digits each, in RGB565. | `R 5 f800f800…` |

Fields are separated by single spaces. Numbers are plain decimal.

**RGB565** is the 16-bit colour format LED panel libraries use: 5 bits red, 6 bits
green, 5 bits blue. `f800` is red, `07e0` is green, `001f` is blue, `ffff` is white,
`0000` is off. With Adafruit Protomatter the value goes straight into
`matrix.drawPixel(x, y, value)`. For `P`, convert with `matrix.color565(r, g, b)`.

**When each one is sent:**

- `P`: the moment an LED changes. Moving the hover cursor one step is two `P` lines
  (old LED off, new LED on). Drawing adds one or two more per camera frame.
- `R`: when 8 or more LEDs change in the same row in one frame (cheaper than many
  `P`s). Also, whenever nothing else needs sending, the laptop re-sends one row every
  0.1 s, cycling through the whole picture every 3.2 s. That is the **repair
  mechanism**: if a message was lost, or the ESP32 was restarted, the panel fixes
  itself within a few seconds. Most of these rows change nothing.
- `C`: when the drawing is cleared, and once when the laptop program starts.

Damaged or out-of-range messages (`x` of 40, a row with 127 digits, letters where a
number should be) should be dropped without changing anything.

## ESP32 → laptop

| Message | Meaning | Example |
|---|---|---|
| `D <cm>` | Ultrasonic distance in centimetres. Decimals are welcome. | `D 23.4` |
| `D -1` | No echo came back (nothing in range). | `D -1` |
| `READY` | Optional. Print once at the end of `setup()`. The laptop then re-sends the whole picture straight away. | `READY` |

**Send `D` 20 to 40 times a second.** The distance is the pen tip, so every reading
that arrives late makes the pen feel late. Send every reading, including `-1`; the
laptop does the filtering.

What the laptop does with the distance (all adjustable in `laptop/config.py`):

| Distance | Pen state |
|---|---|
| below 15 cm | **down**: ink |
| 15 to 40 cm | **hover**: blinking cursor, no ink |
| above 40 cm, or no reading for 0.25 s | **idle**: nothing shown |

It uses the middle value of the last 3 readings, so one wild reading does no harm,
and it needs 2 cm of extra movement to switch back, so the pen doesn't flicker.

## Keeping it fast

The laptop sends very little: usually under 2,000 bytes a second, where 115200 baud
can carry about 11,500. The delays that matter are on the ESP32, in `loop()`:

- **No `delay()` in `loop()`.** Use `millis()` to decide when to ping the sensor.
- **Give `pulseIn` a short timeout**, for example
  `pulseIn(ECHO_PIN, HIGH, 8000)`. Without one it waits up to a full second when there
  is no echo, and the panel freezes for that second. 8000 µs covers about 1.3 m.
- **Read every waiting byte each loop** (`while (Serial.available())`), not one line
  per loop.
- **Call `matrix.show()` once per loop**, and only if something changed, not once per
  message.
- **Don't print a reply for every message.** Printing is slow and floods the laptop.
- **Call `Serial.setRxBufferSize(2048);` before `Serial.begin(115200);`.** The default
  buffer holds 256 bytes; a fast stroke can send more than that in one burst while the
  sketch is busy with the sensor.

## Hardware notes

- **Sensor pins:** the panel uses pins 5 and 18 (see `hackathon_rgbbox.ino`), which
  `hackathon.ino` also used for the ultrasonic sensor. They can't share. The example
  uses TRIG = 22 and ECHO = 23.
- **ECHO is 5 V** on an HC-SR04 and the ESP32 is 3.3 V. Use a divider: 1 kΩ from ECHO to
  the ESP32 pin, 2 kΩ from that pin to GND.
- **The sensor sees a narrow cone**, roughly 15° either side of straight ahead. At
  15 cm that is a patch only about 8 cm wide. If the hand leaves the cone while drawing,
  the sensor reads the wall behind it and the pen lifts. Point the sensor so the cone
  covers the area the hand draws in, and shrink the laptop's drawing box (`[` key) to
  fit. A flat hand reflects better than a single finger.

## Testing the sketch without the camera

**By hand:** open the Arduino Serial Monitor at 115200 baud, line ending "Newline", and type:

```
C
P 0 0 255 0 0
P 31 31 0 0 255
R 10 ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff
```

Expected: panel clears, top-left LED red, bottom-right LED blue, row 10 all white.
`D` lines should be scrolling past the whole time.

**With the test tool** (close the Serial Monitor first), from the `laptop` folder:

```bash
python panel_test.py
```

It sends a test picture, moves a dot across the panel at camera speed, then reports how
many distance readings per second arrive and the longest gap between them. The picture
to expect is described at the top of `laptop/panel_test.py`.

## Example code

`firmware/example_receiver/` has a small sketch that does all of the above:
`panel_protocol.h` reads the messages and `example_receiver.ino` wires it to the panel
and the sensor. It is optional: use it, copy from it, or ignore it. Its message handling
is tested on a PC against the laptop code (`tools/check_firmware.py`), but it has not
been compiled for or run on a real ESP32, so treat the pin numbers and the first upload
as untested.
