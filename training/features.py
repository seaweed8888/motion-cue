"""Feature spec v1: SI units, float32, 55 values. AI-assisted implementation."""
import numpy as np

FEATURE_VERSION = 1
FEATURE_COUNT = 55


def validate(samples):
    samples = np.asarray(samples, dtype=np.float32)
    if samples.ndim != 2 or samples.shape[1] != 7 or len(samples) < 3:
        raise ValueError("Expected at least three [t_seconds, ax, ay, az, gx, gy, gz] samples")
    if not np.isfinite(samples).all() or not (np.diff(samples[:, 0]) > 0).all():
        raise ValueError("Samples must be finite with strictly increasing timestamps")
    return samples


def extract(samples):
    s = validate(samples)
    result = [s[-1, 0] - s[0, 0]]
    for axis in range(1, 7):
        x = s[:, axis]
        mean = np.mean(x, dtype=np.float32)
        result.extend([x.min(), x.max(), mean, np.sqrt(np.mean((x-mean)**2)),
                       np.mean(x*x), x[-1]-x[0]])
        for part in range(3):
            result.append(np.mean(x[part*len(x)//3:(part+1)*len(x)//3]))
    return np.asarray(result, dtype=np.float32)
