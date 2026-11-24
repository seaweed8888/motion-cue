"""Exercise the Windows input structures with every OS call replaced."""
import ctypes
import sys
from types import SimpleNamespace

import pytest
from monitoring import keyboard_output
from .test_event_routing import live


@pytest.mark.skipif(sys.platform != "win32", reason="Windows input ABI")
@pytest.mark.parametrize("accepted", [0, 1, 2])
@pytest.mark.parametrize("key", ["Right", "Space"])
def test_key_pair_and_failed_input_disarm(monkeypatch, live, accepted, key):
    calls = []

    def send(count, inputs, size):
        rows = list(inputs) if count == 2 else [inputs._obj]
        calls.append((count, size, [(row.type, row.u.ki.wVk, row.u.ki.dwFlags)
                                    for row in rows]))
        return accepted if count == 2 else 1

    monkeypatch.setattr(keyboard_output.ctypes, "WinDLL",
                        lambda *args, **kwargs: SimpleNamespace(SendInput=send))
    router, base, now, keyboard = live
    router.keyboard = keyboard_output.Keyboard(enabled=True)
    router.remap({"swipe_left": "Left", "swipe_right": key})
    router.receive("events", dict(base, seq=1, gesture="twist", armed=True))
    session = router.session
    outcome = router.receive("events", dict(base, seq=2, gesture="swipe_right", armed=True))
    extended = 0 if key == "Space" else 1
    vk = keyboard_output.KEYS[key]
    size = 40 if ctypes.sizeof(ctypes.c_void_p) == 8 else 28
    assert calls[0] == (2, size, [(1, vk, extended), (1, vk, extended | 2)])
    if accepted == 2:
        assert outcome == "executed" and len(calls) == 1
        assert router.online and router.armed
    else:
        assert calls[1] == (1, size, [(1, vk, extended | 2)])
        assert outcome == "input-error"
        assert not router.online and not router.armed
        assert router.session != session and not router.leases
        assert router.history[0]["outcome"] == "input-error"
