"""Manual MQTT fixture, not an IMU/classifier. Run only with host dry-run first."""
import argparse
import json
from pathlib import Path
import threading
import time
import uuid
import paho.mqtt.client as mqtt


class Simulator:
    def __init__(self, config):
        self.device = config["device_id"]
        self.boot = uuid.uuid4().hex
        self.session = self.lease = self.command_id = ""
        self.armed = False
        self.seq = 0
        self.last = 0
        self.lock = threading.RLock()
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        if config.get("username"):
            self.client.username_pw_set(config["username"],config.get("password"))
        if config.get("tls"):
            self.client.tls_set()
        self.client.on_connect = self.connected
        self.client.on_disconnect = self.disconnected
        self.client.on_message = self.control
        self.config = config

    def connected(self,c,u,f,reason,p):
        if not reason.is_failure:
            c.subscribe(f"motionlink/{self.device}/control",0)
            self.publish("status")

    def disconnected(self,*args):
        with self.lock:
            self.armed=False
            self.session=self.lease=self.command_id=""

    def publish(self,kind,gesture=None):
        with self.lock:
            self.seq+=1
            doc=dict(v=1,device_id=self.device,boot_id=self.boot,seq=self.seq,
                session=self.session,lease=self.lease,armed=self.armed,online=True,
                command_id=self.command_id,model_version="MANUAL-FIXTURE",synthetic=True)
            if gesture:doc["gesture"]=gesture
            self.client.publish(f"motionlink/{self.device}/{kind}",json.dumps(doc),qos=0,retain=False)

    def control(self,c,u,msg):
        try:
            doc=json.loads(msg.payload)
            if msg.retain or doc["v"]!=1 or doc["device_id"]!=self.device:return
            with self.lock:
                if doc["session"]!=self.session:
                    self.armed=False
                    self.command_id=""
                self.session,self.lease=doc["session"],doc["lease"]
                self.last=time.monotonic()
                command=doc.get("command")
                if command and command["id"]!=self.command_id:
                    if type(command["armed"]) is not bool:return
                    self.command_id,self.armed=command["id"],command["armed"]
                self.publish("status")
        except (ValueError,TypeError,KeyError):return

    def gesture(self,label):
        with self.lock:
            if time.monotonic()-self.last>1.2:
                self.disconnected()
                return
            if label=="twist":self.armed=not self.armed
            self.publish("events",label)

    def start(self):
        self.client.connect(self.config["broker"],self.config.get("port",1883),5)
        self.client.loop_start()

    def close(self):
        self.client.disconnect()
        self.client.loop_stop()


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--config",default="monitoring/config.example.json")
    args=parser.parse_args()
    sim=Simulator(json.loads(Path(args.config).read_text()))
    sim.start()
    try:
        print("MANUAL FIXTURE: type twist, swipe_left, swipe_right, other; Ctrl+C exits")
        while True:
            label=input("> ").strip()
            if label in ("twist","swipe_left","swipe_right","other"):sim.gesture(label)
    except (KeyboardInterrupt,EOFError):pass
    finally:sim.close()


if __name__=="__main__":main()
