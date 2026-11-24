"""Start a loopback MQTT broker for the desktop host when none is listening."""
import asyncio
import ipaddress
import socket


def listening(host, port):
    try:
        with socket.create_connection((host, port), timeout=.3):
            return True
    except OSError:
        return False


def run_with_broker(config, listener):
    host, port = config["broker"], config.get("port", 1883)
    try:
        try:
            local = ipaddress.ip_address(host).is_loopback
        except ValueError:
            local = host.lower() == "localhost"
        if not local or listening(host, port):
            listener.run()
            return
        if config.get("tls") or config.get("username") or config.get("password"):
            raise RuntimeError("Start your configured TLS/authenticated MQTT broker separately; "
                               "automatic startup supports plain loopback connections only")
        asyncio.run(serve(host, port, listener))
    except Exception as exc:
        listener.router.connection(False, error=f"MQTT startup failed: {exc}")


async def serve(host, port, listener):
    # Keep broker imports and startup off the GUI thread and the normal import path.
    from amqtt.broker import Broker
    from amqtt.errors import BrokerError

    address = f"[{host}]" if ":" in host else host
    broker = Broker({
        "listeners": {"default": {"type": "tcp", "bind": f"{address}:{port}"}},
        "plugins": {"amqtt.plugins.authentication.AnonymousAuthPlugin": {"allow_anonymous": True}},
    })
    try:
        await broker.start()
    except (OSError, BrokerError):
        # Another host may have started a broker after our initial check.
        if not listening(host, port):
            raise
        await asyncio.to_thread(listener.run)
        return
    try:
        await asyncio.to_thread(listener.run)
    finally:
        await broker.shutdown()
