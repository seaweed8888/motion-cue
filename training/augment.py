"""Optional training-only, small consistent coordinate rotation and sensor noise."""
import numpy as np
from .features import validate


def augment(samples, rng):
    result = validate(samples).copy()
    angle = rng.uniform(-.08, .08)
    c, s = np.cos(angle), np.sin(angle)
    rotation = np.array([[c,-s,0],[s,c,0],[0,0,1]], dtype=np.float32)
    for start, noise in ((1, .015), (4, .003)):
        result[:, start:start+3] = result[:, start:start+3] @ rotation.T
        result[:, start:start+3] += rng.normal(0, noise, (len(result),3))
    return result
