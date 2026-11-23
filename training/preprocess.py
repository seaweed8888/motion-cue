"""Segment continuous recordings before training. Parameters match firmware."""
import argparse
from collections import deque
import json
from pathlib import Path
import numpy as np
from .features import validate


def segment(samples):
    samples = validate(samples)
    baseline = samples[0, 1:4].copy()
    pre = deque()
    state, onset, quiet, started, ended = "idle", None, None, 0, 0
    window = []
    for row in samples:
        t = float(row[0])
        acceleration = np.linalg.norm(row[1:4]-baseline)
        rotation = np.linalg.norm(row[4:7])
        moving = acceleration > 1.2 or rotation > 0.7
        settled = acceleration < 0.6 and rotation < 0.35
        if state == "idle":
            baseline += np.float32(.02)*(row[1:4]-baseline)
            pre.append(row.copy())
            while pre and t-float(pre[0][0]) > .15:
                pre.popleft()
            onset = (t if onset is None else onset) if moving else None
            if onset is not None and t-onset >= .04:
                window, started, quiet, state = list(pre), t, None, "capturing"
        elif state == "capturing":
            window.append(row.copy())
            quiet = (t if quiet is None else quiet) if settled else None
            overlong = t-started >= 2.0 or len(window) >= 256
            if overlong or (quiet is not None and t-quiet >= .2):
                if not overlong:
                    yield np.asarray(window, dtype=np.float32)
                state, ended, quiet = "wait", t, None
        else:
            baseline += np.float32(.02)*(row[1:4]-baseline)
            quiet = (t if quiet is None else quiet) if settled else None
            if quiet is not None and t-quiet >= .2 and t-ended >= .5:
                state, onset, quiet = "idle", None, None
                pre.clear()


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
