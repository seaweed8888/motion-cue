# Windows host

Install `monitoring/requirements.txt`, then run `python monitoring/dashboard.py`
or `python -m monitoring.dashboard` from the repository root. This opens a native
PySide6/Qt studio, maximized on launch with normal title-bar window controls.
Model and recording controls sit on the
left, tilt and live gesture inference in the center, and health on the right.
You can also run `python dashboard.py` from this folder; its default
config path does not depend on the working directory. Closing the window stops
the MQTT listener and any local broker started by this dashboard.
For plain loopback addresses (`127.0.0.1`, `localhost` or `::1`), the dashboard
reuses an existing listener or starts its bundled Python MQTT broker in the
background. No separate Mosquitto installation is needed. An existing broker
is left running when the window closes. Startup failures appear in the dashboard.
Remote brokers and TLS/username/password configurations still require a separately
configured broker; automatic startup never replaces those with an anonymous server.
The requirements use PySide6-Essentials, which includes Qt Widgets without the
unused Qt add-ons and web engine.

The native studio never injects keys. Esc leaves fullscreen and F11 toggles it.
Selected model, inference thresholds, user and session are remembered locally.
Place trusted training `.pkl` artifacts under `models/` and use Refresh model
library to find them. Live inference uses the same 55-feature extraction and
streaming segmentation as training; the confidence and onset controls affect
laptop testing only. They do not rewrite the model or device firmware. The
model's rejection threshold is the reset default. A fixture model is identified
as such, and synthetic telemetry remains marked synthetic in saved recordings.

The tilt ball uses accelerometer-derived roll/pitch over ±45 degrees. It is not
a position estimate; linear acceleration can affect it while moving. Without
fresh telemetry, the ball returns to center, turns gray and its trail clears.
The left inspector also turns gray when telemetry is inactive. Gray means off
or idle; orange means active/live/recognized. Errors remain red. The native
Windows title bar stays visible; there is no extra in-app header.
Health includes broker and device state, telemetry freshness, actual timestamp
sample rate, expected rate, gap/invalid-batch counts, inference skips and recent predictions.
No values are fabricated when a sensor or trained model is absent.

Motion reads the newest validated tilt on a separate precise 16 ms display timer;
it does not wait for the 80 ms health refresh or ease toward old readings. The
trail fades independently and the instrument stops repainting once stationary.
Model discovery/loading and recording saves run in background workers. Prediction
runs outside the telemetry lock, with at most one waiting gesture window. Under
overload, older waiting windows are replaced and counted as Inference skips;
raw samples remain intact for recording. Results from an old model, threshold
configuration or connection are ignored. Results over two seconds old are ignored.
Display timing is best effort: device batching, MQTT, OS scheduling and display
refresh add latency beyond the desktop timer.

For labeled data, enter user/session, choose one gesture type, press Record,
then Stop and Save take (or Discard). Each take is annotated with that label
over its entire captured interval. Saves write a temporary file before exposing
the completed JSON, keep the take on failure, and finish before a requested close.
Saved JSON files go under `data/raw/` and
work with `python -m training.preprocess`. Keep all takes from one session in
the same split. Empty/invalid/interrupted recordings cannot be saved. The limit
is 300 seconds; closing with an unsaved take offers save/discard/cancel.
Review collected gesture boundaries before training. Retraining remains in
the existing training CLI. The device must publish calibrated SI-unit batches
to `motioncue/<device_id>/telemetry`; hardware publishing is still pending.

The separate browser host supports native Windows key
injection using SendInput; it is disabled unless `--enable-keyboard` is supplied.
No browser extension or administrator rights are needed for ordinary desktop
apps. Elevated foreground apps may reject input from a normal process.
One press/release pair is sent immediately per accepted swipe.

Copy config.example.json to config.json and pass `--config monitoring/config.json`.
Use an authenticated MQTT broker on the laptop. For hardware, bind the broker
to the laptop LAN address, allow the port only on the private network firewall,
and give the device write access to its status/events/telemetry and read access
to its control topic. Give the host the inverse rights. Keep passwords in ignored
config files. TLS is supported with the system CA store (`tls: true`).

The optional browser dashboard (`python -m monitoring.app`) requires a separate
MQTT broker and binds its HTTP server only to 127.0.0.1,
uses same-origin request tokens for mutations,
and streams bounded history through SSE. No remote hosting or database.
The native dashboard calls the shared router directly and starts no HTTP server.
Run one host at a time so gestures are not processed twice.
The browser dashboard accepts only arrows, PageUp, PageDown and Space for mappings.
Mappings are not persisted.

Test with the manual simulator before enabling keys. Never count manual fixture
events as recognized gestures. Focus the slideshow before actual use.
