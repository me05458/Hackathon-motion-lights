"""Air drawing on a 32x32 LED panel: the camera finds your fingertip, the ultrasonic
sensor is the pen tip.

  python main.py                  ESP32 plugged in: its ultrasonic sensor is the pen
  python main.py --no-serial      no ESP32: on-screen board only, keys 1/2/3 fake the sensor
  python main.py --camera 1       use another camera (an external webcam is usually 1)
  python main.py --pen gesture    no sensor: pointing draws, any other hand shape hovers

Each camera frame does the same five steps (see the loop in main()):
  1. camera    -> where is the index fingertip?            (tracker.py, pointer.py)
  2. sensor    -> is the pen down, hovering or idle?       (link.py, pen.py)
  3. combine   -> move the cursor, leave ink if pen down   (drawing.py)
  4. commands  -> a sign held still changes colour etc.    (commands.py, asl.py)
  5. panel     -> send only the LEDs that changed          (panel.py)

Click the camera window, then use the keys:
  q / Esc  quit              c  clear            s  save the drawing as a PNG
  [  ]     shrink / grow the drawing box
  p        set the pen-down distance to where your hand is now
  1 2 3    (--no-serial only) pretend the hand is at pen-down / hover / idle distance
"""
import argparse
import os
import sys
import time

import camera
import cv2

import board_view
import config
import gestures
import pen as pen_states
from commands import HoldTrigger
from drawing import Drawing
from link import NullLink, SerialLink
from panel import PanelSender
from pen import DistancePen
from pointer import Pointer

STATE_COLOURS = {pen_states.DOWN: (0, 0, 255), pen_states.HOVER: (0, 255, 255),
                 pen_states.IDLE: (160, 160, 160)}          # B, G, R for OpenCV


def parse_args():
    p = argparse.ArgumentParser(description="Air drawing on a 32x32 LED panel")
    p.add_argument("--no-serial", action="store_true", help="don't talk to the ESP32")
    p.add_argument("--port", help="serial port, e.g. COM5 (default: auto-detect)")
    p.add_argument("--baud", type=int, default=config.BAUD, help=f"serial speed (default {config.BAUD})")
    p.add_argument("--camera", type=int, default=config.CAMERA_INDEX, help="camera index (default 0)")
    p.add_argument("--pen", choices=("sensor", "gesture"), default="sensor",
                   help="sensor: ultrasonic distance decides pen down/hover/idle (default). "
                        "gesture: pointing = pen down, any other hand shape = hover")
    p.add_argument("--commands", choices=("auto", "asl", "gesture", "none"), default="auto",
                   help="what changes colour etc: trained ASL letters, built-in gestures, or "
                        "nothing. auto = ASL if a trained model exists, otherwise gestures")
    p.add_argument("--no-board", action="store_true", help="hide the on-screen LED board")
    return p.parse_args()


def load_commands(choice):
    """Returns (asl classifier or None, {sign: action})."""
    if choice == "none":
        return None, {}
    if choice == "asl" or (choice == "auto" and os.path.exists(config.ASL_MODEL_PATH)):
        import asl
        letters = asl.ASLClassifier()                # raises a clear error if not trained
        if choice == "auto" and letters.max_distance is None:
            # A model from before letters were commands: it can't reject unknown hand
            # shapes, so a relaxed hand would keep triggering whichever letter is nearest.
            print("Your ASL model is from an older version. Run  python train_asl.py  to update "
                  "it (no re-recording needed). Using the built-in gestures for now.")
        else:
            usable = {k: v for k, v in config.ASL_COMMANDS.items() if k in letters.letters}
            print("ASL commands: " + (", ".join(f"{k}={v}" for k, v in usable.items())
                                      or "none of the trained letters has a command (see ASL_COMMANDS)"))
            if all(k in config.ASL_COMMANDS for k in letters.letters):
                print("Tip: also record your relaxed hand, e.g.  python record_asl.py REST  then "
                      "train again, so it isn't mistaken for a letter.")
            return letters, usable
    print("Gesture commands: " + ", ".join(f"{k}={v}" for k, v in config.GESTURE_COMMANDS.items()))
    return None, dict(config.GESTURE_COMMANDS)


def draw_overlay(frame, pointer, art, state, pen, link, trigger, sign_text, note, fps, simulated):
    """Everything drawn on top of the camera picture."""
    h, w = frame.shape[:2]
    left, top, side = (int(v) for v in pointer.box.rect(w, h))
    colour = STATE_COLOURS[state]
    cv2.rectangle(frame, (left, top), (left + side, top + side), colour, 2)   # the drawing box

    dist = f"{pen.distance:.0f} cm" if pen.distance is not None else "no reading"
    if simulated:
        dist += " (keys 1/2/3)"
    cv2.putText(frame, f"PEN {state}   {dist}", (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.75, colour, 2)
    where = f"({art.cursor[0]},{art.cursor[1]})" if art.cursor else "(-)"
    rate = f"   sensor {link.readings_per_s:.0f}/s" if link.connected else ""
    cv2.putText(frame, f"{art.color_name}  brush {art.brush}  {where}   {fps:.0f} fps{rate}",
                (10, 54), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 0), 2)

    r, g, b = art.color                                                       # pen colour swatch
    cv2.rectangle(frame, (w - 60, 10), (w - 10, 60), (b, g, r), -1)
    cv2.rectangle(frame, (w - 60, 10), (w - 10, 60), (255, 255, 255), 2)

    # Depth gauge down the right edge: where the hand is between the sensor (top) and far away.
    gy0, gy1, gx = 80, h - 20, w - 30
    span = max(config.PEN_IDLE_CM * 1.5, 1)
    to_y = lambda cm: int(gy0 + (gy1 - gy0) * min(1.0, cm / span))            # noqa: E731
    cv2.rectangle(frame, (gx, gy0), (gx + 14, to_y(pen.down_cm)), STATE_COLOURS[pen_states.DOWN], -1)
    cv2.rectangle(frame, (gx, to_y(pen.down_cm)), (gx + 14, to_y(pen.idle_cm)), STATE_COLOURS[pen_states.HOVER], -1)
    cv2.rectangle(frame, (gx, to_y(pen.idle_cm)), (gx + 14, gy1), STATE_COLOURS[pen_states.IDLE], -1)
    if pen.distance is not None:
        y = to_y(pen.distance)
        cv2.line(frame, (gx - 8, y), (gx + 22, y), (255, 255, 255), 3)

    if sign_text:                                                             # command being held
        cv2.putText(frame, sign_text, (10, h - 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
        cv2.rectangle(frame, (10, h - 30), (10 + int(200 * trigger.progress), h - 15), (255, 255, 0), -1)
        cv2.rectangle(frame, (10, h - 30), (210, h - 15), (255, 255, 255), 1)
    if note:
        cv2.putText(frame, note, (10, 84), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)


def main():
    args = parse_args()
    from tracker import HandTracker, draw_hand   # imported here so --help works without MediaPipe

    try:
        letters, actions = load_commands(args.commands)
    except (FileNotFoundError, RuntimeError) as e:
        print(e)
        return 1

    if args.no_serial:
        link = NullLink()
        if args.pen == "sensor":
            link.sim_cm = config.PEN_IDLE_CM + 20                 # start idle; keys 1/2/3 change it
            print("No ESP32: press 1 (pen down), 2 (hover) or 3 (idle) to fake the sensor.")
    else:
        try:
            link = SerialLink(port=args.port, baud=args.baud)
            print(f"Connected to ESP32 on {link.port}")
        except Exception as e:
            print(f"Serial error: {e}")
            print("Tip: close the Arduino Serial Monitor (only one program can use the port), "
                  "or run with --no-serial.")
            return 1

    cap = camera.open_camera(args.camera)
    if cap is None:
        print(camera.camera_help(args.camera))
        link.close()
        return 1

    simulated = getattr(link, "sim_cm", None) is not None    # faking the sensor with keys?
    tracker = HandTracker()
    pointer = Pointer()
    pen = DistancePen()
    art = Drawing()
    sender = PanelSender(link)
    trigger = HoldTrigger(actions)
    gesture_filter = gestures.GestureFilter(config.STABLE_FRAMES)
    letter_filter = gestures.GestureFilter(config.STABLE_FRAMES, start="?")
    note, note_until = "", 0.0
    fps, last_frame_at = 0.0, time.monotonic()
    try:
        while True:
            ok, frame = camera.read_frame(cap)
            if not ok:
                print("Camera stopped sending frames.\n" + camera.camera_help(args.camera))
                break
            if config.MIRROR:
                frame = cv2.flip(frame, 1)
            now = time.monotonic()
            fps += 0.1 * (1.0 / max(now - last_frame_at, 1e-3) - fps)
            last_frame_at = now
            frame_h, frame_w = frame.shape[:2]

            # 1. Camera: where is the index fingertip (landmark 8)?
            raw_gesture, lm = tracker.process(frame)
            gesture = gesture_filter.update(raw_gesture)
            if lm is not None:
                lx, ly, inside = pointer.update(lm[8].x, lm[8].y, frame_w, frame_h, now)
            else:
                pointer.reset()

            # 2. Sensor: is the pen down, hovering or idle?
            for cm, at in link.poll(now):
                pen.add(cm, at)
            if link.restarted:
                sender.invalidate()              # ESP32 rebooted: send the whole picture again
            state = pen.update(now)
            if args.pen == "gesture":
                pointing = gesture == "POINT" and raw_gesture == "POINT"
                state = pen_states.DOWN if pointing else pen_states.HOVER

            # 3. Combine: ink needs BOTH the sensor saying "down" and the camera seeing a
            #    hand inside the box. Either one alone draws nothing.
            show_cursor, ink = pen_states.combine(state, lm is not None, lm is not None and inside)
            if show_cursor:
                art.move(lx, ly, pen_down=ink)
            else:
                art.hide_cursor()
                state = pen_states.IDLE          # for the on-screen label

            # 4. Commands: only while the pen is up, and only after a deliberate hold.
            sign = None
            if lm is not None and not art.pen_down:
                if letters is not None:
                    sign = letter_filter.update(letters.predict(lm)[0])
                else:
                    sign = gesture
            fired = trigger.update(sign, now)
            if fired:
                result = art.apply(fired)
                note, note_until = (result or f"unknown action {fired}"), now + 1.5
            sign_text = f"{trigger.sign}: {actions[trigger.sign]}" if trigger.sign else ""

            # 5. Panel: send only the LEDs that changed.
            image = art.render(now)
            sender.show(image, now)

            if lm is not None:
                draw_hand(frame, lm)
            draw_overlay(frame, pointer, art, state, pen, link, trigger, sign_text,
                         note if now < note_until else "", fps, simulated)
            cv2.imshow("Camera", frame)
            if not args.no_board:
                board_view.show_image(image)

            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), 27):
                break
            elif key == ord("c"):
                art.clear()
            elif key == ord("s"):
                name = time.strftime("drawing_%Y%m%d_%H%M%S.png")
                cv2.imwrite(name, board_view.scale_up(art.canvas))
                print(f"Saved {name}")
            elif key in (ord("["), ord("]")):
                pointer.box.resize(0.9 if key == ord("[") else 1 / 0.9)
                print(f"Drawing box size is now {pointer.box.size:.2f}  (DRAW_BOX_SIZE in config.py)")
            elif key == ord("p") and pen.distance is not None:
                pen.down_cm = round(pen.distance + 1.0, 1)
                pen.idle_cm = max(pen.idle_cm, pen.down_cm + 3 * pen.margin_cm)
                print(f"Pen-down distance is now {pen.down_cm} cm  (PEN_DOWN_CM in config.py)")
            elif simulated and key in (ord("1"), ord("2"), ord("3")):
                link.sim_cm = {ord("1"): pen.down_cm / 2, ord("2"): (pen.down_cm + pen.idle_cm) / 2,
                               ord("3"): pen.idle_cm + 20}[key]
    finally:
        tracker.close()
        cap.release()
        link.close()
        cv2.destroyAllWindows()
    return 0


if __name__ == "__main__":
    sys.exit(main())
