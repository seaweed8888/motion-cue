"""Native Windows foreground input. AI-assisted implementation; validate on target apps."""
import ctypes
import sys
from ctypes import wintypes

KEYS = {"Left": 0x25, "Right": 0x27, "Up": 0x26, "Down": 0x28,
        "PageUp": 0x21, "PageDown": 0x22, "Space": 0x20}


class Keyboard:
    def __init__(self, enabled=False):
        self.enabled = enabled
        if enabled and sys.platform != "win32":
            raise RuntimeError("Keyboard output requires a native Windows process")

    def press(self, key):
        vk = KEYS[key]
        if not self.enabled:
            return "dry-run"
        class KEYBDINPUT(ctypes.Structure):
            _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD),
                        ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD),
                        ("dwExtraInfo", ctypes.c_size_t)]
        class MOUSEINPUT(ctypes.Structure):
            _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG),
                        ("mouseData", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
                        ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_size_t)]
        class UNION(ctypes.Union):
            _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT)]
        class INPUT(ctypes.Structure):
            _fields_ = [("type", wintypes.DWORD), ("u", UNION)]
        send = ctypes.WinDLL("user32", use_last_error=True).SendInput
        send.argtypes = [wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
        send.restype = wintypes.UINT
        extended = 1 if key != "Space" else 0
        pair = (INPUT * 2)(INPUT(1, UNION(ki=KEYBDINPUT(vk, 0, extended, 0, 0))),
                           INPUT(1, UNION(ki=KEYBDINPUT(vk, 0, extended | 2, 0, 0))))
        if send(2, pair, ctypes.sizeof(INPUT)) != 2:
            send(1, ctypes.byref(pair[1]), ctypes.sizeof(INPUT))
            raise OSError("SendInput failed; check foreground app permissions")
        return "executed"
