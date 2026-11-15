"""Shows a 32x32 picture on the LED panel by sending only what changed.

The laptop owns the picture; the ESP32 just colours LEDs as told. Each frame, show()
compares the new picture with what the panel already has and sends only the LEDs that
differ: usually the one or two around the cursor, a few bytes, so drawing feels instant.

  few LEDs changed in a row      one short "P" message per LED
  many LEDs changed in a row     one "R" message for the whole row (cheaper than many P's)
  picture went completely dark   a single "C"
  nothing changed                use the quiet moment to re-send one row, so a lost
                                 message or a restarted ESP32 gets repaired on its own
"""
import numpy as np

import config
import protocol


class PanelSender:
    def __init__(self, link, w=config.PANEL_W, h=config.PANEL_H,
                 resync_row_s=config.PANEL_RESYNC_ROW_S, row_threshold=config.PANEL_ROW_THRESHOLD):
        self.link = link                 # anything with .write(bytes)
        self.w, self.h = w, h
        self.resync_row_s = resync_row_s
        self.row_threshold = row_threshold
        self.shown = None                # what we believe the panel shows; None = unknown
        self._row = 0                    # next row to re-send
        self._row_due = None
        self.bytes_sent = 0

    def _write(self, data):
        self.link.write(data)
        self.bytes_sent += len(data)

    def invalidate(self):
        """The panel's contents are unknown (ESP32 restarted): send everything again."""
        self.shown = None

    def show(self, image, now):
        """image: (h, w, 3) uint8 RGB. Call once per frame."""
        if self.shown is None:
            self._write(protocol.encode_clear())
            self.shown = np.zeros((self.h, self.w, 3), np.uint8)
        changed = (image != self.shown).any(axis=2)
        if changed.any():
            if not image.any():
                self._write(protocol.encode_clear())
            else:
                for y in np.nonzero(changed.any(axis=1))[0]:
                    xs = np.nonzero(changed[y])[0]
                    if len(xs) >= self.row_threshold:
                        self._write(protocol.encode_row(y, image[y]))
                    else:
                        for x in xs:
                            self._write(protocol.encode_pixel(x, y, image[y, x]))
            self.shown = image.copy()
        elif self.resync_row_s > 0:
            # Idle bandwidth only: never delays ink.
            if self._row_due is None:
                self._row_due = now
            if now >= self._row_due:
                self._write(protocol.encode_row(self._row, image[self._row]))
                self._row = (self._row + 1) % self.h
                self._row_due = max(self._row_due + self.resync_row_s, now)
