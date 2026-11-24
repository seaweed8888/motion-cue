"""Automatic local broker startup, reuse, failure reporting and ownership."""
import socket
import threading

import pytest

from monitoring import local_broker
from monitoring.event_router import Router
from monitoring.mqtt_listener import Listener
from .test_event_routing import Keyboard
from .test_mqtt_integration import wait_for


class StubListener:
    def __init__(self):
        self.router = Router("test", Keyboard())
        self.ran = False

    def run(self):
        self.ran = True


@pytest.mark.parametrize("host", ["mqtt.example.test", "192.0.2.1"])
def test_remote_broker_is_not_started(host, monkeypatch):
    def unexpected(*args):
        raise AssertionError("Remote broker must not be probed or started")

    monkeypatch.setattr(local_broker, "listening", unexpected)
    listener = StubListener()
    local_broker.run_with_broker(dict(broker=host), listener)
    assert listener.ran and listener.router.error is None


def test_existing_broker_is_reused(monkeypatch):
    monkeypatch.setattr(local_broker, "listening", lambda *args: True)
    listener = StubListener()
    local_broker.run_with_broker(dict(broker="localhost", tls=True, username="test"), listener)
    assert listener.ran and listener.router.error is None


@pytest.mark.parametrize("option", [dict(tls=True), dict(username="test"), dict(password="secret")])
def test_secure_configuration_is_not_replaced_by_anonymous_broker(monkeypatch, option):
    monkeypatch.setattr(local_broker, "listening", lambda *args: False)
    listener = StubListener()
    local_broker.run_with_broker(dict(broker="127.0.0.1", **option), listener)
    assert not listener.ran
    assert "separately" in listener.router.error


def test_startup_failure_reaches_dashboard(monkeypatch):
    monkeypatch.setattr(local_broker, "listening", lambda *args: False)

    async def fail(*args):
        raise OSError("port unavailable")

    monkeypatch.setattr(local_broker, "serve", fail)
    listener = StubListener()
    local_broker.run_with_broker(dict(broker="127.0.0.1"), listener)
    assert not listener.ran
    assert "MQTT startup failed: port unavailable" == listener.router.error


def test_real_broker_starts_reuses_and_stops_only_with_its_owner():
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    config = dict(broker="127.0.0.1", port=port, device_id="auto-start-test")
    owner = Listener(config, Router(config["device_id"], Keyboard()))
    other = Listener(config, Router(config["device_id"], Keyboard()))
    owner_thread = threading.Thread(target=local_broker.run_with_broker, args=(config, owner), daemon=True)
    other_thread = threading.Thread(target=local_broker.run_with_broker, args=(config, other), daemon=True)
    owner_thread.start()
    try:
        wait_for(lambda: owner.router.broker)
        other_thread.start()
        wait_for(lambda: other.router.broker)
        other.stop_event.set()
        other_thread.join(3)
        other.close()
        assert not other_thread.is_alive()
        assert local_broker.listening(config["broker"], port)
        assert owner.router.broker
    finally:
        other.stop_event.set()
        if other_thread.ident is not None:
            other_thread.join(3)
        other.close()
        owner.stop_event.set()
        owner_thread.join(5)
        owner.close()
    assert not owner_thread.is_alive()
    assert not local_broker.listening(config["broker"], port)
