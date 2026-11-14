"""All tunable settings in one place. Change values here, not in the other files."""

# --- Serial link to the ESP32 ---
SERIAL_PORT = None          # None = auto-detect. Or set e.g. "COM5" (Windows) / "/dev/ttyUSB0" (Linux)
BAUD = 115200
HEARTBEAT_S = 0.5           # resend the current gesture this often so the ESP32 knows we're alive

# --- Camera ---
CAMERA_INDEX = 0
CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480
MIRROR = True               # flip the image so moving your hand right moves the dot right

# --- Hand tracking ---
MODEL_URL = ("https://storage.googleapis.com/mediapipe-models/hand_landmarker/"
             "hand_landmarker/float16/latest/hand_landmarker.task")
MODEL_PATH = "hand_landmarker.task"   # downloaded automatically on first run
MIN_DETECTION_CONFIDENCE = 0.6
MIN_TRACKING_CONFIDENCE = 0.5

# --- Gesture stability ---
STABLE_FRAMES = 3           # a new gesture must be seen this many frames in a row before it counts
SMOOTHING = 0.4             # 0..1, how fast x/y follow the hand (1 = no smoothing)

# --- LED panel (must match the firmware) ---
PANEL_W = 32
PANEL_H = 32
SIM_SCALE = 14              # on-screen board: pixels per LED
