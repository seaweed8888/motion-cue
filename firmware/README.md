# ESP32-S3 firmware — ESP-IDF / EIM

The firmware is a native ESP-IDF CMake project, with an optional GNU Make wrapper.
EIM manages the SDK and opens an activated terminal; build/flash commands run
in that terminal. No Arduino or PlatformIO installation is needed.

```text
firmware/
  CMakeLists.txt          ESP-IDF project, target esp32s3
  Makefile                Optional build/flash/monitor shortcuts
  sdkconfig.defaults      C++ exception support for feature validation
  include/                Configuration, model, and core interfaces
  src/
    CMakeLists.txt        Registers the firmware component
    app_main.cpp          ESP-IDF boot entry point
    main.cpp              Portable gesture processing
    ...                   IMU, segmentation, features, mode, and session logic
  build/                  Generated binaries and flash arguments (ignored)
```

## Build and flash from EIM

1. Open EIM → **Manage Installations** → **Open Dashboard**.
2. Select an installed ESP-IDF version → **Open IDF Terminal**.
3. Connect the ESP32-S3 over USB and identify its serial port in Device Manager.
4. Run these commands, replacing `COM5` with that port:

```powershell
cd C:\Repos\motion-cue\firmware
idf.py build
idf.py -p COM5 flash monitor
```

Exit the monitor with Ctrl+]. ESP-IDF handles binary offsets and bootloader
flashing. Before flashing, use `idf.py menuconfig` to check the board's flash
size/mode and console interface. No GPIOs, PSRAM, or sensor settings are assumed.

If GNU Make is available in that terminal, these commands do the same work:

```powershell
make build
make flash-monitor PORT=COM5
```

Other targets: `flash`, `monitor`, `menuconfig`, `size`, `clean`, `help`.
`PORT`, `BAUD` (flash baud, default 460800), and `BUILD_DIR` can be overridden.
Make is optional; EIM's Windows installation need not provide it.

Expected serial output includes `Motion Cue ESP32-S3: disarmed` and
`IMU driver is not configured; gesture control is disabled`. This is a
bootable firmware scaffold, **not a functioning gesture controller yet**.

Official [EIM terminal and flashing instructions](https://docs.espressif.com/projects/esp-idf/en/stable/esp32/get-started/windows-start-project.html).

## Integration still required

C++17 sources implement segmentation, feature extraction, model rejection,
twist mode and the session watchdog. Host-side tests compile these files.
`main.cpp` supplies the portable processing function; `app_main.cpp` boots ESP-IDF.
`imu.cpp` intentionally fails initialization. The model header rejects all motion.

The exact board and sensor still need confirmation. Implement the acquisition
task, real IMU driver, calibration and regular
acquisition. Add actual Wi-Fi/MQTT transport around Session using the shared
protocol. Publish mode events/status with a monotonic sequence and boot ID;
call Session::tick every loop and disconnect on transport failure. Reset the
segmenter on reconnect and never replay a captured pre-disconnect event.

Stationary startup calibration must estimate gyro bias and verify accelerometer
norm/axis signs. Sampling remains active while disarmed. Reject timing gaps,
invalid samples and buffer overflow. Measure RAM, flash and execution time on
the actual board; native tests cannot establish these measurements.

Twist toggling is configurable via `ControlMode::twist_toggle`; default true is
an assumption from the handoff. Replace gesture_model.h only with a reviewed
export. Keep model version/feature version in status and release metadata.
