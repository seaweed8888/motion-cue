import json
from pathlib import Path
import sys
import numpy as np
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
