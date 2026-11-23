# Hardware decisions needed

- Exact ESP32-S3 board and revision: unknown.
- Exact accelerometer/gyroscope board and chip: unknown.
- Toolchain: native ESP-IDF via EIM, selected for the requested build/flash workflow.
- Twist toggles arm/disarm: proposed default, pending confirmation.
- Wiring, I2C pins/address, sensor rate, voltage and LED: unassigned.

Use USB power initially. Do not infer a GPIO pinout from the ESP32 family name.
After identifying hardware, document wiring and measured stationary calibration,
axis directions, supported ODR and timing jitter. Keep the holding orientation
marked for both partners. No arbitrary-grip support is claimed.
