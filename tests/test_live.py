import json
from pathlib import Path
import pickle
import threading
import time

import numpy as np
import pytest
from sklearn.ensemble import RandomForestClassifier
from monitoring.live import LABELS, LiveMonitor, UNITS
from training.features import extract
from training.preprocess import load_recording, segment


def telemetry(samples=None, **changes):
    doc = dict(v=1, device_id="test", boot_id="boot", units=UNITS,
               sample_rate_hz=100, samples=samples if samples is not None else
               [[t, 0, 0, 9.81, 0, 0, 0] for t in (0, .01, .02)])
    doc.update(changes)
    return doc


@pytest.mark.parametrize("axis,output,sign", [(1, 1, 1), (2, 0, 1), (4, 0, 1), (5, 1, -1), (6, 0, 1)])
@pytest.mark.parametrize("direction", [-1, 1])
def test_motion_follows_acceleration_and_rotation_then_centers(axis, output, sign, direction):
    live = LiveMonitor("test", clock=lambda: 100.)
    live.receive(telemetry())
    rows = [[i/100, 0., 0., 9.81, 0., 0., 0.] for i in range(3, 23)]
    for row in rows:
        row[axis] = direction*2.
    live.receive(telemetry(rows))
    assert live.motion_pose()[output]*sign*direction > .01
    assert np.linalg.norm(live.motion_pose()[:2]) <= 1.
    live.receive(telemetry([[i/100, 0, 0, 9.81, 0, 0, 0] for i in range(23, 223)]))
    assert live.motion_pose() == pytest.approx((0., 0., True), abs=.002)


def test_motion_starts_neutral_at_any_tilt_and_resets_on_reconnect(monitor):
    live, now = monitor
    live.receive(telemetry([[i/100, 0, 6.9367, 6.9367, 0, 0, 0] for i in range(100)]))
    assert live.motion_pose() == (0., 0., True)
    live.receive(telemetry([[i/100, 0, 9, 6.9367, 0, 0, 0] for i in range(100, 120)]))
    assert live.motion_pose()[0] > 0
    now[0] += .7
    assert abs(live.motion_pose()[0]) < .01
    live.disconnected()
    assert live.motion_pose() == (0., 0., False)
    live.receive(telemetry(boot_id="new"))
    assert live.motion_pose() == (0., 0., True)


def test_motion_uses_all_samples_and_is_independent_of_batch_size():
    rows = [[i/100, 0, 0, 9.81, 0, 0, 0] for i in range(120)]
    for row in rows[3:90]:
        row[2] = 2.
    monitors = [LiveMonitor("test", clock=lambda: 100.) for _ in range(2)]
    monitors[0].receive(telemetry(rows))
    for start in range(0, len(rows), 3):
        monitors[1].receive(telemetry(rows[start:start+3]))
    assert monitors[0].motion_pose() == pytest.approx(monitors[1].motion_pose())
    assert monitors[0].motion_pose()[0] > .01


def test_motion_tracks_turn_and_settles_while_held_at_new_angle():
    live = LiveMonitor("test", clock=lambda: 100.)
    live.receive(telemetry())
    rows = []
    for i in range(3, 203):
        angle = min(i-2, 40)/100
        rows.append([i/100, 0, 9.81*np.sin(angle), 9.81*np.cos(angle),
                     1. if i <= 42 else 0., 0, 0])
    live.receive(telemetry(rows[:40]))
    assert live.motion_pose()[0] > .2
    live.receive(telemetry(rows[40:]))
    assert live.motion_pose() == pytest.approx((0., 0., True), abs=.002)


def test_slow_motion_accumulates_at_high_sample_rates():
    live = LiveMonitor("test", clock=lambda: 100.)
    live.receive(telemetry([[i/1000, 0, 0, 9.81, 0, 0, .1] for i in range(501)],
                           sample_rate_hz=1000))
    assert .05 < live.motion_pose()[0] < .1


@pytest.fixture
def monitor():
    now = [100.]
    return LiveMonitor("test", clock=lambda: now[0]), now


def test_tilt_rate_and_timeout(monitor):
    live, now = monitor
    live.receive(telemetry([[t, 0, 9.81, 9.81, 0, 0, 0] for t in (0, .01, .02)]))
    state = live.snapshot()
    assert state["online"] and state["roll"] == pytest.approx(45)
    assert state["pitch"] == 0 and state["rate"] == pytest.approx(100)
    assert state["total"] == 3
    now[0] += 2
    assert not live.snapshot()["online"]
    assert live.snapshot()["prediction"] == "Idle"


@pytest.mark.parametrize("changes", [dict(v=True), dict(device_id="other"), dict(units={}),
                                      dict(sample_rate_hz=0), dict(sample_rate_hz=True),
                                      dict(samples=[[0]*7]*3)])
def test_invalid_telemetry_is_rejected(monitor, changes):
    live, now = monitor
    live.receive(telemetry(**changes))
    state = live.snapshot()
    assert not state["online"] and state["invalid"] == 1 and state["error"]
    assert state["total"] == 0


def test_retained_duplicate_and_recording_errors(monitor):
    live, now = monitor
    live.receive(telemetry(), retained=True)
    assert live.snapshot()["invalid"] == 1
    live.receive(telemetry())
    live.start_recording("one", "day1", 2)
    live.receive(telemetry())
    assert live.snapshot()["recording_error"]
    assert live.snapshot()["recording_state"] == "review"
    with pytest.raises(ValueError):
        live.save_recording()


@pytest.mark.parametrize("failure", ["restart", "gap", "disconnect", "timeout"])
def test_interrupted_recordings_cannot_save(monitor, tmp_path, failure):
    live, now = monitor
    live.receive(telemetry())
    live.start_recording("one", "day1", 1)
    live.receive(telemetry([[t, 0, 0, 9.81, 0, 0, 0] for t in (.03, .04, .05)]))
    if failure == "restart":
        live.receive(telemetry(boot_id="new"))
    elif failure == "gap":
        live.receive(telemetry([[t, 0, 0, 9.81, 0, 0, 0] for t in (.2, .21, .22)]))
    elif failure == "disconnect":
        live.disconnected()
    else:
        now[0] += 2
        live.snapshot()
    with pytest.raises(ValueError):
        live.save_recording(tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_labeled_capture_is_training_compatible(monitor, tmp_path):
    live, now = monitor
    live.receive(telemetry())
    live.start_recording("one", "day1", 3)
    samples = [[t, 0, 0, 9.81, 0, 0, 0] for t in (.03, .04, .05)]
    live.receive(telemetry(samples, synthetic=True))
    with pytest.raises(ValueError, match="Stop"):
        live.save_recording(tmp_path)
    live.stop_recording()
    path = live.save_recording(tmp_path)
    doc = load_recording(path)
    assert doc["samples"] == np.asarray(samples, dtype=np.float32).tolist()
    assert doc["synthetic"] and doc["user_id"] == "one" and doc["session_id"] == "day1"
    assert doc["boundaries"][0]["label"] == 3
    assert live.snapshot()["recording_state"] == "idle"


def test_model_inference_across_telemetry_batches(monitor, tmp_path):
    live, now = monitor
    samples = json.loads(Path("data/sample/continuous.json").read_text())["samples"]
    window = list(segment(samples))[0]
    features = extract(window)
    model = RandomForestClassifier(n_estimators=5, max_depth=4, random_state=4).fit(
        np.array([features, features+100, features+200, features+300]), [2, 0, 1, 3])
    path = tmp_path/"trained.pkl"
    path.write_bytes(pickle.dumps(dict(model=model, threshold=0., feature_version=1, synthetic=True)))
    live.load_model(path, model_dir=tmp_path)
    for index in range(0, len(samples), 10):
        batch = samples[index:index+10]
        if len(batch) >= 3:
            live.receive(telemetry(batch))
    expected = LABELS[str(int(model.predict([features])[0]))].replace("_", " ").capitalize()
    deadline = time.monotonic()+3
    while live._predicting and time.monotonic() < deadline:
        time.sleep(.001)
    assert not live._predicting
    state = live.snapshot()
    assert state["prediction"] == expected
    assert len(state["history"]) == 1 and state["confidence"] is not None
    assert live.synthetic_model
    old_segmenter = live.segmenter
    live.configure(.95, 2., 1.)
    assert live.threshold == .95 and live.segmenter is not old_segmenter
    with pytest.raises(ValueError):
        live.load_model(path, model_dir=tmp_path/"another")


def test_streaming_segmenter_matches_offline():
    from training.preprocess import Segmenter
    samples = json.loads(Path("data/sample/continuous.json").read_text())["samples"]
    streaming = Segmenter()
    actual = [window for row in np.asarray(samples, dtype=np.float32)
              if (window := streaming.push(row)) is not None]
    expected = list(segment(samples))
    assert len(actual) == len(expected) == 1
    np.testing.assert_array_equal(actual[0], expected[0])


@pytest.mark.parametrize("problem", ["version", "features", "classes", "threshold"])
def test_incompatible_models_are_rejected(monitor, tmp_path, problem):
    live, now = monitor
    count = 54 if problem == "features" else 55
    labels = [0, 1, 2, 2] if problem == "classes" else [0, 1, 2, 3]
    model = RandomForestClassifier(n_estimators=1, random_state=1).fit(np.zeros((4, count)), labels)
    artifact = dict(model=model, feature_version=2 if problem == "version" else 1,
                    threshold=2. if problem == "threshold" else .75, synthetic=True)
    path = tmp_path/"bad.pkl"
    path.write_bytes(pickle.dumps(artifact))
    with pytest.raises(ValueError):
        live.load_model(path, model_dir=tmp_path)
    assert live.model is None


def test_recording_limit_and_discard(monitor):
    live, now = monitor
    live.receive(telemetry())
    live.start_recording("one", "day1", 1)
    live.recording["started"] = now[0]-301
    live.receive(telemetry([[t, 0, 0, 9.81, 0, 0, 0] for t in (.03, .04, .05)]))
    assert live.snapshot()["recording_state"] == "review"
    assert not live.snapshot()["recording_error"]
    live.discard_recording()
    assert live.snapshot()["recording_state"] == "idle"


def test_failed_save_keeps_recording(monitor, tmp_path):
    live, now = monitor
    live.receive(telemetry())
    live.start_recording("one", "day1", 0)
    live.receive(telemetry([[t, 0, 0, 9.81, 0, 0, 0] for t in (.03, .04, .05)]))
    live.stop_recording()
    blocked = tmp_path/"not-a-directory"
    blocked.write_text("existing data")
    with pytest.raises(OSError):
        live.save_recording(blocked)
    assert live.snapshot()["recording_count"] == 3
    assert blocked.read_text() == "existing data"


def test_saving_does_not_hold_the_telemetry_lock(monitor, tmp_path, monkeypatch):
    live, now = monitor
    live.receive(telemetry())
    live.start_recording("one", "day1", 0)
    live.receive(telemetry([[t, 0, 0, 9.81, 0, 0, 0] for t in (.03, .04, .05)]))
    live.stop_recording()
    started, release = threading.Event(), threading.Event()
    dump = json.dump
    outcomes = []

    def slow_dump(*args, **kwargs):
        started.set()
        assert release.wait(3)
        return dump(*args, **kwargs)

    monkeypatch.setattr("monitoring.live.json.dump", slow_dump)
    worker = threading.Thread(target=lambda: outcomes.append(live.save_recording(tmp_path)))
    worker.start()
    try:
        assert started.wait(2)
        live.receive(telemetry([[t, 0, 0, 9.81, 0, 0, 0] for t in (.06, .07, .08)]))
        assert live.snapshot()["total"] == 9
        assert list(tmp_path.glob("*.json")) == []
    finally:
        release.set()
        worker.join(3)
    assert not worker.is_alive() and len(outcomes) == 1
    assert len(json.loads(outcomes[0].read_text())["samples"]) == 3
    assert not list(tmp_path.glob("*.partial"))


def test_partial_save_is_cleaned_and_take_is_preserved(monitor, tmp_path, monkeypatch):
    live, now = monitor
    live.receive(telemetry())
    live.start_recording("one", "day1", 0)
    live.receive(telemetry([[t, 0, 0, 9.81, 0, 0, 0] for t in (.03, .04, .05)]))
    live.stop_recording()

    def fail(doc, stream):
        stream.write('{"partial":')
        raise OSError("disk full")

    monkeypatch.setattr("monitoring.live.json.dump", fail)
    with pytest.raises(OSError, match="disk full"):
        live.save_recording(tmp_path)
    assert list(tmp_path.iterdir()) == []
    assert live.snapshot()["recording_count"] == 3


def test_disconnected_device_cannot_start_recording(monitor):
    live, now = monitor
    live.receive(telemetry())
    live.disconnected()
    with pytest.raises(ValueError, match="Connect"):
        live.start_recording("one", "day1", 1)


@pytest.mark.parametrize("invalidate", [None, "disconnect", "threshold", "model"])
def test_slow_inference_never_blocks_telemetry_or_replays_stale_results(monitor, monkeypatch, invalidate):
    live, now = monitor
    started, release = threading.Event(), threading.Event()
    calls = []

    class SlowModel:
        def predict_proba(self, features):
            calls.append(float(features[0]))
            started.set()
            assert release.wait(3)
            return [[0., 0., 1., 0.]]

    class Windows:
        def push(self, row):
            return row

    monkeypatch.setattr("monitoring.live.extract", lambda row: row[0])
    live.model, live.segmenter = SlowModel(), Windows()
    live.receive(telemetry())
    assert started.wait(2)
    try:
        live.receive(telemetry([[t, 0, 9.81, 9.81, 0, 0, 0] for t in (.03, .04, .05)]))
        assert live.snapshot()["total"] == 6
        assert live.pose() == pytest.approx((45., 0., True))
        if invalidate == "disconnect":
            live.disconnected()
        elif invalidate == "threshold":
            live.configure(.9, 2., 1.)
        elif invalidate == "model":
            live.clear_model()
    finally:
        release.set()
    deadline = time.monotonic()+3
    while live._predicting and time.monotonic() < deadline:
        time.sleep(.001)
    assert not live._predicting
    if invalidate:
        assert not live.snapshot()["history"]
    else:
        assert len(calls) == 2 and calls[-1] == pytest.approx(.05)
        assert live.snapshot()["prediction"] != "Idle"


def test_failed_inference_does_not_interrupt_valid_recording(monitor, monkeypatch):
    live, now = monitor
    live.receive(telemetry())
    live.start_recording("one", "day1", 1)

    class BrokenModel:
        def predict_proba(self, features):
            raise RuntimeError("broken model")

    class Windows:
        def push(self, row):
            return row

    live.model, live.segmenter = BrokenModel(), Windows()
    monkeypatch.setattr("monitoring.live.extract", lambda row: row)
    live.receive(telemetry([[t, 0, 0, 9.81, 0, 0, 0] for t in (.03, .04, .05)]))
    deadline = time.monotonic()+3
    while live._predicting and time.monotonic() < deadline:
        time.sleep(.001)
    state = live.snapshot()
    assert "broken model" in state["error"] and state["online"]
    assert state["recording_count"] == 3 and state["recording_state"] == "recording"
    live.discard_recording()
