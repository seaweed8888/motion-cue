"""Segment continuous recordings before training. Parameters match firmware."""
import argparse
from collections import deque
import json
from pathlib import Path
import numpy as np
from .features import validate


class Segmenter:
    def __init__(self, acceleration_onset=1.2, rotation_onset=.7):
        self.acceleration_onset, self.rotation_onset = acceleration_onset, rotation_onset
        self.baseline = None
        self.pre = deque(maxlen=32)
        self.state, self.onset, self.quiet = "idle", None, None
        self.started = self.ended = 0
        self.window = []

    def push(self, row):
        if self.baseline is None:
            self.baseline = row[1:4].copy()
        t = float(row[0])
        acceleration = np.linalg.norm(row[1:4]-self.baseline)
        rotation = np.linalg.norm(row[4:7])
        moving = acceleration > self.acceleration_onset or rotation > self.rotation_onset
        settled = acceleration < 0.6 and rotation < 0.35
        if self.state == "idle":
            self.baseline += np.float32(.02)*(row[1:4]-self.baseline)
            self.pre.append(row.copy())
            while self.pre and t-float(self.pre[0][0]) > .15:
                self.pre.popleft()
            self.onset = (t if self.onset is None else self.onset) if moving else None
            if self.onset is not None and t-self.onset >= .04:
                self.window, self.started, self.quiet, self.state = list(self.pre), t, None, "capturing"
        elif self.state == "capturing":
            self.window.append(row.copy())
            self.quiet = (t if self.quiet is None else self.quiet) if settled else None
            overlong = t-self.started >= 2.0 or len(self.window) >= 256
            if overlong or (self.quiet is not None and t-self.quiet >= .2):
                self.state, self.ended, self.quiet = "wait", t, None
                if not overlong:
                    return np.asarray(self.window, dtype=np.float32)
        else:
            self.baseline += np.float32(.02)*(row[1:4]-self.baseline)
            self.quiet = (t if self.quiet is None else self.quiet) if settled else None
            if self.quiet is not None and t-self.quiet >= .2 and t-self.ended >= .5:
                self.state, self.onset, self.quiet = "idle", None, None
                self.pre.clear()


def segment(samples):
    segmenter = Segmenter()
    for row in validate(samples):
        window = segmenter.push(row)
        if window is not None:
            yield window


def load_recording(path):
    doc = json.loads(Path(path).read_text())
    required = ("user_id", "session_id", "recording_id", "sample_rate_hz", "units", "samples", "boundaries")
    if any(k not in doc for k in required):
        raise ValueError(f"Missing recording metadata: {path}")
    if doc["units"] != {"acceleration": "m/s2", "gyroscope": "rad/s", "time": "s"}:
        raise ValueError("Unsupported units")
    validate(doc["samples"])
    if not 0 < doc["sample_rate_hz"] <= 1000:
        raise ValueError("Invalid sample rate")
    if np.max(np.diff(np.asarray(doc["samples"])[:,0])) > 2.5/doc["sample_rate_hz"]:
        raise ValueError("Acquisition gap; repair or split the recording before segmentation")
    for b in doc["boundaries"]:
        if b["label"] not in range(4) or not b["start"] < b["end"]:
            raise ValueError("Invalid annotation boundary")
    return doc


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("recordings", nargs="+")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    events = []
    for path in args.recordings:
        doc = load_recording(path)
        for window in segment(doc["samples"]):
            matches = [b for b in doc["boundaries"] if b["start"] < window[-1,0] and b["end"] > window[0,0]]
            if len(matches) > 1:
                raise ValueError("Segment overlaps multiple labels; inspect segmentation")
            events.append({**{k: doc[k] for k in ("user_id", "session_id", "recording_id")},
                           "synthetic": doc.get("synthetic", False),
                           "label": matches[0]["label"] if matches else 0,
                           "samples": window.tolist()})
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(events))
    print(f"Wrote {len(events)} segmented events")


if __name__ == "__main__":
    main()
