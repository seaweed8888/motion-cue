import argparse
import json
from pathlib import Path
import pickle
import numpy as np
from sklearn.metrics import classification_report, confusion_matrix, ConfusionMatrixDisplay
from .features import extract
from .train import split_events


def main():
    parser = argparse.ArgumentParser(description="Load only trusted local pickle models")
    parser.add_argument("model")
    parser.add_argument("events")
    parser.add_argument("--split", choices=["validation", "test"], default="validation")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    artifact = pickle.loads(Path(args.model).read_bytes())
    rows = split_events(json.loads(Path(args.events).read_text()), artifact["splits"])[args.split]
    synthetic = artifact["synthetic"] or any(e.get("synthetic", False) for e in rows)
    scores = artifact["model"].predict_proba([extract(e["samples"]) for e in rows])
    prediction = np.argmax(scores, axis=1)
    prediction[np.max(scores, axis=1) < artifact["threshold"]] = 0
    truth = [e["label"] for e in rows]
    metrics = dict(split=args.split, synthetic=synthetic,
                   report=classification_report(truth, prediction, labels=list(range(4)), output_dict=True, zero_division=0),
                   confusion_matrix=confusion_matrix(truth, prediction, labels=list(range(4))).tolist(),
                   full_pipeline_metrics="Not measured: requires continuous real handling trials")
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    (output/"metrics.json").write_text(json.dumps(metrics, indent=2))
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    ConfusionMatrixDisplay.from_predictions(truth, prediction, labels=list(range(4)))
    plt.title(f"{'SYNTHETIC FIXTURE · ' if synthetic else ''}{args.split}")
    plt.savefig(output/"confusion_matrix.png")
    plt.close()


if __name__ == "__main__":
    main()
