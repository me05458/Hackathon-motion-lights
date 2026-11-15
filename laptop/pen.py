"""The pen: turns ultrasonic distance readings into DOWN / HOVER / IDLE.

        sensor |-- DOWN --|------- HOVER -------|---- IDLE ---->
               0      PEN_DOWN_CM          PEN_IDLE_CM         distance

This is what fixes the "Midas touch" problem of camera-only drawing: the camera never
has to guess whether you mean to draw. You push your hand towards the sensor to draw,
and pull back to stop, like touching and leaving a sheet of paper.

Real ultrasonic sensors are messy, so this handles:
  spikes      one wild reading is ignored (middle value of the last few readings)
  flicker     to leave a state you must move PEN_MARGIN_CM past the limit, not just to it
  dropouts    a missed echo or two keeps the current state; a longer gap means IDLE
  no sensor   no readings at all means IDLE, so the pen can never get stuck down
"""
import config
from filters import Median

DOWN, HOVER, IDLE = "DOWN", "HOVER", "IDLE"


class DistancePen:
    def __init__(self, down_cm=config.PEN_DOWN_CM, idle_cm=config.PEN_IDLE_CM,
                 margin_cm=config.PEN_MARGIN_CM, median_n=config.PEN_MEDIAN,
                 dropout_s=config.PEN_DROPOUT_S):
        self.down_cm, self.idle_cm, self.margin_cm = down_cm, idle_cm, margin_cm
        self.dropout_s = dropout_s
        self.state = IDLE
        self.distance = None             # the steadied distance in cm, or None if unknown
        self._median = Median(median_n)
        self._last_good = None           # time of the last usable reading

    def add(self, cm, now):
        """Feed one sensor reading. cm <= 0 means "no echo"."""
        if cm is not None and cm > 0:
            self._median.add(cm)
            self._last_good = now

    def update(self, now):
        """Call once per camera frame. Returns DOWN, HOVER or IDLE."""
        if self._last_good is None or now - self._last_good > self.dropout_s:
            self._median.clear()
            self.distance = None
            self.state = IDLE
            return self.state
        d = self.distance = self._median.value
        if self.state == DOWN:
            if d > self.down_cm + self.margin_cm:
                self.state = HOVER
        elif d < self.down_cm:
            self.state = DOWN
        if self.state == HOVER and d > self.idle_cm + self.margin_cm:
            self.state = IDLE
        elif self.state == IDLE and d < self.idle_cm:
            self.state = DOWN if d < self.down_cm else HOVER
        return self.state


def combine(sensor_state, hand_visible, inside_box):
    """Sensor fusion: what the camera and the ultrasonic sensor say together.
    Returns (show_cursor, ink). Ink needs BOTH: the sensor saying DOWN and the camera
    seeing a hand inside the drawing box. So neither a passer-by in front of the sensor
    nor a hand waving far from it can draw."""
    if not hand_visible or sensor_state == IDLE:
        return False, False
    return True, sensor_state == DOWN and inside_box
