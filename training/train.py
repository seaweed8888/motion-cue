import argparse
import json
from pathlib import Path
import pickle
import numpy as np
from sklearn.ensemble import RandomForestClassifier
import yaml
from .features import extract, FEATURE_VERSION
from .augment import augment


def split_events(events, splits):
    sets = {k: set(splits[k]) for k in ("train", "validation", "test")}
    if any(not group for group in sets.values()):
        raise ValueError("Each split requires sessions")
    if any(sets[a] & sets[b] for a,b in (("train","validation"),("train","test"),("validation","test"))):
        raise ValueError("Session leakage across splits")
    result = {k: [] for k in sets}
    recordings = {}
    for event in events:
        session = f"{event['user_id']}/{event['session_id']}"
        recording = event["recording_id"]
        if recording in recordings and recordings[recording] != session:
            raise ValueError("recording_id must be globally unique")
        recordings[recording] = session
        target = [k for k,v in sets.items() if session in v]
        if len(target) != 1:
            raise ValueError(f"Unassigned session: {session}")
        result[target[0]].append(event)
    for name, rows in result.items():
        if set(e["label"] for e in rows) != set(range(4)):
            raise ValueError(f"{name} needs all four classes")
    users = {e["user_id"] for e in events}
    if any({e["user_id"] for e in rows} != users for rows in result.values()):
        raise ValueError("Every split must include each user")
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("events")
    parser.add_argument("splits")
    parser.add_argument("--output", required=True)
    parser.add_argument("--config", default="training/configs/random_forest.yaml")
    parser.add_argument("--augment", action="store_true")
    parser.add_argument("--allow-synthetic", action="store_true")
    args = parser.parse_args()
    events = json.loads(Path(args.events).read_text())
    if any(e.get("synthetic") for e in events) and not args.allow_synthetic:
        raise ValueError("Synthetic fixtures require --allow-synthetic; not measured performance")
    split = split_events(events, json.loads(Path(args.splits).read_text()))
    config = yaml.safe_load(Path(args.config).read_text())
    threshold = config.pop("rejection_threshold")
    if not 0 <= threshold <= 1:
        raise ValueError("Rejection threshold must be between 0 and 1")
    train = split["train"]
    x, y = [extract(e["samples"]) for e in train], [e["label"] for e in train]
    if args.augment:
        rng = np.random.default_rng(250)
        x += [extract(augment(e["samples"], rng)) for e in train]
        y += [e["label"] for e in train]
    model = RandomForestClassifier(**config).fit(x, y)
    artifact = dict(model=model, feature_version=FEATURE_VERSION, threshold=threshold,
                    synthetic=any(e.get("synthetic") for e in events),
                    splits=json.loads(Path(args.splits).read_text()))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(pickle.dumps(artifact))
    print(f"Trained on {len(train)} real-or-fixture events; validation/test held out")


if __name__ == "__main__":
    main()
