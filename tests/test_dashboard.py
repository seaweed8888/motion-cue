import json
import threading
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from http.server import ThreadingHTTPServer
import pytest
from monitoring.app import make_handler
from monitoring.event_router import Router
from .test_event_routing import Keyboard


def test_local_dashboard_and_mutation_token():
    router=Router("test",Keyboard())
    server=ThreadingHTTPServer(("127.0.0.1",0),make_handler(router))
    thread=threading.Thread(target=server.serve_forever,daemon=True)
    thread.start()
    base=f"http://127.0.0.1:{server.server_port}"
    try:
        with urlopen(base) as response:
            assert b"Your next move" in response.read()
        with urlopen(base+"/api/state") as response:
            state=json.load(response)
        data=json.dumps({"swipe_left":"PageUp","swipe_right":"Space"}).encode()
        with pytest.raises(HTTPError) as error:
            urlopen(Request(base+"/api/mappings",data=data))
        assert error.value.code==403
        request=Request(base+"/api/mappings",data=data,headers={"X-MotionCue-Token":state["token"]})
        with urlopen(request) as response:
            assert json.load(response)["mappings"]["swipe_right"]=="Space"
        with pytest.raises(HTTPError) as error:
            urlopen(Request(base+"/api/state",headers={"Host":"attacker.example"}))
        assert error.value.code==403
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
