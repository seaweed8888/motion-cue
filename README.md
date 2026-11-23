# MotionLink (working title)

ESP32-S3 gesture controller for Windows presentations. Twist arms/disarms;
swipes send mapped presentation keys. Project files follow [handoff.md](handoff.md).

Implemented: native Windows host, local dashboard, MQTT session/lease validation,
manual device simulator, recording/training/export tools, portable C++ segmentation,
features and mode logic. **Not hardware-ready:** exact board and IMU are unknown;
sensor driver, board loop and Wi-Fi/MQTT transport integration remain pending.
The ESP-IDF/EIM firmware project can build a disarmed boot scaffold; see
[firmware build and flash instructions](firmware/README.md).
No real dataset, trained release model, or measured gesture accuracy exists yet.

## Run the Windows host

Use Python 3.13 (tested), a local MQTT broker, and a native desktop-user terminal.

```powershell
python -m venv .venv
.venv/Scripts/python -m pip install -r monitoring/requirements.txt
.venv/Scripts/python -m monitoring.app
```

Open http://127.0.0.1:8765. Default is **dry-run**, with no injected keys.
Start a local Mosquitto broker separately (`mosquitto -v` for localhost testing).
To use the physical device later, configure an authenticated LAN listener and
per-device topic ACLs; see [monitoring/README.md](monitoring/README.md).

In another terminal, exercise the complete MQTT/dashboard path:

```powershell
.venv/Scripts/python shared/examples/simulate.py
```

Type `twist`, then `swipe_right`, then `swipe_left`. This is explicitly a manual
fixture, not sensor recognition. For real key output restart the host with
`--enable-keyboard`, focus a test presentation, and use the controller.
Mappings are session-local and reset when the host restarts.

## Develop and verify

```powershell
.venv/Scripts/python -m pip install -r training/requirements.txt -r tests/requirements.txt
.venv/Scripts/python -m pytest -q
```

C++ parity tests require a C++17 compiler. On Windows use an x64 Visual Studio
Developer Command Prompt with `set DISTUTILS_USE_SDK=1` if compiler auto-discovery
fails. Tests compile and execute native C++ feature/segmentation/export checks.

See [training](training/README.md), [firmware](firmware/README.md),
[protocol](shared/mqtt_protocol.md), and [hardware decisions](docs/hardware.md).

## Remaining project work

1. Confirm board, IMU and twist-toggle behavior. Firmware now uses ESP-IDF via EIM.
2. Integrate and calibrate hardware; verify acquisition timing and six SI channels.
3. Collect both partners across independent sessions, including ordinary handling.
4. Train, validate and test; deploy the exported model only after parity checks.
5. Measure device RAM/flash/latency and trial desktop/browser presentations.
6. Complete the course report, narrated video, team names and teamwork assessment.

AI assistance was used for the initial implementation, tests and documentation.
Team members must review and understand it. No open-source license has been
chosen; see LICENSE. Course timing in the handoff has not been independently verified.
