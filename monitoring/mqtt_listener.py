import json
import threading
import paho.mqtt.client as mqtt


class Listener:
    def __init__(self, config, router, telemetry=None):
        if not isinstance(config.get("broker"), str) or not config["broker"].strip():
            raise ValueError("broker must be a nonempty hostname or IP address")
        port = config.get("port", 1883)
        if type(port) is not int or not 1 <= port <= 65535:
            raise ValueError("port must be an integer between 1 and 65535")
        self.config, self.router = config, router
        self.telemetry = telemetry
        self.topic = f"motioncue/{router.device_id}/"
        self.stop_event = threading.Event()
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, clean_session=True)
        if config.get("username"):
            self.client.username_pw_set(config["username"], config.get("password"))
        if config.get("tls"):
            self.client.tls_set()
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = lambda *args: router.connection(False)
        self.client.on_message = self.on_message
        self.client.max_queued_messages_set(4)
        self.client.connect_async(config["broker"], port, 5)

    def on_connect(self, client, userdata, flags, reason, properties):
        self.router.connection(not reason.is_failure)
        if not reason.is_failure:
            client.subscribe([(self.topic + "status", 0), (self.topic + "events", 0)])
            if self.telemetry is not None:
                client.subscribe(self.topic + "telemetry", 0)

    def on_message(self, client, userdata, message):
        kind = message.topic.rsplit("/", 1)[-1]
        if len(message.payload) > (65536 if kind == "telemetry" else 8192):
            if kind == "telemetry" and self.telemetry is not None:
                self.telemetry(None, message.retain)
            return
        try:
            msg = json.loads(message.payload)
            if kind == "telemetry" and self.telemetry is not None:
                self.telemetry(msg, message.retain)
            else:
                self.router.receive(kind, msg, message.retain)
        except (ValueError, TypeError, KeyError):
            if kind == "telemetry" and self.telemetry is not None:
                self.telemetry(None, message.retain)
            return

    def run(self):
        try:
            if self.client.loop_start() != mqtt.MQTT_ERR_SUCCESS:
                raise RuntimeError("Could not start MQTT network loop")
            while not self.stop_event.wait(0.4):
                pulse = self.router.pulse()
                if self.client.is_connected():
                    self.client.publish(self.topic + "control", json.dumps(pulse), qos=0, retain=False)
        except Exception as exc:
            self.close()
            self.router.connection(False, error=f"MQTT worker stopped: {exc}")

    def close(self):
        self.stop_event.set()
        self.router.connection(False)
        self.client.disconnect()
        self.client.loop_stop()
