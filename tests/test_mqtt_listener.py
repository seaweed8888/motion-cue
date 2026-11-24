from unittest.mock import Mock

import pytest
import paho.mqtt.client as mqtt
from monitoring.event_router import Router
from monitoring.mqtt_listener import Listener
from .test_event_routing import Keyboard, live
from types import SimpleNamespace
import json


@pytest.mark.parametrize("settings", [
    {}, {"broker": ""}, {"broker": " "}, {"broker": 123},
    {"broker": "localhost", "port": 0}, {"broker": "localhost", "port": 65536},
    {"broker": "localhost", "port": "1883"}, {"broker": "localhost", "port": True},
])
def test_invalid_broker_settings_fail_before_worker(settings):
    with pytest.raises(ValueError, match="broker|port"):
        Listener(settings, Router("test", Keyboard()))


@pytest.mark.parametrize("failure", ["exception", "return-code", "publish"])
def test_worker_failure_disarms_and_reports_error(monkeypatch, live, failure):
    router, base, now, keyboard = live
    router.receive("events", dict(base, seq=1, gesture="twist", armed=True))
    router.command(False)
    listener = Listener({"broker": "localhost"}, router)
    start = Mock(return_value=mqtt.MQTT_ERR_SUCCESS)
    if failure == "exception":
        start.side_effect = RuntimeError("network startup failed")
    elif failure == "return-code":
        start.return_value = mqtt.MQTT_ERR_INVAL
    else:
        monkeypatch.setattr(listener.stop_event, "wait", Mock(return_value=False))
        monkeypatch.setattr(listener.client, "is_connected", Mock(return_value=True))
        monkeypatch.setattr(listener.client, "publish", Mock(side_effect=OSError("publish failed")))
    monkeypatch.setattr(listener.client, "loop_start", start)
    disconnect, stop = Mock(), Mock()
    monkeypatch.setattr(listener.client, "disconnect", disconnect)
    monkeypatch.setattr(listener.client, "loop_stop", stop)
    listener.run()
    state = router.snapshot()
    assert state["error"].startswith("MQTT worker stopped:")
    assert not state["broker"] and not state["online"] and not state["armed"]
    assert state["pending"] is None and listener.stop_event.is_set()
    disconnect.assert_called_once()
    stop.assert_called_once()


def test_telemetry_subscription_routing_and_size_limit():
    handler = Mock()
    router = Router("test", Keyboard())
    listener = Listener({"broker": "localhost"}, router, telemetry=handler)
    client = Mock()
    listener.on_connect(client, None, None, SimpleNamespace(is_failure=False), None)
    client.subscribe.assert_any_call("motioncue/test/telemetry", 0)
    doc = {"v": 1, "device_id": "test", "samples": [0]*3000}
    payload = json.dumps(doc).encode()
    assert 8192 < len(payload) < 65536
    listener.on_message(client, None, SimpleNamespace(topic="motioncue/test/telemetry", payload=payload, retain=False))
    handler.assert_called_with(doc, False)
    listener.on_message(client, None, SimpleNamespace(topic="motioncue/test/telemetry", payload=b"x"*65537, retain=False))
    handler.assert_called_with(None, False)
    listener.on_message(client, None, SimpleNamespace(topic="motioncue/test/telemetry", payload=b"bad json", retain=False))
    handler.assert_called_with(None, False)
