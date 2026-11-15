import time
import cv2
import serial
import camera
import config
import asl
import train_asl

from tracker import HandTracker
from gestures import GestureFilter

PORT = "COM5"                      

ser = serial.Serial(PORT, 115200, timeout=0)
time.sleep(2)                      

cap = camera.open_camera(1)
tracker = HandTracker()
filt = GestureFilter(config.STABLE_FRAMES)
letter_filt = GestureFilter(config.STABLE_FRAMES)
last = None
last_color = None

#train
train_asl.train(data_path="asl.csv", model_path="aslmodel.joblib")
asl_model = asl.ASLClassifier(path="aslmodel.joblib")


while True:
    
    ok, frame = camera.read_frame(cap)
    if not ok:
        break
    raw, lm = tracker.process(frame)
    g = filt.update(raw)


    
    if g != last:
        if g == "OPEN":
            ser.write(b"DRAW=ON\n")     # open hand = start drawing
        elif g == "POINT":
            ser.write(b"COLOR=TOGGLE\n")    # point = change color
        last = g


    if lm is not None and g not in ("OPEN", "FIST"):
        detected_letter, _ = asl_model.predict(lm)    
        if detected_letter != "?":
            letter = letter_filt.update(detected_letter)
            if letter in ("R", "G", "B", "W", "V", "L", "E", "Y", "V") and letter != last_color: 
                ser.write(f"COLOR={letter}\n".encode()) # into bytes i guess
                last_color = letter


    
    cv2.imshow("Hand", frame)
    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

tracker.close()
cap.release()
ser.close()
cv2.destroyAllWindows()
