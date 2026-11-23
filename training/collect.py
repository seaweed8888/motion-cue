"""Record MQTT acquisition timestamps; annotate boundaries after capture."""
import argparse
import json
from pathlib import Path
import threading
import time
import uuid
import paho.mqtt.client as mqtt
from .features import validate


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--config", default="monitoring/config.example.json")
    p.add_argument("--user", required=True)
    p.add_argument("--session", required=True)
    p.add_argument("--seconds", type=float, default=30)
    p.add_argument("--output", required=True)
    args = p.parse_args()
    if not 0 < args.seconds <= 300:
        p.error("Capture duration must be between 0 and 300 seconds")
    config = json.loads(Path(args.config).read_text())
    samples, metadata, failures = [], {}, []
    lock = threading.Lock()
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    if config.get("username"):
        client.username_pw_set(config["username"], config.get("password"))
    if config.get("tls"):
        client.tls_set()
    def connected(c, u, f, reason, props):
        if not reason.is_failure:
            c.subscribe(f"motionlink/{config['device_id']}/telemetry", qos=0)
    def received(c, u, msg):
        try:
            if msg.retain or len(msg.payload) > 65536:
                raise ValueError("Retained/oversize telemetry")
            doc = json.loads(msg.payload)
            if doc["v"] != 1 or doc["device_id"] != config["device_id"]:
                raise ValueError("Wrong telemetry version/device")
            batch = validate(doc["samples"])
            with lock:
                meta = {k:doc[k] for k in ("boot_id", "sample_rate_hz", "units")}
                if metadata and metadata != meta:
                    raise ValueError("Device restarted or metadata changed")
                metadata.update(meta)
                if samples and batch[0,0] <= samples[-1][0]:
                    raise ValueError("Nonmonotonic acquisition timestamps")
                samples.extend(batch.tolist())
        except (ValueError, KeyError, TypeError) as exc:
            failures.append(str(exc))
    client.on_connect, client.on_message = connected, received
    client.connect(config["broker"], config.get("port",1883), 5)
    client.loop_start()
    try:
        time.sleep(args.seconds)
    finally:
        client.disconnect()
        client.loop_stop()
    if failures or not samples:
        raise RuntimeError(f"Capture invalid: {failures or 'no telemetry received'}")
    doc = dict(metadata, user_id=args.user, session_id=args.session,
               recording_id=uuid.uuid4().hex, samples=samples, boundaries=[], synthetic=False)
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as f:
        json.dump(doc, f)
    print("Saved continuous recording. Add labeled boundaries before preprocessing.")


if __name__ == "__main__":
    main()
