"""Live telemetry, local inference and labeled recording. Never emits keyboard input."""
from collections import deque
import json
import math
from pathlib import Path
import pickle
import threading
import time
import uuid

import numpy as np
from training.features import FEATURE_COUNT, FEATURE_VERSION, extract, validate
from training.preprocess import Segmenter

ROOT = Path(__file__).resolve().parents[1]
LABELS = json.loads((ROOT / "shared/labels.json").read_text())
UNITS = {"acceleration": "m/s2", "gyroscope": "rad/s", "time": "s"}


class LiveMonitor:
    def __init__(self, device_id, clock=time.monotonic):
        self.device_id, self.clock = device_id, clock
        self.lock = threading.RLock()
        self.model = None
        self.model_path = None
        self.synthetic_model = False
        self.default_threshold = .75
        self.threshold, self.acceleration_onset, self.rotation_onset = .75, 1.2, .7
        self.segmenter = Segmenter()
        self.last_seen = None
        self.connected = False
        self.last_t = None
        self.metadata = None
        self.roll = self.pitch = self.rate = 0.
        self._motion_t = self._gravity = self._quiet_since = None
        self._velocity = np.zeros(2)
        self._position = np.zeros(2)
        self.latest = None
        self.gaps = self.invalid = self.total = 0
        self.error = ""
        self.prediction, self.confidence, self.predicted_at = "Idle", None, 0
        self.history = deque(maxlen=6)
        self.recording = None
        self._generation = 0
        self._pending = None
        self._predicting = False
        self._inference_error = ""
        self.inference_skips = 0

    def configure(self, threshold, acceleration, rotation):
        if not 0 <= threshold <= 1 or not .6 < acceleration <= 10 or not .35 < rotation <= 10:
            raise ValueError("Invalid inference thresholds")
        with self.lock:
            self.threshold, self.acceleration_onset, self.rotation_onset = threshold, acceleration, rotation
            self.segmenter = Segmenter(acceleration, rotation)
            self._generation += 1
            self._pending = None
            self.prediction, self.confidence = "Idle", None

    @staticmethod
    def read_model(path, model_dir=ROOT / "models"):
        path, model_dir = Path(path).resolve(), Path(model_dir).resolve()
        if not path.is_relative_to(model_dir) or path.suffix != ".pkl":
            raise ValueError("Choose a local .pkl model from the models folder")
        # Pickles are executable; only the project's trusted training artifacts belong here.
        with path.open("rb") as stream:
            artifact = pickle.load(stream)
        model = artifact["model"]
        if (artifact["feature_version"] != FEATURE_VERSION or model.n_features_in_ != FEATURE_COUNT
                or list(model.classes_) != [0, 1, 2, 3]):
            raise ValueError("Model must use feature version 1, 55 features and all four gesture classes")
        threshold = float(artifact["threshold"])
        if not 0 <= threshold <= 1:
            raise ValueError("Invalid model rejection threshold")
        return path, artifact, threshold

    def load_model(self, path, model_dir=ROOT / "models"):
        self.install_model(self.read_model(path, model_dir))

    def install_model(self, loaded):
        path, artifact, threshold = loaded
        with self.lock:
            self.model, self.model_path = artifact["model"], path
            self.synthetic_model = bool(artifact.get("synthetic", False))
            self.default_threshold = threshold
            self.configure(threshold, self.acceleration_onset, self.rotation_onset)
            self.prediction, self.confidence = "Idle", None
            self.history.clear()
            self.error = ""
            self._inference_error = ""

    def clear_model(self):
        with self.lock:
            self.model = self.model_path = None
            self._generation += 1
            self._pending = None
            self.prediction, self.confidence = "Idle", None
            self.history.clear()
            self._inference_error = ""

    def disconnected(self):
        with self.lock:
            self.segmenter = Segmenter(self.acceleration_onset, self.rotation_onset)
            self.connected = False
            self.last_t = None
            self._motion_t = self._gravity = self._quiet_since = None
            self._velocity[:] = self._position[:] = 0
            self._generation += 1
            self._pending = None
            self.prediction, self.confidence = "Idle", None
            if self.recording and self.recording["state"] == "recording":
                self.recording["error"] = "Connection lost during recording; discard and record again."
                self.recording["state"] = "review"

    def receive(self, doc, retained=False):
        with self.lock:
            try:
                if (retained or not isinstance(doc, dict) or type(doc.get("v")) is not int
                        or doc["v"] != 1 or doc.get("device_id") != self.device_id):
                    raise ValueError("Invalid telemetry envelope")
                if doc.get("units") != UNITS or not isinstance(doc.get("boot_id"), str) or not doc["boot_id"]:
                    raise ValueError("Telemetry needs a boot ID and calibrated SI units")
                nominal = doc["sample_rate_hz"]
                if type(nominal) not in (int, float) or not 0 < nominal <= 1000:
                    raise ValueError("Invalid telemetry sample rate")
                batch = validate(doc["samples"])
                metadata = {key: doc[key] for key in ("boot_id", "sample_rate_hz", "units")}
                changed = self.metadata is not None and metadata != self.metadata
                if changed:
                    self.disconnected()
                if self.last_t is not None and batch[0, 0] <= self.last_t:
                    raise ValueError("Out-of-order or duplicate telemetry")
                times = batch[:, 0] if self.last_t is None else np.r_[self.last_t, batch[:, 0]]
                gap_count = int(np.count_nonzero(np.diff(times) > 2.5 / nominal))
                stale = self.last_seen is not None and self.clock() - self.last_seen > 1.5
                if gap_count or stale:
                    self.gaps += max(1, gap_count)
                    self.disconnected()
                self.metadata, self.last_t = metadata, float(batch[-1, 0])
                self.last_seen = self.clock()
                self.connected = True
                self.rate = float((len(batch)-1) / (batch[-1, 0]-batch[0, 0]))
                self.latest = batch[-1].tolist()
                ax, ay, az = map(float, batch[-1, 1:4])
                self.roll = math.degrees(math.atan2(ay, az))
                self.pitch = math.degrees(math.atan2(-ax, math.hypot(ay, az)))
                self.total += len(batch)
                self.error = ""
                if gap_count:
                    return
                if self.recording and self.recording["state"] == "recording":
                    record = self.recording
                    record["metadata"] = metadata
                    record["synthetic"] |= bool(doc.get("synthetic", False))
                    record["samples"].extend(batch.tolist())
                    if self.clock()-record["started"] >= 300 or len(record["samples"]) >= 300000:
                        record["state"] = "review"
                for row in batch:
                    self._move(row)
                    window = self.segmenter.push(row)
                    if window is not None and self.model is not None:
                        # Keep only the newest waiting window; inference must never queue telemetry.
                        if self._pending is not None:
                            self.inference_skips += 1
                        self._pending = (window, self.model, self._generation, self.clock())
                        if not self._predicting:
                            self._predicting = True
                            threading.Thread(target=self._infer_pending, daemon=True).start()
            except (ValueError, KeyError, TypeError, AttributeError) as exc:
                self.invalid += 1
                self.error = str(exc)
                self.disconnected()

    def _infer_pending(self):
        while True:
            with self.lock:
                pending, self._pending = self._pending, None
                if pending is None:
                    self._predicting = False
                    return
            window, model, generation, received_at = pending
            failure = ""
            try:
                scores = np.asarray(model.predict_proba([extract(window)])[0])
                if (scores.shape != (4,) or not np.isfinite(scores).all()
                        or np.any(scores < 0) or np.any(scores > 1)):
                    raise ValueError("Model returned invalid class scores")
                winner = int(scores.argmax())
            except Exception as exc:
                failure = f"Inference failed: {exc}. Check or reload the model."
            with self.lock:
                if generation != self._generation or self.clock()-received_at >= 2:
                    continue
                self._inference_error = failure
                if failure:
                    self.prediction, self.confidence = "Idle", None
                    continue
                self.confidence = float(scores[winner])
                label = winner if self.confidence >= self.threshold else 0
                self.prediction = LABELS[str(label)].replace("_", " ").capitalize()
                self.predicted_at = received_at
                self.history.appendleft(dict(gesture=self.prediction, confidence=self.confidence,
                                             time=time.strftime("%H:%M:%S")))

    def _move(self, row):
        t = float(row[0])
        acceleration, rotation = row[1:4].astype(float), row[4:7].astype(float)
        if self._motion_t is None:
            self._gravity = acceleration.copy()
            self._motion_t = t
            return
        dt, self._motion_t = t-self._motion_t, t
        # Rotate gravity into the current sensor frame before removing it.
        angle = float(np.linalg.norm(rotation))*dt
        if angle > 0:
            axis = rotation/np.linalg.norm(rotation)
            gravity = self._gravity
            self._gravity = (gravity*math.cos(angle)-np.cross(axis, gravity)*math.sin(angle)
                             + axis*np.dot(axis, gravity)*(1-math.cos(angle)))
        linear = acceleration-self._gravity
        self._gravity += (1-math.exp(-dt/.5))*linear
        quiet = np.linalg.norm(linear) < .35 and np.linalg.norm(rotation) < .08
        self._quiet_since = (t if self._quiet_since is None else self._quiet_since) if quiet else None
        if self._quiet_since is not None and t-self._quiet_since >= .12:
            self._velocity[:] = 0
            self._position *= math.exp(-dt/.12)
            if np.linalg.norm(self._position) < .0005:
                self._position[:] = 0
        else:
            # shortcut: damped sensor-plane motion, use external tracking for metric hand position.
            self._velocity *= math.exp(-dt/.35)
            if not quiet:
                self._velocity += np.array([linear[1], linear[0]])*dt
            self._position *= math.exp(-dt/3)
            self._position += (self._velocity*8 + np.array([rotation[0]+rotation[2], -rotation[1]])/math.radians(45))*dt
            self._position /= max(1., float(np.linalg.norm(self._position)))

    def motion_pose(self):
        """Normalized gesture position, with a return to center if samples stop arriving."""
        with self.lock:
            age = 0. if self.last_seen is None else self.clock()-self.last_seen
            online = self.connected and self.last_seen is not None and age <= 1.5
            fade = math.exp(-max(0., age-.12)/.12) if online else 0.
            x, y = self._position*fade
            return float(x), float(y), online

    def pose(self):
        """Small snapshot for the display clock, independent of inference and health formatting."""
        with self.lock:
            online = self.connected and self.last_seen is not None and self.clock()-self.last_seen <= 1.5
            return self.roll, self.pitch, online

    def start_recording(self, user, session, label):
        with self.lock:
            if self.recording is not None:
                raise ValueError("Save or discard the current recording first")
            if not user.strip() or not session.strip() or str(label) not in LABELS:
                raise ValueError("Enter a user, session and gesture label")
            if not self.connected or self.last_seen is None or self.clock()-self.last_seen > 1.5:
                raise ValueError("Connect a device publishing live telemetry first")
            self.recording = dict(state="recording", user_id=user.strip(), session_id=session.strip(),
                                  label=int(label), samples=[], metadata=None, error="", synthetic=False,
                                  started=self.clock())

    def stop_recording(self):
        with self.lock:
            if self.recording:
                self.recording["state"] = "review"

    def discard_recording(self):
        with self.lock:
            self.recording = None

    def save_recording(self, directory=ROOT / "data/raw"):
        with self.lock:
            record = self.recording
            if not record or record["state"] != "review":
                raise ValueError("Stop the recording before saving")
            if record["error"] or len(record["samples"]) < 3:
                raise ValueError(record["error"] or "Recording contains no complete telemetry batch")
            identifier = uuid.uuid4().hex
            samples = record["samples"]
            doc = dict(record["metadata"], user_id=record["user_id"], session_id=record["session_id"],
                       recording_id=identifier, samples=samples, synthetic=record["synthetic"],
                       boundaries=[dict(start=samples[0][0], end=samples[-1][0], label=record["label"])])
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"recording-{identifier}.json"
        temporary = path.with_suffix(".json.partial")
        try:
            with temporary.open("x", encoding="utf-8") as stream:
                json.dump(doc, stream)
            temporary.rename(path)
        except Exception:
            temporary.unlink(missing_ok=True)
            raise
        with self.lock:
            if self.recording is record:
                self.recording = None
        return path

    def snapshot(self):
        with self.lock:
            age = None if self.last_seen is None else self.clock()-self.last_seen
            online = self.connected and age is not None and age <= 1.5
            if self.connected and not online:
                self.disconnected()
            record = self.recording
            return dict(online=online, age=age, roll=self.roll, pitch=self.pitch, rate=self.rate,
                        nominal=self.metadata["sample_rate_hz"] if self.metadata else None,
                        latest=self.latest, total=self.total, gaps=self.gaps, invalid=self.invalid,
                        inference_skips=self.inference_skips,
                        error=self.error or self._inference_error, prediction=self.prediction if online and self.clock()-self.predicted_at < 2 else "Idle",
                        confidence=self.confidence, history=list(self.history),
                        recording_state=record["state"] if record else "idle",
                        recording_count=len(record["samples"]) if record else 0,
                        recording_error=record["error"] if record else "")
