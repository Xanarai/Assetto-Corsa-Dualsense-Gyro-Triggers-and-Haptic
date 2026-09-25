"""
Windows Keyboard Event Sender for DualSense AC Bridge.
Simulates keypresses using Windows SendInput API and keybd_event.
Specifically maps controller inputs (e.g., D-Pad Right) to keyboard keys (e.g., F10).
"""

import ctypes
import logging

logger = logging.getLogger("DualSenseACBridge.KeySender")

VK_F10 = 0x79
SCAN_F10 = 0x44

KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_SCANCODE = 0x0008
INPUT_KEYBOARD = 1

PUL = ctypes.POINTER(ctypes.c_ulong)


class KeyBdInput(ctypes.Structure):
    _fields_ = [
        ("wVk", ctypes.c_ushort),
        ("wScan", ctypes.c_ushort),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", PUL)
    ]


class HardwareInput(ctypes.Structure):
    _fields_ = [
        ("uMsg", ctypes.c_ulong),
        ("wParamL", ctypes.c_short),
        ("wParamH", ctypes.c_ushort)
    ]


class MouseInput(ctypes.Structure):
    _fields_ = [
        ("dx", ctypes.c_long),
        ("dy", ctypes.c_long),
        ("mouseData", ctypes.c_ulong),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", PUL)
    ]


class Input_I(ctypes.Union):
    _fields_ = [
        ("ki", KeyBdInput),
        ("mi", MouseInput),
        ("hi", HardwareInput)
    ]


class INPUT(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.c_ulong),
        ("ii", Input_I)
    ]


def send_f10_key(down: bool = True):
    """
    Sends F10 keypress (down=True) or release (down=False) using Windows SendInput & keybd_event.
    Compatible with DirectX games, RawInput, DirectInput, and standard Windows message loops.
    """
    try:
        user32 = ctypes.windll.user32
        flags = 0 if down else KEYEVENTF_KEYUP

        # 1. Primary: SendInput with both virtual key code and hardware scan code
        extra = ctypes.c_ulong(0)
        ii = Input_I()
        ii.ki = KeyBdInput(VK_F10, SCAN_F10, flags, 0, ctypes.pointer(extra))
        inp = INPUT(ctypes.c_ulong(INPUT_KEYBOARD), ii)
        user32.SendInput(1, ctypes.pointer(inp), ctypes.sizeof(INPUT))

        # 2. Secondary fallback: keybd_event for legacy/DirectInput hooks
        user32.keybd_event(VK_F10, SCAN_F10, flags, 0)

        logger.debug(f"F10 key {'DOWN' if down else 'UP'} sent successfully.")
    except Exception as e:
        logger.warning(f"Failed to send F10 keyboard event: {e}")
