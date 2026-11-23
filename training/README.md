# Recording and ML

Install training/requirements.txt. Run modules from the repository root.

Export settings follow the [emlearn tree documentation](https://emlearn.readthedocs.io/en/latest/tree_based_models.html).

```powershell
python -m training.collect --user partner1 --session day1 --output data/raw/day1.json
python -m training.preprocess data/raw/day1.json --output data/processed/events.json
python -m training.train data/processed/events.json data/splits.json --output models/baseline.pkl
python -m training.evaluate models/baseline.pkl data/processed/events.json --split validation --output models/validation
python -m training.evaluate models/baseline.pkl data/processed/events.json --split test --output models/releases/v001
python -m training.export_model models/baseline.pkl --output firmware/include/gesture_model.h
```

Supply all recordings to preprocess, not only the example day1 file. Capture
records continuous calibrated six-channel samples. Add `boundaries` entries
`{"start":1.0,"end":1.4,"label":3}` in acquisition seconds before preprocessing.
Unannotated segments become class 0 (other). Review segment boundaries and
missed gestures; automatic segmentation is not a substitute for annotations.

The split JSON assigns complete sessions, e.g.
`{"train":["partner1/day1","partner2/day1"],"validation":["partner1/day2","partner2/day2"],"test":["partner1/day3","partner2/day3"]}`.
Use globally unique recording IDs. Every split needs all four labels and both
users. Choose splits before augmentation; `--augment` affects training only.
No augmentation is the baseline. Tune rejection threshold on validation only.
Run untouched test evaluation once the model and threshold are fixed.

Labels are in shared/labels.json. Forest begins at 20 trees/depth 5. emlearn
uses float features and soft voting with 8-bit leaves; native tests verify scores
and clear-winner labels. Near ties/rejection boundaries require real-data checks.
Pickle artifacts must come from trusted local training, never untrusted downloads.

data/sample contains synthetic pipeline fixtures only. Training/export refuse
synthetic data unless `--allow-synthetic` is explicit. Do not deploy such models
or report their scores as gesture accuracy. Add full continuous-stream metrics
(false commands/minute, misses, mode errors and latency) from physical trials.
