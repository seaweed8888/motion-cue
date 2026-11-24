# Feature specification v1

Input: at least 3 samples, `[t, ax, ay, az, gx, gy, gz]`, increasing acquisition
time in seconds, acceleration in m/s² (gravity retained), angular velocity in rad/s.
Subtract measured gyro bias in the driver before recording AND inference.
Do not independently normalize, reorder axes, or remove gravity during training.
Use a marked, consistent grip. Event timestamps are local relative times; avoid
float32 precision loss from long absolute uptime by rebasing in the driver.

Output: 55 float32 values, no scaling. First event duration (`last t - first t`).
For each axis in ax/ay/az/gx/gy/gz order append:

1. Minimum, maximum, arithmetic mean.
2. Population standard deviation, mean square, last minus first.
3. Mean of each of three sequential partitions with boundaries `floor(k*N/3)`.

Movement gate uses acceleration minus slowly tracked gravity/baseline, and gyro
magnitude. Acceleration onset/settle thresholds: 1.2/0.6 m/s²; gyro: 0.7/0.35 rad/s.
Onset persists 40 ms; pre-trigger 150 ms; completion after 200 ms quiet;
capture timeout 2 s; cooldown 500 ms plus 200 ms settled. Baseline alpha 0.02
per sample. Freeze baseline while capturing. All are provisional for ~100 Hz.
Capacity 256 event samples, 32 pre-trigger samples. Select a supported IMU rate
before hardware use and change both implementations together if tuning.

Feature tests compare identical windows in Python/C++. Export uses emlearn inline
float thresholds and 8-bit soft-vote leaves. Probability parity tolerance accounts
for quantization; validate near-threshold rejection on real held-out windows.
