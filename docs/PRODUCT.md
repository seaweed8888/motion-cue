# Motion Cue

<!-- impeccable:product-schema 1 -->

## Platform

Native Windows desktop, built with Python and PySide6 / Qt Widgets. The studio
is a standalone window, not a browser app. A separate local browser host exists
for presentation keyboard output.

## Users

The user and their partner are developing and evaluating an ESP32-S3 handheld
presentation controller. Both collect labeled sensor data across separate
sessions and test gesture models on a Windows laptop.

## Product Purpose

Make it possible to inspect live IMU movement, test trained gesture models,
collect labeled recordings, adjust inference thresholds, and diagnose device
health. The controller's presentation gestures are left swipe, right swipe,
and twist, with an other/unknown movement class. Twist controls armed mode;
accepted swipes navigate presentations through mapped Windows keys.

The studio supports development and evaluation. Presentation keyboard output
stays separate so live testing does not advance slides or send accidental keys.

## Operating Context

- Run the native studio with `python monitoring/dashboard.py`. Start maximized
  with normal minimize/maximize/close controls; Esc leaves optional fullscreen
  and F11 toggles it.
- Receive calibrated six-channel IMU samples through a local MQTT broker.
- Load trusted local `.pkl` training artifacts from `models/` and run inference
  on the laptop. Remember the selected model and inference thresholds.
- Enter a user/session, choose a gesture label, record a take, then stop and
  save or discard it. Save training-compatible JSON under `data/raw/`.
- The CLI collector also supports V to start, C to stop, S to save, X to
  discard, and Q to quit, with live raw-sample counts.
- Keep recordings from the same user/session together in training splits.
  Use the existing CLI tools for preprocessing, training, evaluation and export.

## Capabilities and Constraints

- The studio never injects keyboard input. The separate browser host can
  explicitly enable Windows presentation-key output. Run only one host at a time.
- The center shows a tilt-driven ball, with Idle or the inferred gesture above
  it. Tilt is roll/pitch, not an estimate of physical position.
- The left controls model selection, laptop inference thresholds and labeled
  recording. The right shows connection, sampling and model health.
- Fine tuning covers collection/labeling and confidence/movement thresholds.
  Studio changes do not rewrite model artifacts or device firmware.
- Health includes broker/device connection, telemetry freshness, actual and
  expected sample rates, data-gap warnings, armed state and recent predictions.
- Empty or invalid recordings cannot be saved; unsaved takes require an
  explicit save/discard decision before closing. Existing files are preserved.
- The board and IMU still need identification. Sensor acquisition, calibration
  and hardware MQTT telemetry publishing remain pending in the firmware scaffold.

## Brand Commitments

The product name is Motion Cue. The user's binding references are PowerPoint
for color and Apple for minimal interface language: mostly white, with restrained
pops of color. The user supplied and confirmed the three-column dashboard sketch.
No logo, invented app mark or in-app header. Keep the existing three-column
layout and visually light controls. Apply gray when off and orange when on:
the ball and inspector activate with fresh telemetry, recognized gestures are
orange, and idle/disconnected states are gray. The ball has a short movement
trail. Avoid filler
copy and empty ready messages. Preserve real status, counts, errors and save feedback.
The user requested a bolder colorized left control panel and a mostly symmetric,
controller-like arrangement around the central tilt display.
For the white surfaces, the user also requested Apple and Google inspiration:
clear tonal layering and an elevated finish, while preserving the orange palette.

## Evidence on Hand

- `monitoring/dashboard.py`, `monitoring/live.py`: native studio and live processing.
- `training/`: collection, segmentation, feature extraction, training and export.
- `tests/`: automated software checks, including Python/C++ comparisons.
- `data/sample/` and test fixtures: synthetic demonstrations only.
- No real dataset, trained release model or measured gesture accuracy exists yet.
  Hardware behavior and presentation compatibility must not be claimed as verified.

## Product Principles

- Keep model experimentation separate from presentation-key output.
- Show real device/model state; distinguish missing readings and synthetic fixtures.
- Preserve recordings, labels and session boundaries throughout the training flow.
- Keep the primary jobs accessible: inspect movement, test a model, collect a take.
