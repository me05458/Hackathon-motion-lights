"""ASL letter recognition from the 21 hand landmarks.

Workflow:
  1. python record_asl.py A B L Y     record examples (appends to asl_data.csv)
  2. python train_asl.py              train, print accuracy, save asl_model.joblib
  3. python main.py --no-serial --asl show the recognised letter live

features() is used for both training and live recognition, so they always match.
"""
import csv
import math
import os

import numpy as np

import config

N_POINTS = 21
FEATURE_VERSION = 1          # bump if features() changes; old models then refuse to load


def raw_row(lm):
    """21 landmarks -> 42 numbers (x0, y0, x1, y1, ...). This is what record_asl.py saves,
    so the normalisation can change later without re-recording."""
    return [v for p in lm for v in (p.x, p.y)]


def features(raw):
    """42 raw numbers -> 42 normalised numbers: wrist at (0, 0), and scaled so the
    wrist-to-middle-knuckle distance is 1. Hand position and camera distance drop out."""
    pts = np.asarray(raw, dtype=np.float64).reshape(N_POINTS, 2)
    pts = pts - pts[0]                               # landmark 0 = wrist
    size = math.hypot(*pts[9]) or 1.0                # landmark 9 = middle knuckle
    return (pts / size).ravel()


def load_data(path=config.ASL_DATA_PATH):
    """Returns (X features, y labels) from the recorded CSV."""
    X, y = [], []
    with open(path, newline="") as f:
        for row in csv.reader(f):
            if len(row) != 1 + 2 * N_POINTS:
                continue                             # header or a damaged line
            try:
                X.append(features([float(v) for v in row[1:]]))
            except ValueError:
                continue
            y.append(row[0])
    return np.array(X), np.array(y)


def append_samples(rows, path=config.ASL_DATA_PATH):
    """rows: list of (label, raw_row). Appends to the CSV."""
    with open(path, "a", newline="") as f:
        w = csv.writer(f)
        for label, raw in rows:
            w.writerow([label] + [f"{v:.5f}" for v in raw])


def make_model():
    from sklearn.neighbors import KNeighborsClassifier
    return KNeighborsClassifier(n_neighbors=5, weights="distance")


def save_model(model, path=config.ASL_MODEL_PATH):
    import joblib
    joblib.dump({"model": model, "feature_version": FEATURE_VERSION}, path)


class ASLClassifier:
    def __init__(self, path=config.ASL_MODEL_PATH, min_confidence=config.ASL_MIN_CONFIDENCE):
        import joblib
        if not os.path.exists(path):
            raise FileNotFoundError(
                f"{path} not found. Run record_asl.py, then train_asl.py, first.")
        saved = joblib.load(path)
        if saved.get("feature_version") != FEATURE_VERSION:
            raise RuntimeError(f"{path} was trained with older features. Run train_asl.py again.")
        self.model = saved["model"]
        self.min_confidence = min_confidence

    def predict(self, lm):
        """Returns (letter, confidence 0..1). letter is "?" if the model isn't sure."""
        probs = self.model.predict_proba([features(raw_row(lm))])[0]
        i = int(np.argmax(probs))
        conf = float(probs[i])
        letter = str(self.model.classes_[i])
        return (letter if conf >= self.min_confidence else "?"), conf
