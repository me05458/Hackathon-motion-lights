"""All tunable settings in one place. Change values here, not in the other files."""

# --- Serial link to the ESP32 ---
SERIAL_PORT = None          # None = auto-detect. Or set e.g. "COM5" (Windows) / "/dev/ttyUSB0" (Linux)
BAUD = 115200               # must match Serial.begin(...) in the ESP32 sketch

# --- Camera ---
CAMERA_INDEX = 0            # an external (Logitech) camera is usually 1; or use --camera 1
CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480
CAMERA_FPS = 0              # 0 = leave the camera's default. Try 60 if your camera supports it.
MIRROR = True               # flip the image so moving your hand right moves the cursor right

# --- Hand tracking ---
MODEL_URL = ("https://storage.googleapis.com/mediapipe-models/hand_landmarker/"
             "hand_landmarker/float16/latest/hand_landmarker.task")
MODEL_PATH = "hand_landmarker.task"   # downloaded automatically on first run
MIN_DETECTION_CONFIDENCE = 0.6
MIN_TRACKING_CONFIDENCE = 0.5
STABLE_FRAMES = 3           # a gesture/letter must be seen this many frames in a row to count

# --- Drawing area: the square part of the camera picture that IS the 32x32 panel ---
# You draw inside this box, so you never have to reach the edges of the camera view.
DRAW_BOX_CENTER = (0.5, 0.5)    # where the box sits in the picture: (0..1 across, 0..1 down)
DRAW_BOX_SIZE = 0.70            # side of the box, as a fraction of the picture's height
                                # smaller = less arm movement, but a shakier cursor

# --- Cursor smoothing ("One Euro" filter: steady when slow, quick when fast) ---
POINTER_MIN_CUTOFF = 1.5    # lower = steadier when the hand is nearly still, but more lag
POINTER_BETA = 0.3          # higher = follows fast strokes more closely (less lag, more jitter)
POINTER_STICKINESS = 0.15   # how far past an LED's edge (in LEDs) the finger must go before
                            # the cursor moves on; stops flicker between two neighbouring LEDs

# --- The pen: the ultrasonic sensor decides down / hover / idle ---
PEN_DOWN_CM = 15.0          # closer than this = pen DOWN (ink)                  ("x")
PEN_IDLE_CM = 40.0          # further than this = IDLE; in between = HOVER       ("xx")
PEN_MARGIN_CM = 2.0         # must move this far back past a limit to switch back, so a hand
                            # sitting right on a limit doesn't flicker between two states
PEN_MEDIAN = 3              # use the middle value of the last N readings: kills single spikes
PEN_DROPOUT_S = 0.25        # no usable reading for this long = IDLE (pen can never stick down)

# --- Drawing ---
# The pen colours, in the order "next colour" steps through them.
DRAW_PALETTE = [
    ("red", (255, 0, 0)),
    ("orange", (255, 128, 0)),
    ("yellow", (255, 255, 0)),
    ("green", (0, 255, 0)),
    ("cyan", (0, 255, 255)),
    ("blue", (0, 0, 255)),
    ("purple", (160, 0, 255)),
    ("white", (255, 255, 255)),
    ("eraser", (0, 0, 0)),
]
MAX_BRUSH = 3               # brush sizes 1..MAX_BRUSH (a brush of 2 paints 2x2 LEDs)

# --- Commands: hold a sign still to change colour, clear, etc. ---
# Commands only work while the pen is UP (hover or idle), never while drawing.
# Actions:  "color:<name>"  "next_color"  "prev_color"  "clear"  "brush:<n>"  "next_brush"
COMMAND_HOLD_S = 0.5        # hold a sign this long before it counts
CLEAR_HOLD_S = 1.0          # clearing needs a longer hold, so it can't happen by accident
COMMAND_REPEAT_S = 1.0      # next/prev colour and next brush repeat this often while held

# ASL letters -> action. Only these letters need training (python record_asl.py R G B ...).
# Any other label you record (for example REST, for your relaxed drawing hand) does nothing,
# which is useful: it teaches the model what is NOT a command.
ASL_COMMANDS = {
    "R": "color:red",
    "O": "color:orange",
    "Y": "color:yellow",
    "G": "color:green",
    "B": "color:blue",
    "P": "color:purple",
    "W": "color:white",
    "E": "color:eraser",
    "C": "clear",
    "L": "next_brush",
}
# Used when no ASL model has been trained yet (or with --commands gesture).
GESTURE_COMMANDS = {
    "PEACE": "next_color",
    "THUMBS_UP": "prev_color",
    "FIST": "clear",
}

# --- ASL model files ---
ASL_DATA_PATH = "asl_data.csv"      # written by record_asl.py
ASL_MODEL_PATH = "asl_model.joblib" # written by train_asl.py
ASL_MIN_CONFIDENCE = 0.6            # below this the letter shows as "?"

# --- LED panel ---
PANEL_W = 32
PANEL_H = 32
SIM_SCALE = 14              # on-screen board: screen pixels per LED
CURSOR_BLINK_HZ = 2.0       # cursor blinks this many times a second
PANEL_RESYNC_ROW_S = 0.1    # when nothing else needs sending, re-send one row of the picture
                            # this often (the whole picture every 3.2 s), so the panel repairs
                            # itself after a lost message or an ESP32 restart. 0 = never.
PANEL_ROW_THRESHOLD = 8     # this many changed LEDs in one row = send the whole row at once
