import argparse
import json
from pathlib import Path
import pickle
import emlearn
from .features import FEATURE_VERSION, FEATURE_COUNT


def export(artifact, output):
    if artifact["feature_version"] != FEATURE_VERSION:
        raise ValueError("Feature version mismatch")
    if list(artifact["model"].classes_) != [0,1,2,3]:
        raise ValueError("Expected class IDs 0,1,2,3")
    model = emlearn.convert(artifact["model"], method="inline", dtype="float", leaf_bits=8)
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    model.save(file=str(output), name="gesture_model")
    with output.open("a") as f:
        f.write(f'\n#define MOTIONCUE_MODEL_READY 1\n#define MOTIONCUE_THRESHOLD {float(artifact["threshold"])}f\n')
    output.with_suffix(".json").write_text(json.dumps(dict(feature_version=FEATURE_VERSION,
        feature_count=FEATURE_COUNT, synthetic=artifact["synthetic"], leaf_bits=8, dtype="float",
        threshold=artifact["threshold"]), indent=2))
    return model


def main():
    p = argparse.ArgumentParser(description="Load only trusted local pickle models")
    p.add_argument("model")
    p.add_argument("--output", required=True)
    p.add_argument("--allow-synthetic", action="store_true")
    args = p.parse_args()
    artifact = pickle.loads(Path(args.model).read_bytes())
    if artifact["synthetic"] and not args.allow_synthetic:
        raise ValueError("Refusing fixture model deployment without --allow-synthetic")
    export(artifact, args.output)


if __name__ == "__main__":
    main()
