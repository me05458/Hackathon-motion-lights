import time
import cv2
import serial
import camera
import config
from tracker import HandTracker
from gestures import GestureFilter

PORT = "COM5"                      # change to your port

ser = serial.Serial(PORT, 115200, timeout=0)
time.sleep(2)                      

cap = camera.open_camera(0)
tracker = HandTracker()
filt = GestureFilter(config.STABLE_FRAMES)
last = None

while True:
    ok, frame = camera.read_frame(cap)
    if not ok:
        break
    raw, lm = tracker.process(frame)
    g = filt.update(raw)
    if g != last:
        if g == "OPEN":
            ser.write(b"DRAW=ON\n")     # open hand = start drawing
        elif g == "FIST":
            ser.write(b"DRAW=OFF\n")   
        elif g == "POINT":
            ser.write(b"COLOR=TOGGLE\n")    # point = change color
        last = g
    cv2.imshow("Hand", frame)
    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

tracker.close()
cap.release()
ser.close()
cv2.destroyAllWindows()