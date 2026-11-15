"""Train the ASL letter model.   python train_asl.py

Reads asl_data.csv, tests on 20% of the samples it didn't train on, prints the accuracy
per letter and which letters get mixed up, then trains on everything and saves asl_model.joblib.
It also lists which commands (ASL_COMMANDS in config.py) are ready to use.
"""
import argparse
import os
import sys
from collections import Counter

import asl
import config


def train(data_path=config.ASL_DATA_PATH, model_path=config.ASL_MODEL_PATH, quiet=False):
    """Returns the test accuracy (0..1). Raises ValueError if there isn't enough data."""
    from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
    from sklearn.model_selection import train_test_split

    say = (lambda *a: None) if quiet else print
    if not os.path.exists(data_path):
        raise ValueError(f"{data_path} not found. Record some letters with record_asl.py first.")
    X, y = asl.load_data(data_path)
    counts = Counter(y)
    say("Samples per letter:", ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))
    if len(counts) < 2:
        raise ValueError("Need at least 2 different letters to train.")
    if min(counts.values()) < 10:
        raise ValueError("Each letter needs at least 10 samples. Record more of: "
                         + ", ".join(k for k, v in counts.items() if v < 10))

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, stratify=y, random_state=0)
    model = asl.make_model()
    model.fit(X_train, y_train)
    pred = model.predict(X_test)
    acc = accuracy_score(y_test, pred)

    say(f"\nTest accuracy: {acc:.1%}  ({len(y_test)} samples it did not train on)\n")
    say(classification_report(y_test, pred, zero_division=0))
    labels = sorted(counts)
    cm = confusion_matrix(y_test, pred, labels=labels)
    mixups = [(cm[i][j], a, b) for i, a in enumerate(labels) for j, b in enumerate(labels)
              if i != j and cm[i][j]]
    if mixups:
        say("Most mixed up (real -> predicted):")
        for n, a, b in sorted(mixups, reverse=True)[:5]:
            say(f"  {a} -> {b}: {n} times. Record more of both.")

    model = asl.make_model()                       # final model uses all the data
    model.fit(X, y)
    asl.save_model(model, model_path, max_distance=asl.typical_max_distance(model, X))

    # In the drawing app letters are commands: say which ones are ready to use.
    commands = config.ASL_COMMANDS
    ready = [f"{k} = {commands[k]}" for k in labels if k in commands]
    say("\nCommands you can use now: " + (", ".join(ready) if ready else "none yet"))
    missing = [k for k in commands if k not in counts]
    if missing:
        say("Not trained yet (record them to use them): " + " ".join(missing))
    other = [k for k in labels if k not in commands]
    if other:
        say("Trained but with no command (fine, they do nothing): " + " ".join(other))
    say(f"\nSaved {model_path}")
    return acc


def main():
    p = argparse.ArgumentParser(description="Train the ASL letter model")
    p.add_argument("--data", default=config.ASL_DATA_PATH)
    p.add_argument("--model", default=config.ASL_MODEL_PATH)
    args = p.parse_args()
    try:
        train(args.data, args.model)
    except ValueError as e:
        print(e)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
