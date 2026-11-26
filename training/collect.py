"""Record MQTT acquisition timestamps; annotate boundaries after capture."""
import argparse
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import uuid
import paho.mqtt.client as mqtt
from .features import validate


def read_key():
    import msvcrt
    return msvcrt.getwch().lower() if msvcrt.kbhit() else None


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--config", default="monitoring/config.example.json")
    p.add_argument("--user", required=True)
    p.add_argument("--session", required=True)
    p.add_argument("--seconds", type=float, help="Timed capture instead of interactive controls (max 300)")
    p.add_argument("--output", required=True)
    args = p.parse_args()
    if args.seconds is not None and not 0 < args.seconds <= 300:
        p.error("Capture duration must be between 0 and 300 seconds")
    if args.seconds is None and (sys.platform != "win32" or not sys.stdin.isatty()):
        p.error("Interactive capture requires a Windows terminal; use --seconds for timed capture")
    output = Path(args.output)
    if output.exists():
        p.error(f"Output already exists: {output}")
    config = json.loads(Path(args.config).read_text())
    samples, metadata, failures = [], {}, []
    synthetic = False
    lock = threading.Lock()
    state = "recording" if args.seconds is not None else "idle"
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    if config.get("username"):
        client.username_pw_set(config["username"], config.get("password"))
    if config.get("tls"):
        client.tls_set()
    def connected(c, u, f, reason, props):
        if not reason.is_failure:
            c.subscribe(f"motioncue/{config['device_id']}/telemetry", qos=0)
    def received(c, u, msg):
        nonlocal synthetic
        with lock:
            if state != "recording":
                return
            try:
                if msg.retain or len(msg.payload) > 65536:
                    raise ValueError("Retained/oversize telemetry")
                doc = json.loads(msg.payload)
                if doc["v"] != 1 or doc["device_id"] != config["device_id"]:
                    raise ValueError("Wrong telemetry version/device")
                batch = validate(doc["samples"])
                meta = {k:doc[k] for k in ("boot_id", "sample_rate_hz", "units")}
                if metadata and metadata != meta:
                    raise ValueError("Device restarted or metadata changed")
                metadata.update(meta)
                if samples and batch[0,0] <= samples[-1][0]:
                    raise ValueError("Nonmonotonic acquisition timestamps")
                samples.extend(batch.tolist())
                synthetic |= bool(doc.get("synthetic", False))
            except (ValueError, KeyError, TypeError) as exc:
                if not failures:
                    failures.append(str(exc))

    def disconnected(*unused):
        with lock:
            if state == "recording" and not failures:
                failures.append("MQTT disconnected during capture; discard and record again")

    def save(number):
        if failures or not samples:
            raise ValueError(f"Capture invalid: {failures or 'no telemetry received'}")
        doc = dict(metadata, user_id=args.user, session_id=args.session,
                   recording_id=uuid.uuid4().hex, samples=samples, boundaries=[], synthetic=synthetic)
        path = output if number == 1 else output.with_name(f"{output.stem}-{number:03d}{output.suffix}")
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                                 suffix=".partial", delete=False)
        try:
            with temporary as stream:
                json.dump(doc, stream)
            # Publish the complete file atomically without replacing an existing recording.
            if os.name == "nt":
                os.rename(temporary.name, path)
            else:
                os.link(temporary.name, path)
        finally:
            Path(temporary.name).unlink(missing_ok=True)
        print(f"Saved {len(samples)} samples to {path}. Add labeled boundaries before preprocessing.")

    client.on_connect, client.on_message = connected, received
    client.on_disconnect = disconnected
    client.connect(config["broker"], config.get("port",1883), 5)
    client.loop_start()
    try:
        if args.seconds is not None:
            print(f"Session {args.session} - collecting for {args.seconds:g} seconds...")
            time.sleep(args.seconds)
            with lock:
                state = "review"
                save(1)
            return
        print(f"Session {args.session} | User {args.user}")
        print("V start | C stop | S save stopped recording | X discard | Q quit (no Enter needed)")
        print("Ready. Start telemetry on the device, then press V. Maximum recording: 300 seconds.")
        number, started, last_count = 1, 0, -1
        while True:
            try:
                time.sleep(.1)
                key = read_key()
            except KeyboardInterrupt:
                key = "q"
            with lock:
                if state == "recording" and time.monotonic() - started >= 300:
                    print("\n300-second limit reached; recording stopped for review.")
                    key = "c"
                if key == "v":
                    if state != "idle":
                        print("\nStop and save or discard the current recording first.")
                    elif not client.is_connected():
                        print("\nBroker offline. Waiting for connection; press V to retry.")
                    else:
                        state, started, last_count = "recording", time.monotonic(), -1
                        print(f"\nRecording {number} started. C stop | X discard")
                elif key == "c" and state == "recording":
                    state = "review"
                    print(f"\nSession {args.session} - {len(samples)} samples (recording {number}, stopped)")
                    if failures:
                        print(f"Invalid capture: {failures[0]}")
                    print("S save | X discard")
                elif key == "s" and state == "review":
                    try:
                        save(number)
                    except (ValueError, OSError) as exc:
                        print(f"Cannot save: {exc}. Recording kept; retry S or discard with X.")
                    else:
                        number += 1
                        samples.clear()
                        metadata.clear()
                        failures.clear()
                        synthetic = False
                        state = "idle"
                        print("Ready. V start | Q quit")
                elif key == "x" and state != "idle":
                    print(f"\nDiscarded recording {number} ({len(samples)} samples). No file saved.")
                    samples.clear()
                    metadata.clear()
                    failures.clear()
                    synthetic = False
                    state = "idle"
                    print("Ready. V start | Q quit")
                elif key == "q":
                    if state == "idle":
                        break
                    print("\nUnsaved recording kept. C stop, then S save; or X discard before quitting.")
                if state == "recording" and len(samples) != last_count:
                    last_count = len(samples)
                    print(f"\rSession {args.session} - {last_count} samples (recording {number})", end="", flush=True)
    finally:
        with lock:
            state = "idle"
        client.disconnect()
        client.loop_stop()


if __name__ == "__main__":
    main()
