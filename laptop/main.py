"""Gesture -> LED board. Run:  python main.py            (with ESP32 plugged in)
                               python main.py --no-serial (camera + on-screen board only)
Press q or Esc in either window to quit.
"""
import argparse
import sys

import cv2

import board_view
import config
import gestures
from link import NullLink, SerialLink


def parse_args():
    p = argparse.ArgumentParser(description="Hand gestures -> 32x32 LED board")
    p.add_argument("--no-serial", action="store_true", help="don't talk to the ESP32")
    p.add_argument("--port", help="serial port, e.g. COM5 (default: auto-detect)")
    p.add_argument("--camera", type=int, default=config.CAMERA_INDEX, help="camera index (default 0)")
    p.add_argument("--no-board", action="store_true", help="hide the on-screen LED board")
    p.add_argument("--asl", action="store_true",
                   help="also recognise ASL letters (train first: record_asl.py, train_asl.py)")
    return p.parse_args()


def main():
    args = parse_args()
    from tracker import HandTracker, draw_hand   # imported here so --help works without MediaPipe

    letters = letter_filter = None
    if args.asl:
        import asl
        try:
            letters = asl.ASLClassifier()
        except (FileNotFoundError, RuntimeError) as e:
            print(e)
            return 1
        letter_filter = gestures.GestureFilter(config.STABLE_FRAMES)

    if args.no_serial:
        link = NullLink()
    else:
        try:
            link = SerialLink(port=args.port)
            print(f"Connected to ESP32 on {link.port}")
        except Exception as e:
            print(f"Serial error: {e}")
            print("Tip: close the Arduino Serial Monitor (only one program can use the port), "
                  "or run with --no-serial.")
            return 1

    cap = cv2.VideoCapture(args.camera)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.CAMERA_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.CAMERA_HEIGHT)
    if not cap.isOpened():
        print(f"Could not open camera {args.camera}. Try another number, e.g. --camera "
              f"{0 if args.camera else 1}.")
        link.close()
        return 1

    tracker = HandTracker()
    filt = gestures.GestureFilter(config.STABLE_FRAMES, config.SMOOTHING)
    lx, ly = config.PANEL_W // 2, config.PANEL_H // 2
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                print("Camera stopped sending frames.")
                break
            if config.MIRROR:
                frame = cv2.flip(frame, 1)

            raw, x, y, lm = tracker.process(frame)
            gesture = filt.update(raw, x, y)
            if filt.x is not None:
                lx, ly = gestures.to_led(filt.x, filt.y, config.PANEL_W, config.PANEL_H)

            link.poll()
            link.send(gesture, lx, ly)

            if lm is not None:
                draw_hand(frame, lm)
            dist = f"{link.distance_cm:.0f} cm" if link.distance_cm > 0 else "-"
            cv2.putText(frame, f"{gesture}  ({lx},{ly})  dist {dist}", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
            if letters is not None:
                letter, conf = letters.predict(lm) if lm is not None else ("-", 0.0)
                shown = letter_filter.update(letter)
                cv2.putText(frame, shown, (frame.shape[1] - 110, 110),
                            cv2.FONT_HERSHEY_SIMPLEX, 3.5, (255, 255, 0), 6)
                cv2.putText(frame, f"ASL {letter} {conf:.0%}", (10, 65),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
            cv2.imshow("Camera", frame)
            if not args.no_board:
                board_view.show(gesture, lx, ly, link.distance_cm)

            if cv2.waitKey(1) & 0xFF in (ord("q"), 27):
                break
    finally:
        tracker.close()
        cap.release()
        link.close()
        cv2.destroyAllWindows()
    return 0


if __name__ == "__main__":
    sys.exit(main())
