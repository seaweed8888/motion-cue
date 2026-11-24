import json
from pathlib import Path
import sys
import pickle
import numpy as np
import pytest
from sklearn.ensemble import RandomForestClassifier
from training import train, evaluate, export_model, preprocess
from training.augment import augment


def test_training_evaluation_export_and_preprocess(tmp_path,monkeypatch):
    window=json.loads(Path("tests/fixtures/window.json").read_text())
    rng=np.random.default_rng(4)
    events=[]
    splits={"train":[],"validation":[],"test":[]}
    for split in splits:
        for user in ("one","two"):
            splits[split].append(f"{user}/{split}")
            for label in range(4):
                for repeat in range(3):
                    samples=augment(window,rng)
                    samples[:,1]+=label
                    events.append(dict(user_id=user,session_id=split,
                        recording_id=f"{user}-{split}-{label}-{repeat}",label=label,
                        synthetic=True,samples=samples.tolist()))
    events_path=tmp_path/"events.json"
    events_path.write_text(json.dumps(events))
    splits_path=tmp_path/"splits.json"
    splits_path.write_text(json.dumps(splits))
    model=tmp_path/"model.pkl"
    monkeypatch.setattr(sys,"argv",["train",str(events_path),str(splits_path),"--output",str(model),"--allow-synthetic"])
    train.main()
    monkeypatch.setattr(sys,"argv",["evaluate",str(model),str(events_path),"--output",str(tmp_path/"eval")])
    evaluate.main()
    assert json.loads((tmp_path/"eval/metrics.json").read_text())["synthetic"]
    assert (tmp_path/"eval/confusion_matrix.png").exists()
    monkeypatch.setattr(sys,"argv",["export",str(model),"--output",str(tmp_path/"gesture_model.h"),"--allow-synthetic"])
    export_model.main()
    assert "MOTIONCUE_MODEL_READY 1" in (tmp_path/"gesture_model.h").read_text()
    output=tmp_path/"segmented.json"
    monkeypatch.setattr(sys,"argv",["preprocess","data/sample/continuous.json","--output",str(output)])
    preprocess.main()
    assert len(json.loads(output.read_text()))==1


@pytest.mark.parametrize("model_synthetic", [False, True])
@pytest.mark.parametrize("data_synthetic", [False, True])
def test_evaluation_labels_synthetic_model_or_data(tmp_path, monkeypatch,
                                                 model_synthetic, data_synthetic):
    window = json.loads(Path("tests/fixtures/window.json").read_text())
    splits = {name: [f"one/{name}"] for name in ("train", "validation", "test")}
    events = [dict(user_id="one", session_id=name, recording_id=name, label=label,
                   samples=window, synthetic=data_synthetic and label == 1)
              for name in splits for label in range(4)]
    model = RandomForestClassifier(n_estimators=1, max_depth=1, random_state=1).fit(
        np.zeros((4, 55)), [0, 1, 2, 3])
    artifact = dict(model=model, feature_version=1, threshold=.75, splits=splits,
                    synthetic=model_synthetic)
    model_path, events_path = tmp_path/"model.pkl", tmp_path/"events.json"
    model_path.write_bytes(pickle.dumps(artifact))
    events_path.write_text(json.dumps(events))
    import matplotlib.pyplot as plt
    titles = []
    monkeypatch.setattr(plt, "savefig", lambda path: titles.append(plt.gca().get_title()))
    monkeypatch.setattr(sys, "argv", ["evaluate", str(model_path), str(events_path),
                                     "--output", str(tmp_path/"evaluation")])
    evaluate.main()
    metrics = json.loads((tmp_path/"evaluation/metrics.json").read_text())
    assert metrics["synthetic"] is (model_synthetic or data_synthetic)
    assert ("SYNTHETIC FIXTURE" in titles[0]) is (model_synthetic or data_synthetic)
