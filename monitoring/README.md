# Windows host

Run `python -m monitoring.app` from the repository root. Native Windows key
injection uses SendInput; it is disabled unless `--enable-keyboard` is supplied.
No browser extension or administrator rights are needed for ordinary desktop
apps. Elevated foreground apps may reject input from a normal process.
One press/release pair is sent immediately per accepted swipe.

Copy config.example.json to config.json and pass `--config monitoring/config.json`.
Use an authenticated MQTT broker on the laptop. For hardware, bind the broker
to the laptop LAN address, allow the port only on the private network firewall,
and give the device write access to its status/events/telemetry and read access
to its control topic. Give the host the inverse rights. Keep passwords in ignored
config files. TLS is supported with the system CA store (`tls: true`).

The dashboard binds only 127.0.0.1, uses same-origin request tokens for mutations,
and streams bounded history through SSE. No remote hosting or database.
Mappings accept only arrows, PageUp, PageDown and Space. They are not persisted.

Test with the manual simulator before enabling keys. Never count manual fixture
events as recognized gestures. Focus the slideshow before actual use.
