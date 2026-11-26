import json
import sys
from types import SimpleNamespace

import pytest
from training import collect


@pytest.fixture
def capture(tmp_path, monkeypatch):
    class Client:
        def __init__(self):
            self.connected = True
            self.closed = False
            self.subscriptions = []

        def connect(self, *args):
            pass

        def loop_start(self):
            self.on_connect(self, None, None, SimpleNamespace(is_failure=False), None)

        def subscribe(self, topic, qos):
            self.subscriptions.append(topic)

        def is_connected(self):
            return self.connected

        def disconnect(self):
            self.closed = True
            self.on_disconnect()

        def loop_stop(self):
            pass

        def emit(self, **changes):
            doc = dict(v=1, device_id="test", boot_id="boot", sample_rate_hz=100,
                       units={"acceleration": "m/s2", "gyroscope": "rad/s", "time": "s"},
                       samples=[[t, 0, 0, 9.81, 0, 0, 0] for t in [0, .01, .02]])
            doc.update(changes)
            self.on_message(self, None, SimpleNamespace(retain=False, payload=json.dumps(doc).encode()))

    client = Client()
    config, output = tmp_path/"config.json", tmp_path/"day1.json"
    config.write_text(json.dumps(dict(device_id="test", broker="localhost")))
    monkeypatch.setattr(collect.mqtt, "Client", lambda *args: client)
    monkeypatch.setattr(sys, "argv", ["collect", "--config", str(config), "--user", "one",
                                     "--session", "day1", "--output", str(output)])
    monkeypatch.setattr(sys, "stdin", SimpleNamespace(isatty=lambda: True))
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(collect.time, "sleep", lambda seconds: None)
    return client, output


def script_keys(monkeypatch, client, commands):
    commands = iter(commands)

    def next_key():
        command = next(commands)
        if callable(command):
            command()
            return None
        return command

    monkeypatch.setattr(collect, "read_key", next_key)


def test_start_stop_save_discard_and_repeat(capture, monkeypatch, capsys):
    client, output = capture
    script_keys(monkeypatch, client, [
        client.emit, "v", client.emit, "c", client.emit, "q", "v", "s",
        "v", client.emit, "x", "v", client.emit, "c", "s", "q",
    ])
    collect.main()
    first = json.loads(output.read_text())
    second = json.loads(output.with_name("day1-002.json").read_text())
    assert len(first["samples"]) == len(second["samples"]) == 3
    assert first["session_id"] == second["session_id"] == "day1"
    assert first["recording_id"] != second["recording_id"]
    assert first["boundaries"] == [] and first["synthetic"] is False
    assert not output.with_name("day1-003.json").exists()
    text = capsys.readouterr().out
    assert "Session day1 - 3 samples" in text
    assert "Unsaved recording kept" in text
    assert "Discarded recording 2" in text
    assert "Stop and save or discard" in text
    assert client.closed and client.subscriptions == ["motioncue/test/telemetry"]


@pytest.mark.parametrize("problem", ["empty", "duplicate", "restart", "disconnect", "invalid"])
def test_bad_capture_cannot_be_saved(capture, monkeypatch, capsys, problem):
    client, output = capture
    commands = ["v"]
    if problem != "empty":
        commands.append(client.emit)
    if problem == "duplicate":
        commands.append(client.emit)
    elif problem == "restart":
        commands.append(lambda: client.emit(boot_id="different"))
    elif problem == "disconnect":
        commands.append(lambda: client.on_disconnect())
    elif problem == "invalid":
        commands.append(lambda: client.emit(samples=[[0]*7]*3))
    script_keys(monkeypatch, client, [*commands, "c", "s", "x", "q"])
    collect.main()
    assert not output.exists()
    assert "Cannot save: Capture invalid" in capsys.readouterr().out
    assert client.closed


def test_timed_capture_still_saves(capture, monkeypatch):
    client, output = capture
    monkeypatch.setattr(sys, "argv", [*sys.argv, "--seconds", "1"])
    monkeypatch.setattr(collect.time, "sleep", lambda seconds: client.emit())
    collect.main()
    assert len(json.loads(output.read_text())["samples"]) == 3
    assert client.closed


def test_existing_output_is_preserved(capture):
    client, output = capture
    output.write_text("existing data")
    with pytest.raises(SystemExit):
        collect.main()
    assert output.read_text() == "existing data"


def test_cannot_start_offline(capture, monkeypatch, capsys):
    client, output = capture
    client.connected = False
    script_keys(monkeypatch, client, ["v", "q"])
    collect.main()
    assert "Broker offline" in capsys.readouterr().out
    assert not output.exists()


def test_duration_limit_stops_for_review(capture, monkeypatch, capsys):
    client, output = capture
    clock = [0]
    monkeypatch.setattr(collect.time, "monotonic", lambda: clock[0])
    script_keys(monkeypatch, client, [
        "v", client.emit, lambda: clock.__setitem__(0, 301), "s", "q",
    ])
    collect.main()
    assert len(json.loads(output.read_text())["samples"]) == 3
    assert "300-second limit reached" in capsys.readouterr().out


def test_later_output_collision_keeps_existing_file(capture, monkeypatch, capsys):
    client, output = capture
    later = output.with_name("day1-002.json")
    later.write_text("existing data")
    script_keys(monkeypatch, client, [
        "v", client.emit, "c", "s", "v", client.emit, "c", "s", "q", "x", "q",
    ])
    collect.main()
    assert output.exists() and later.read_text() == "existing data"
    text = capsys.readouterr().out
    assert "Cannot save:" in text and "Unsaved recording kept" in text


def test_synthetic_marker_survives_mixed_batches_and_resets(capture, monkeypatch):
    client, output = capture
    later_batch = [[t, 0, 0, 9.81, 0, 0, 0] for t in (.03, .04, .05)]
    script_keys(monkeypatch, client, [
        "v", lambda: client.emit(synthetic=True),
        lambda: client.emit(samples=later_batch), "c", "s",
        "v", client.emit, "c", "s",
        "v", lambda: client.emit(synthetic=True), "x",
        "v", client.emit, "c", "s", "q",
    ])
    collect.main()
    assert json.loads(output.read_text())["synthetic"] is True
    for number in (2, 3):
        assert json.loads(output.with_name(f"day1-{number:03d}.json").read_text())["synthetic"] is False


def test_failed_write_keeps_capture_and_allows_retry(capture, monkeypatch, capsys):
    client, output = capture
    dump = json.dump

    def failed_dump(doc, stream):
        assert not output.exists()
        stream.write('{"partial":')
        raise OSError("disk full")

    monkeypatch.setattr(collect.json, "dump", failed_dump)

    def retry():
        assert not output.exists()
        assert not list(output.parent.glob("*.partial"))
        monkeypatch.setattr(collect.json, "dump", dump)

    script_keys(monkeypatch, client, ["v", client.emit, "c", "s", retry, "s", "q"])
    collect.main()
    assert len(json.loads(output.read_text())["samples"]) == 3
    assert "disk full" in capsys.readouterr().out
    assert not list(output.parent.glob("*.partial"))


def test_timed_synthetic_capture_is_marked(capture, monkeypatch):
    client, output = capture
    monkeypatch.setattr(sys, "argv", [*sys.argv, "--seconds", "1"])
    monkeypatch.setattr(collect.time, "sleep", lambda seconds: client.emit(synthetic=True))
    collect.main()
    assert json.loads(output.read_text())["synthetic"] is True
