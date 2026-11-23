"""Real local MQTT broker + both clients. Never inject keyboard events."""
import asyncio
import socket
import threading
import time
from amqtt.broker import Broker
from monitoring.event_router import Router
from monitoring.mqtt_listener import Listener
from shared.examples.simulate import Simulator
from .test_event_routing import Keyboard


def wait_for(predicate):
    until=time.monotonic()+8
    while time.monotonic()<until:
        if predicate():return
        time.sleep(.02)
    raise AssertionError("MQTT integration timed out")


def test_real_broker_handshake_keys_and_disconnect():
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1",0))
        port=reservation.getsockname()[1]
    loop=asyncio.new_event_loop()
    thread=threading.Thread(target=loop.run_forever,daemon=True)
    thread.start()
    async def start():
        broker=Broker({"listeners":{"default":{"type":"tcp","bind":f"127.0.0.1:{port}"}},
                       "plugins":{"amqtt.plugins.authentication.AnonymousAuthPlugin":{"allow_anonymous":True}}})
        await broker.start()
        return broker
    broker=asyncio.run_coroutine_threadsafe(start(),loop).result(8)
    config=dict(device_id="integration",broker="127.0.0.1",port=port)
    keyboard=Keyboard()
    router=Router("integration",keyboard)
    listener=Listener(config,router)
    host=threading.Thread(target=listener.run,daemon=True)
    host.start()
    device=Simulator(config)
    try:
        device.start()
        wait_for(lambda:router.online)
        assert not router.armed
        device.gesture("twist")
        wait_for(lambda:router.armed)
        device.gesture("swipe_right")
        wait_for(lambda:keyboard.keys==["Right"])
        router.command(False)
        wait_for(lambda:router.pending is None and not router.armed)
        device.gesture("swipe_left")
        wait_for(lambda:any(e["gesture"]=="swipe_left" for e in router.history))
        assert keyboard.keys==["Right"]
        device.close()
        wait_for(lambda:not router.online)
        assert not router.armed
    finally:
        device.close()
        listener.close()
        host.join(3)
        asyncio.run_coroutine_threadsafe(broker.shutdown(),loop).result(8)
        loop.call_soon_threadsafe(loop.stop)
        thread.join(3)
        loop.close()
