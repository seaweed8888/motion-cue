# Motion Cue

ESP32-S3 gesture controller for Windows presentations. Twist arms/disarms;
swipes send mapped presentation keys. See the [documentation index](docs/README.md)
for guides, specifications and project history.

Implemented: native Windows host, local dashboard, MQTT session/lease validation,
manual device simulator, recording/training/export tools, portable C++ segmentation,
features and mode logic. **Not hardware-ready:** exact board and IMU are unknown;
sensor driver, board loop and Wi-Fi/MQTT transport integration remain pending.
The ESP-IDF/EIM firmware project can build a disarmed boot scaffold; see
[firmware build and flash instructions](firmware/README.md).
No real dataset, trained release model, or measured gesture accuracy exists yet.

## Run the Windows host

Use Python 3.13 (tested) and a native desktop-user terminal.

```powershell
python -m venv .venv
.venv/Scripts/python -m pip install -r monitoring/requirements.txt
.venv/Scripts/python monitoring/dashboard.py
```

The native Qt studio opens maximized with the normal Windows title bar and
window controls, with a tilt ball, local model testing,
labeled recording and device health. It **never injects keys**. Esc leaves
fullscreen; F11 toggles it. Load trusted `.pkl` models from `models/`. You can
also run `python -m monitoring.dashboard`, or launch
`dashboard.py` directly from the `monitoring` folder. The example config is found
relative to the script; use `--config monitoring/config.json` for a custom config.
The browser dashboard remains available through `python -m monitoring.app`
at http://127.0.0.1:8765.
The native dashboard starts its bundled local MQTT broker automatically when
the configured loopback address/port is unused, or reuses an existing broker.
Closing the dashboard stops only the broker it started. The separate browser
dashboard still needs a running broker (for example, `mosquitto -v`).
To use the physical device later, configure an authenticated LAN listener and
per-device topic ACLs; see [monitoring/README.md](monitoring/README.md).

In another terminal, exercise the complete MQTT/dashboard path:

```powershell
.venv/Scripts/python shared/examples/simulate.py
```

Type `twist`, then `swipe_right`, then `swipe_left`. This is explicitly a manual
fixture, not sensor recognition, and does not publish raw telemetry for the tilt
display or local inference. For real key output, use the separate browser host
`python -m monitoring.app --enable-keyboard`, focus a test presentation, and use
the controller. Run only one host at a time.
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
[protocol](docs/reference/mqtt-protocol.md), and
[hardware decisions](docs/reference/hardware.md).

## Repository organization

Application and firmware code live in `monitoring/`, `training/`, `firmware/`
and `shared/`; automated checks live in `tests/`. Data and model artifacts belong
in `data/` and `models/`. Each component keeps its own usage `README.md`.

Cross-project documentation belongs under [docs/](docs/README.md): specifications
in `reference/`, measurements and reviews in `reports/`, and historical plans
in `archive/`. Root `PRODUCT.md` and `DESIGN.md` are the product/design context
used by Impeccable. [AGENTS.md](AGENTS.md) records placement and maintenance rules
for future agents.

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
