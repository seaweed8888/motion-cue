# MotionLink — Project Handoff

Updated: November 23, 2026. MotionLink is a working title, not a confirmed final name.

## Purpose and current status

Build a handheld ESP32-S3 gesture controller for presentations. The device detects movement, captures a complete motion event, classifies it locally, and communicates with a Windows application that injects ordinary keyboard events into the foreground application. A twist arms gesture control; left/right swipes navigate slides while armed.

This document records the agreed scope and recommended implementation. No firmware, trained model, dataset, or application has been implemented or verified in this handoff. Do not report proposed performance as achieved results.

## Confirmed user decisions

| Item | Decision |
|---|---|
| Host operating system | Windows |
| Microcontroller family | ESP32-S3; exact development board unknown |
| Motion sensor | Not selected or identified yet |
| Users | The user and their partner; both will collect training data |
| Activation | Twist enables gesture mode; support armed/disarmed operation |
| Motion segmentation | Automatic movement start, end after a quiet interval, and maximum recording duration |
| Classification | Random Forest trained on laptop, exported through emlearn, executed on ESP32 |
| Communication | MQTT between ESP32 and laptop application |
| Presentation control | Real Windows keystrokes, rather than controlling only a custom browser slideshow |
| Scope | Only the five core features listed below |

## Assumptions and unresolved hardware details

- **Twist toggle is an assumption:** the user explicitly requested twisting to turn gesture mode on and described armed/disarmed operation. Implement twist-to-arm and twist-again-to-disarm as the documented default. Do not present twist-to-disarm as explicitly confirmed. Keep this behavior configurable in code.
- Boot disarmed. Connection loss/restart returns the system to disarmed and clears pending actions.
- Initial mappings: swipe right → Right Arrow; swipe left → Left Arrow. Twist changes mode and sends no presentation keystroke.
- Implement editable mappings for the two swipe gestures and a dashboard arm/disarm control as part of the agreed core controls.
- A consistent marked holding orientation is the initial training assumption. Do not claim arbitrary-grip, either-hand, or new-user support without testing it.
- Recommend a six-axis accelerometer/gyroscope breakout such as the Adafruit LSM6DS3TR-C, but sensor selection is not a purchase decision. Identify the actual sensor before choosing drivers, register settings, or sample rates.
- Confirm the precise ESP32-S3 development board before assigning GPIOs, onboard LED behavior, flash layout, or a PlatformIO board identifier.
- Arduino C++ with PlatformIO is a proposed tooling default, not a confirmed user preference. Reuse an established course toolchain if appropriate.

Hardware-dependent work is blocked on the board/sensor details; message contracts, the Windows application, recording formats, and ML scripts can be developed independently using clearly labeled fixtures.

## Five required features

1. Automatic idle/movement detection and gesture segmentation.
2. Three recognizable gestures (left swipe, right swipe, twist), with rejection of ordinary or unknown movement.
3. One keystroke per accepted swipe gesture.
4. Keystroke mapping controls and armed/disarmed controls, including twist activation.
5. Connection status and gesture history in a simple web dashboard.

Training/collection tools and model evaluation are necessary implementation work. They do not imply a production correction/retraining interface.

Out of scope for the first version: correction-based retraining, online learning, wireless model updates, multiple user profiles, live sensor graphs, battery/enclosure development, cloud hosting, mobile apps, and custom PCBs. Use USB power initially. Local inference does not remove the need for a connected Windows host to control slides.

## System architecture

1. The IMU sends acceleration and angular velocity over I2C to the ESP32-S3.
2. The ESP32 samples at a regular hardware-supported rate and timestamps samples at acquisition.
3. A movement gate and segmenter extract complete motion events.
4. Firmware calculates features and runs the exported Random Forest.
5. The firmware updates armed/disarmed state and publishes accepted events/status over Wi-Fi and MQTT.
6. A broker runs on the laptop. The Windows application subscribes to events, checks mode/freshness/duplicates, and injects a mapped key press and release.
7. The same application serves a local web dashboard and streams status/history updates to it.

The ESP32 is one physical node; the laptop is the second. The broker, host application, and browser can all run on that laptop. Internet/cloud access is unnecessary for local operation once the LAN is established.

Run the keyboard-injection component as a native Windows desktop-user process. The course Linux environment may be used for training and infrastructure, but a browser page or Linux VM alone does not provide the required native Windows keyboard control.

## Firmware state model

Keep **control mode** separate from **motion state**. A stationary controller may remain armed.

| Control mode | Recognized twist | Recognized swipe | Unknown movement |
|---|---|---|---|
| Disarmed | Arm, publish new state, consume event | Ignore for keyboard control | Ignore |
| Armed | Disarm, publish new state, consume event | Publish one mapped-action event | Ignore |

**Disarmed must still monitor for twist.** Continue sampling and event-triggered classification while disarmed, but only a valid twist may change control mode. Do not turn off the IMU or all gesture detection when disarmed. This is distinct from classifying every stationary sample.

Motion states:

- `IDLE`: update the rolling pre-trigger buffer and movement estimate.
- `CAPTURING`: save samples after persistent motion onset; continue until quiet-time completion.
- `CLASSIFYING`: extract features once from the completed event; predict/reject; apply mode logic.
- `WAIT_FOR_IDLE`: suppress new commands until motion settles and the event cooldown ends.

Initial parameters to tune with recordings, not fixed requirements:

| Parameter | Starting point |
|---|---|
| Sampling | Around 100 Hz; choose the sensor's supported output rate and document actual rate |
| Pre-trigger history | About 150 ms |
| Motion-onset persistence | About 30–50 ms |
| Quiet interval to finish | About 200 ms |
| Maximum event duration | About 2 seconds; reject overlong events initially |
| Post-event cooldown | About 400–600 ms plus a return to idle |

Use calibrated, filtered acceleration/rotation features for motion detection. Do not threshold raw acceleration magnitude as if stationary readings were zero: gravity is present. Use hysteresis between onset and settling thresholds. Thresholds segment events; the Random Forest performs the meaningful gesture classification.

Consume the entire twist event when changing mode. Do not let its trailing movement immediately trigger a swipe or a second toggle. Require stable settling before another event. Both firmware and host must prevent duplicate actions.

## ML and data workflow

### Data collection

Record real gestures from both partners across separate sessions. Include variations in speed and modest grip/starting angle changes within the supported orientation. Collect ordinary movement: picking up, putting down, repositioning, returning after a swipe, and incomplete gestures.

Save continuous recordings or enough surrounding context to evaluate segmentation. Log timestamps, six IMU channels, units, sample rate, user ID, session ID, recording ID, and label/gesture boundaries. Keep timestamps from acquisition; network arrival time is not the sampling clock.

Suggested model labels:

| ID | Label | Meaning |
|---|---|---|
| 0 | `other` | Ordinary/unsupported movement; no command |
| 1 | `swipe_left` | Candidate previous-slide command |
| 2 | `swipe_right` | Candidate next-slide command |
| 3 | `twist` | Candidate mode toggle |

Idle is primarily a segmenter state; `other` must include real motion, not only stationary samples. A score-based rejection rule can reject uncertain predictions, but is not guaranteed detection of every unseen movement.

### Features and training

Train with scikit-learn on the laptop. Proposed initial forest: 20 trees, maximum depth 5; tune using validation results and actual device resource use.

Use acceleration and gyroscope features such as signed extrema, mean, variability, energy, event duration, and signed summaries from sequential parts of the gesture. Preserve temporal information: left/right swipes can have similar whole-event statistics with opposite acceleration order. Maintain the same feature definitions, order, units, filtering, segmentation, and numeric representation in Python and firmware.

Split by session before generating windows or augmentation. Keep each recording and all derivatives in the same split. Train on training sessions, tune with validation sessions, and evaluate final results on untouched sessions. Both partners should be represented appropriately for the intended two-user system.

Start with a baseline without augmentation. Then test modest sensor noise, context-preserving temporal shifts, and small consistent 3D coordinate rotations. Apply the same rotation to accelerometer and gyroscope triplets. Avoid axis flips, time reversal, or large rotations that change directional labels. Augment training data only; synthetic variants are not independent real recordings.

### Export and firmware integration

Use emlearn to export the selected forest to a generated header. Specify feature datatype explicitly; do not silently truncate physical-unit features to integers. Choose voting/probability settings intentionally and validate prediction scores as well as labels if rejection uses them.

Check exported predictions against Python on fixed held-out fixtures. Check Python/C++ feature parity from identical raw sample windows. Pin compatible library versions after verifying the export workflow. Measure flash, RAM, feature-processing time, and inference time on the actual board.

This deployed forest performs inference only. Retraining, model correction interfaces, and over-the-air updates are outside the first release.

## MQTT contract and connection behavior

Proposed topic prefix: `motionlink/<device_id>/`.

| Topic suffix | Publisher | Contents |
|---|---|---|
| `status` | ESP32 | Online state, armed state, model version, uptime, current session information |
| `events` | ESP32 | Accepted gestures, mode changes, or diagnostic rejection records |
| `control` | Windows host | Arm/disarm commands and connection-session handshake |
| `telemetry` | ESP32, collection/debug mode | Timestamped raw IMU batches for training/diagnostics |

Version message schemas. Include a boot identifier, event sequence, host control-session identifier, model version, gesture label, mode state, and local event time as appropriate. Motion events must not be retained. If delivery settings can duplicate messages, deduplicate on `(device_id, boot_id, event_id)` before injection.

Issue a fresh control-session identifier on host/device reconnect and reject events from old sessions. Do not replay buffered gesture commands after an outage. Use nonpersistent event sessions, bounded queues, and clear pending actions on disconnect. For stale-event detection, do not directly subtract ESP32 uptime from Windows wall time; use an explicit clock mapping or another tested freshness mechanism alongside the session handshake.

Firmware owns mode state. The dashboard shows the acknowledged device state, with a pending indicator while a control command is awaiting confirmation. Heartbeat/status timeout marks the device offline and disables host injection; loss of the active host connection disarms the device. A retained status message alone must not count as proof of a live connection.

## Windows keystroke behavior

The native Windows process receives an accepted swipe, checks the active session and armed state, maps it to an allowed key, and sends exactly one press/release. Proposed implementation: Python with a Windows-capable input library, with the exact dependency chosen and tested during implementation.

- Send input to the currently focused application; the user focuses the intended presentation before use.
- Browser and desktop slideshow support depends on that application's accepted shortcuts, focus, permissions, and configuration. Do not claim universal support without platform testing.
- Default to Right/Left Arrow. Permit a small allowlist of presentation keys such as arrows, Page Up/Page Down, and Space instead of arbitrary executable commands.
- Twist never sends `B` or another slide shortcut.
- Keep keyboard injection outside the browser. Dashboard focus must not be required during a presentation.
- Disarming or losing connection clears queued actions. A disarm event takes precedence over unprocessed navigation events.
- Bind the dashboard to localhost by default. Keep credentials out of the repository and use example config files.

## Minimal dashboard

Show device/host connection state, actual armed/disarmed state, last recognized gesture, recent gesture/action history, two swipe mappings, and arm/disarm controls. Indicate rejected or suppressed events separately from executed commands when shown in history. A local bounded history is sufficient; no production database or analytics platform is required.

## Repository layout

```text
MotionLink/
    README.md
    handoff.md
    LICENSE
    .gitignore
    firmware/
        README.md
        platformio.ini              # only after exact board/toolchain confirmed
        include/config.example.h
        include/gesture_model.h     # generated export
        src/main.cpp
        src/imu.cpp
        src/segmenter.cpp
        src/features.cpp
        src/classifier.cpp
        src/control_mode.cpp
        src/mqtt_client.cpp
    training/
        README.md
        requirements.txt
        collect.py
        preprocess.py
        augment.py
        features.py
        train.py
        evaluate.py
        export_model.py
        configs/random_forest.yaml
    monitoring/
        README.md
        requirements.txt
        app.py
        mqtt_listener.py
        keyboard_output.py
        event_router.py
        config.example.json
        web/index.html
        web/styles.css
        web/app.js
    shared/
        mqtt_protocol.md
        feature_spec.md
        labels.json
        examples/
    data/
        README.md
        sample/
        raw/                        # ignored unless deliberately published
        processed/                  # ignored generated data
    models/
        README.md
        releases/v001/
            metadata.json
            metrics.json
            confusion_matrix.png
    tests/
        test_feature_parity.py
        test_export_parity.py
        test_event_routing.py
        fixtures/
    docs/
        hardware.md
        architecture.svg
        wiring.svg
        experiments.md
        assets/
```

This is a proposed structure, not a list of existing files. Keep sample/debug data clearly labeled. Commit a small reproducible example; ignore credentials, virtual environments, build output, runtime logs, and large generated datasets.

## Implementation order

1. Identify the board and sensor; verify all six channels, units, sampling, and stationary calibration.
2. Establish MQTT communication and native Windows key injection using explicitly labeled manual test events.
3. Build the segmenter and dataset recorder; collect both users and ordinary movement across sessions.
4. Train/evaluate the baseline, export it, and verify parity and hardware resource usage.
5. Integrate the separate armed/disarmed and motion-state logic, twist toggle, rejection, and event cooldown.
6. Finish dashboard controls/history and validate deduplication, reconnect behavior, and real slideshow operation.
7. Record measured results, document iterations, and prepare course deliverables.

## Acceptance checks

- Boot stationary: disarmed and no key output.
- Swipe while disarmed: no presentation command.
- Twist from disarmed: arms exactly once; no keystroke.
- Swipe while armed: one correct press/release, including across repeated trials.
- Twist while armed: disarms once under the documented toggle assumption.
- Slow gestures, return movement, incidental motion, and unknown motion: assessed using labeled real trials; rejected when appropriate.
- Brief pauses and long movements: segmenter completes or times out predictably without repeated actions.
- Remap a swipe: subsequent accepted events use the new allowed key.
- Disconnect/reconnect or restart: offline/unknown is shown, system disarms, and old events do not execute.
- Duplicate MQTT event: at most one command is executed.
- Test at least one desktop slideshow and one browser slideshow on Windows, with the presentation focused. Document platforms/modes actually tested.
- Evaluate full pipeline with fresh sessions, rather than only pre-cut gesture clips.

Report per-class precision/recall and confusion matrix, false commands per minute of ordinary handling, missed gestures, false arm/disarm events, duplicate commands, and response latency. Separate motion duration, endpoint-detection delay, inference time, and host delivery/injection delay where measurable. Do not subtract unsynchronized timestamps to claim end-to-end latency.

## Course requirements and deliverables

Based on the supplied final-project PDF and EE250L Fall 2026 syllabus:

| Requirement | Project evidence |
|---|---|
| Two physical nodes | ESP32-S3 and separate Windows laptop |
| Data collection | Real six-axis IMU recordings |
| Nontrivial real-time processing/ML | Segmentation, feature extraction, trained forest, rejection, and state logic |
| Node-to-node communication | Wi-Fi/MQTT gesture events and control/status messages |
| Web visualization and/or control | Dashboard history, mode controls, mappings, and keyboard-driven slideshow |
| Originality/polish | Twist activation, local inference, measured rejection performance, reliable event handling |

The published submission deadline is December 7, 2026. The project PDF says demo timing is TBA; the syllabus tentatively places demonstrations during November 30–December 4. Verify current course announcements instead of assuming the demo deadline equals submission day.

Work as a pair with equal participation across the system. The syllabus expects pair programming and shared understanding, rather than dividing hardware and software into isolated assignments. Both partners must explain all design decisions.

Required deliverables: source code; team names, dependencies, and execution instructions; at most two-page write-up with a rendered, clearly labeled component/data-flow diagram, design choices, limitations, and lessons; publicly accessible narrated video of at most four minutes; teamwork assessment survey; in-person demo/interview. Provide `README.txt` plus a PDF copy because the project text and rubric use different README filenames; retain `README.md` for GitHub. Acknowledge AI assistance in code comments and write-up, including what assistance was used.

The demo/interview is 70/100 points, including 15 for originality/difficulty and 35 for other project questions. Code, write-up, and other deliverables are 10 points each. Prioritize a repeatable functioning demo, defensible evaluation, and both partners' understanding over extra features. No grade or employment outcome is guaranteed.

## References and next-agent instructions

Authoritative supplied documents: `Final Project_ End-to-End IoT System.pdf` and `EE250L_Fall2026_Syllabus.pdf`.

- emlearn: https://emlearn.readthedocs.io/en/latest/tree_based_models.html
- emlearn overview: https://emlearn.readthedocs.io/en/latest/source/README.html
- Random Forest training: https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.RandomForestClassifier.html
- Candidate sensor: https://www.adafruit.com/product/4503

The next implementer should preserve confirmed scope, label assumptions, inspect any existing repository before modifying it, and resolve exact board/sensor details before hardware configuration. Do not invent existing datasets, performance metrics, sensor identity, or completed features. Prefer an end-to-end vertical slice before adding complexity. Do not add the earlier correction/continuous-learning features unless the user expands scope.
