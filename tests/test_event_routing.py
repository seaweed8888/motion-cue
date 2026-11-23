import pytest
from monitoring.event_router import Router


class Keyboard:
    enabled = False
    def __init__(self): self.keys = []
    def press(self,key): self.keys.append(key);return "dry-run"


@pytest.fixture
def live():
    now = [100.]
    keyboard = Keyboard()
    router = Router("test",keyboard,lambda:now[0])
    router.connection(True)
    base = dict(v=1,device_id="test",boot_id="boot",armed=False,seq=0,online=True)
    assert router.receive("status",base) == "handshake"
    pulse = router.pulse()
    base.update(session=pulse["session"],lease=pulse["lease"])
    assert router.receive("status",base) == "status"
    return router,base,now,keyboard


def test_twist_swipe_duplicate_disarm(live):
    r,b,now,k = live
    assert r.receive("events",dict(b,seq=1,gesture="swipe_right")) == "suppressed"
    assert r.receive("events",dict(b,seq=2,gesture="twist",armed=True)) == "mode-change"
    event = dict(b,seq=3,gesture="swipe_right",armed=True)
    assert r.receive("events",event) == "dry-run"
    assert r.receive("events",event) == "duplicate"
    r.receive("events",dict(b,seq=4,gesture="twist",armed=False))
    assert r.receive("events",dict(b,seq=5,gesture="swipe_right",armed=True)) == "suppressed"
    assert k.keys == ["Right"]


def test_expired_retained_reconnect(live):
    r,b,now,k = live
    assert r.receive("events",dict(b,seq=1,gesture="twist",armed=True),True) == "invalid"
    now[0] += 1.21
    assert r.receive("events",dict(b,seq=2,gesture="twist",armed=True)) == "stale"
    r.connection(False)
    r.connection(True)
    assert r.receive("events",dict(b,seq=3,gesture="swipe_right",armed=True)) == "stale"
    assert not r.armed and not k.keys


def test_pending_disarm_blocks_swipes_and_ack(live):
    r,b,now,k = live
    r.receive("events",dict(b,seq=1,gesture="twist",armed=True))
    command = r.command(False)
    assert r.receive("events",dict(b,seq=2,gesture="swipe_left",armed=True)) == "suppressed"
    r.receive("status",dict(b,seq=3,command_id=command["id"],armed=False))
    assert r.pending is None and not r.armed and not k.keys


def test_remap_and_timeout(live):
    r,b,now,k = live
    with pytest.raises(ValueError):r.remap({"swipe_left":"shell","swipe_right":"Right"})
    r.remap({"swipe_left":"PageUp","swipe_right":"Space"})
    r.receive("events",dict(b,seq=1,gesture="twist",armed=True))
    r.receive("events",dict(b,seq=2,gesture="swipe_left",armed=True))
    assert k.keys == ["PageUp"]
    now[0] += 1.6
    r.pulse()
    assert not r.online and not r.armed


@pytest.mark.parametrize("change",[{"seq":True},{"armed":"true"},{"v":7},{"gesture":"execute"}])
def test_malformed(live,change):
    r,b,now,k = live
    assert r.receive("events",{**b,"seq":1,"gesture":"twist",**change}) == "invalid"
