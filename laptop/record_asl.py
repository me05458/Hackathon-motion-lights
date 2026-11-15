"""Record ASL examples for training.   python record_asl.py R G B C REST  [--samples 200]

Record the letters you use as commands (see ASL_COMMANDS in config.py), plus one extra
label such as REST with your normal, relaxed drawing hand. REST has no command; it
teaches the model what "not a command" looks like, so it stops guessing letters while you draw.

For each letter: make the sign, press SPACE to start/pause recording, and move your hand
around a little while it records (closer, further, slight tilts). It moves to the next
letter when it has enough samples. Press n to skip a letter, q or Esc to quit.
Samples are appended to asl_data.csv, so you can record more later in several sessions.
"""
import argparse
import sys

import camera
import cv2

import asl
import config


def main():
    p = argparse.ArgumentParser(description="Record ASL letter examples")
    p.add_argument("letters", nargs="+", help="labels to record, e.g. R G B C REST")
    p.add_argument("--samples", type=int, default=200, help="samples per letter (default 200)")
    p.add_argument("--camera", type=int, default=config.CAMERA_INDEX)
    args = p.parse_args()
    letters = [l.upper() for l in args.letters]

    from tracker import HandTracker, draw_hand
    cap = camera.open_camera(args.camera)
    if cap is None:
        print(camera.camera_help(args.camera))
        return 1
    tracker = HandTracker()
    total = 0
    try:
        for letter in letters:
            rows, recording = [], False
            while len(rows) < args.samples:
                ok, frame = camera.read_frame(cap)
                if not ok:
                    asl.append_samples(rows)          # keep what was recorded so far
                    total += len(rows)
                    print("Camera stopped sending frames.\n" + camera.camera_help(args.camera))
                    return 1
                if config.MIRROR:                    # same as main.py, or left/right gets swapped
                    frame = cv2.flip(frame, 1)
                _, lm = tracker.process(frame)
                if lm is not None:
                    draw_hand(frame, lm)
                    if recording:
                        rows.append((letter, asl.raw_row(lm)))

                state = "RECORDING" if recording else "paused - SPACE to record"
                colour = (0, 0, 255) if recording else (0, 255, 255)
                cv2.putText(frame, f"Letter {letter}: {len(rows)}/{args.samples}", (10, 35),
                            cv2.FONT_HERSHEY_SIMPLEX, 1.0, colour, 2)
                cv2.putText(frame, state if lm is not None else "no hand seen", (10, 70),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, colour, 2)
                cv2.imshow("Record ASL", frame)

                key = cv2.waitKey(1) & 0xFF
                if key == ord(" "):
                    recording = not recording
                elif key == ord("n"):
                    break
                elif key in (ord("q"), 27):
                    asl.append_samples(rows)          # keep what was recorded so far
                    total += len(rows)
                    print(f"{letter}: saved {len(rows)} samples. Stopped.")
                    return 0
            asl.append_samples(rows)
            total += len(rows)
            print(f"{letter}: saved {len(rows)} samples")
    finally:
        tracker.close()
        cap.release()
        cv2.destroyAllWindows()
        print(f"{total} samples added to {config.ASL_DATA_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
