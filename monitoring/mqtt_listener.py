import json
import threading
import paho.mqtt.client as mqtt


class Listener:
    def __init__(self, config, router):
        self.config, self.router = config, router
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

    def on_connect(self, client, userdata, flags, reason, properties):
        self.router.connection(not reason.is_failure)
        if not reason.is_failure:
            client.subscribe([(self.topic + "status", 0), (self.topic + "events", 0)])

    def on_message(self, client, userdata, message):
        if len(message.payload) > 8192:
            return
        try:
            msg = json.loads(message.payload)
            self.router.receive(message.topic.rsplit("/", 1)[-1], msg, message.retain)
        except (ValueError, TypeError, KeyError):
            return

    def run(self):
        self.client.connect_async(self.config["broker"], self.config.get("port", 1883), 5)
        self.client.loop_start()
        while not self.stop_event.wait(0.4):
            pulse = self.router.pulse()
            if self.client.is_connected():
                self.client.publish(self.topic + "control", json.dumps(pulse), qos=0, retain=False)

    def close(self):
        self.stop_event.set()
        self.router.connection(False)
        self.client.disconnect()
        self.client.loop_stop()
