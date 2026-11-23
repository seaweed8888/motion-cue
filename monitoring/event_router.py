"""Session/lease checks use host monotonic time, never device uptime subtraction."""
from collections import deque
import threading
import time
import uuid
from .keyboard_output import KEYS


class Router:
    def __init__(self, device_id, keyboard, clock=time.monotonic):
        self.device_id, self.keyboard, self.clock = device_id, keyboard, clock
        self.lock = threading.RLock()
        self.history = deque(maxlen=100)
        self.mappings = {"swipe_left": "Left", "swipe_right": "Right"}
        self.broker = False
        self.boot = None
        self.reset()

    def reset(self):
        self.session = uuid.uuid4().hex
        self.leases = {}
        self.armed = self.online = False
        self.pending = None
        self.last_seen = 0
        self.sequence = -1

    def connection(self, connected):
        with self.lock:
            self.broker = connected
            self.reset()

    def pulse(self):
        with self.lock:
            now = self.clock()
            if self.online and now - self.last_seen > 1.5:
                self.reset()
            self.leases = {k: t for k, t in self.leases.items() if now-t <= 1.2}
            lease = uuid.uuid4().hex
            self.leases[lease] = now
            return dict(v=1, device_id=self.device_id, session=self.session,
                        lease=lease, command=self.pending)

    def command(self, armed):
        if type(armed) is not bool:
            raise ValueError("armed must be boolean")
        with self.lock:
            if not self.online:
                raise ValueError("Device is offline")
            self.pending = dict(id=uuid.uuid4().hex, armed=armed)
            return self.pending

    def remap(self, mappings):
        if (not isinstance(mappings, dict) or set(mappings) != set(self.mappings)
                or any(v not in KEYS for v in mappings.values())):
            raise ValueError("Supply both swipes with allowed presentation keys")
        with self.lock:
            self.mappings = mappings.copy()

    def receive(self, kind, msg, retained=False):
        with self.lock:
            if retained or not isinstance(msg, dict) or not self.broker:
                return "invalid"
            if type(msg.get("v")) is not int or msg["v"] != 1 or msg.get("device_id") != self.device_id:
                return "invalid"
            boot = msg.get("boot_id")
            if not isinstance(boot, str) or not 1 <= len(boot) <= 128:
                return "invalid"
            if kind == "status" and boot != self.boot:
                self.boot = boot
                self.reset()
                return "handshake"
            now = self.clock()
            if not isinstance(msg.get("lease"), str) or not isinstance(msg.get("session"), str):
                return "invalid"
            issued = self.leases.get(msg.get("lease"))
            if (boot != self.boot or msg.get("session") != self.session
                    or issued is None or now - issued > 1.2):
                return "stale"
            seq = msg.get("seq")
            if type(seq) is not int or seq < 0:
                return "invalid"
            if seq <= self.sequence:
                return "duplicate"
            if type(msg.get("armed")) is not bool:
                return "invalid"
            if kind not in ("status", "events"):
                return "invalid"
            if kind == "events" and msg.get("gesture") not in ("twist", "other", *self.mappings):
                return "invalid"
            self.sequence = seq
            if kind == "status":
                if msg.get("online") is not True:
                    self.reset()
                    return "offline"
                # A new session can only become live after an acknowledged disarm.
                if not self.online and msg["armed"]:
                    return "awaiting-disarm"
                self.online, self.last_seen = True, now
                self.armed = msg["armed"]
                if self.pending and msg.get("command_id") == self.pending["id"]:
                    if self.armed == self.pending["armed"]:
                        self.pending = None
                return "status"
            gesture = msg["gesture"]
            outcome, key = "suppressed", None
            if gesture == "twist":
                self.armed = msg["armed"]
                outcome = "mode-change"
            elif gesture == "other":
                outcome = "rejected"
            elif (self.online and now-self.last_seen <= 1.5 and self.armed
                  and msg["armed"] and self.pending is None):
                key = self.mappings[gesture]
                try:
                    outcome = self.keyboard.press(key)
                except OSError:
                    self.reset()
                    outcome = "input-error"
            if not msg["armed"]:
                self.armed = False
            self.history.appendleft(dict(gesture=gesture, outcome=outcome, key=key,
                                         seq=seq, time=time.strftime("%H:%M:%S")))
            return outcome

    def snapshot(self):
        with self.lock:
            return dict(broker=self.broker, online=self.online, armed=self.armed,
                        pending=self.pending, mappings=self.mappings.copy(),
                        history=list(self.history), keyboard_enabled=self.keyboard.enabled)
