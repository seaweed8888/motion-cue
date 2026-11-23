# Experiment log

Initial implementation: AI-assisted host, portable firmware core and ML tools.
Synthetic software checks are separate from hardware/model evaluation.

Software verification on Windows, 2026-11-23: native C++ feature parity,
emlearn float-feature/soft-vote score parity, segmentation/mode assertions,
host routing and actual local MQTT integration passed. Browser dashboard loaded;
mapping edits reached the host, with no horizontal overflow at 1060 px.
Keyboard output stayed in dry-run during these checks.

Pending measured trials:

| Trial | Result |
|---|---|
| Both partners, fresh sessions, all gesture classes | Not measured |
| Ordinary handling false commands per minute | Not measured |
| False arm/disarm, missed and duplicate gestures | Not measured |
| Endpoint delay, inference time and host delay | Not measured |
| RAM/flash, sampling timing and calibration | Not measured |
| Desktop slideshow and browser slideshow on Windows | Not tested |

For each run record date, users, session IDs, firmware/model versions, threshold,
grip orientation, platform and full pipeline counts. Do not subtract unsynchronized
device/host clocks for latency. Use local durations or an external synchronized
measurement. Compare baseline against augmentation on validation sessions only.
