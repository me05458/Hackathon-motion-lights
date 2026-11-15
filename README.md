# Hackathon motion lights

Draw on a 32x32 RGB LED panel by moving your finger in the air.

## Setup (Windows!!)

Use Python 3.11, 3.12 or 3.13 (3.12 recommended). In the `laptop` folder, once:

```bash
py -3.12 -m venv .venv
```

```bash
.venv\Scripts\activate
```

```bash
pip install -r requirements.txt
```

Every time after that, only `.venv\Scripts\activate` is needed before running.
macOS/Linux: `python3 -m venv .venv`, then `source .venv/bin/activate`.

## Run(easy)

```bash
python test.py 
```

**What you see in the camera window:**

- **The box** is the panel. Its top-left corner is LED (0, 0). Draw inside it. Its
  colour shows the pen state: red = down, yellow = hover, grey = idle.
- **Top line:** pen state and the measured distance.
- **Bar on the right:** a depth gauge. The white mark is your hand; red, yellow and grey
  are the down, hover and idle zones.
- **Square, top right:** the pen colour.
- **Second line:** colour name, brush size, cursor position, camera frames per second,
  and sensor readings per second.

**Keys** (click the camera window first):

| Key | Does |
|---|---|
| `q` or Esc | quit |
| `c` | clear the drawing |
| `s` | save the drawing as a PNG |
| `[` `]` | shrink / grow the drawing box |
| `p` | set the pen-down distance to where your hand is now |
| `1` `2` `3` | with `--no-serial`: fake pen down / hover / idle |

## Tuning

Everything is in `laptop/config.py`, with a comment on each line.

- **Drawing box** (`DRAW_BOX_CENTER`, `DRAW_BOX_SIZE`): which part of the camera picture
  maps to the panel. The camera picture is wide and the panel is square, so the box is
  a square inside the picture. Smaller means less arm movement but a shakier cursor.
  Keep the box inside the area the ultrasonic sensor can see (see PROTOCOL.md).
- **Pen distances** (`PEN_DOWN_CM`, `PEN_IDLE_CM`): the "x" and "xx" limits. The `p` key
  sets the first one live; copy the printed number into `config.py` to keep it.
- **Cursor feel** (`POINTER_MIN_CUTOFF`, `POINTER_BETA`): the cursor is smoothed more
  when your hand is slow and less when it's fast. Lower the first if it shakes when
  still; raise the second if it trails behind fast strokes.
- **Camera** (`CAMERA_INDEX`, `MIRROR`, `CAMERA_FPS`).

## Commands: changing colour, clearing, brush size

Commands work only while the pen is **up**, and a sign must be **held still** for half a
second (one second for clear), so they can't fire by accident while drawing. A bar at
the bottom of the camera window fills while you hold.

**Before any ASL training,** three built-in gestures work: peace = next colour,
thumbs up = previous colour, fist = clear.

**With ASL letters,** each letter is a command, set in `ASL_COMMANDS` in `config.py`:

| Letter | Command | Letter | Command |
|---|---|---|---|
| R | red | P | purple |
| O | orange | W | white |
| Y | yellow | E | eraser |
| G | green | C | clear |
| B | blue | L | next brush size |

You only train the letters you want. In the `laptop` folder:

1. **Record** the letters, plus one label for your normal relaxed hand:

   ```bash
   python record_asl.py R G B C REST
   ```

   For each one, make the sign, click the camera window, and press SPACE. Move your
   hand a little while it records 200 samples. `REST` has no command: it teaches the
   model what "not a command" looks like. Recordings are added to `asl_data.csv`, so
   you can add more letters or more samples later.

2. **Train:**

   ```bash
   python train_asl.py
   ```

   It prints the accuracy, which letters get mixed up, and which commands are now ready.

3. **Run** `python main.py`. It uses the letters automatically once a model exists.
   `--commands gesture` goes back to the three built-in gestures.

A hand shape the model wasn't trained on is ignored, not matched to the nearest
letter. Letters that involve movement (J, Z) won't work.

## The ESP32 side

The sketch is your team's to write. What it has to do is in **[PROTOCOL.md](PROTOCOL.md)**:
three messages in (`P` set an LED, `C` clear, `R` set a row), one message out
(`D` distance).

Two things help with that:

- `python panel_test.py` (in `laptop`) tests a sketch without the camera: it sends a
  test picture and reports how fast the distance readings arrive.
- `firmware/example_receiver/` is a small, optional example sketch. Its message handling
  is tested on a PC against the laptop code; it has not been run on a real ESP32.

## Files

```
laptop/
  main.py          run this: the loop that ties everything together
  config.py        every setting
  camera.py        opens the webcam
  tracker.py       camera picture -> 21 hand points (MediaPipe)
  pointer.py       fingertip -> steady LED position (the drawing box)
  pen.py           ultrasonic distance -> pen down / hover / idle, and the fusion rule
  filters.py       smoothing maths used by pointer.py and pen.py
  drawing.py       the picture: canvas, colours, brush, cursor
  commands.py      hold-a-sign-to-trigger logic
  gestures.py      hand points -> gesture name (peace, fist, ...)
  asl.py           hand points -> ASL letter
  record_asl.py    record ASL examples        train_asl.py    train the ASL model
  panel.py         sends only the LEDs that changed
  protocol.py      the message formats        link.py         the USB serial port
  board_view.py    on-screen copy of the panel
  panel_test.py    test an ESP32 sketch without the camera
  selftest.py      24 checks that need no hardware
firmware/example_receiver/   optional example ESP32 sketch
tools/check_firmware.py      tests the example's message handling on a PC (needs g++)
PROTOCOL.md                  the laptop <-> ESP32 contract
hackathon*.ino               the team's original test sketches, unchanged
```
