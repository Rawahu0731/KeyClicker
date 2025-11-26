"""
fast_input.py
クロスプラットフォームの高速キー送信モジュール。
- Linux: evdev + uinput を使って直接注入
- Windows: keybd_event (WinAPI) を使って注入
Linux は root または /dev/uinput へのアクセス権が必要です。
"""
def _keycode_from_name(name: str):
import platform
import sys

PLATFORM = platform.system().lower()

if PLATFORM == 'linux':
    try:
        from evdev import UInput, ecodes as e
    except Exception:
        UInput = None
        e = None

    def _keycode_from_name(name: str):
        n = name.lower()
        if len(n) == 1 and 'a' <= n <= 'z':
            return getattr(e, 'KEY_' + n.upper())
        if len(n) == 1 and '0' <= n <= '9':
            return getattr(e, 'KEY_' + n)
        if n == 'space':
            return e.KEY_SPACE
        if n in ('enter', 'return'):
            return e.KEY_ENTER
        if n == 'tab':
            return e.KEY_TAB
        if n == 'esc' or n == 'escape':
            return e.KEY_ESC
        if n == 'backspace':
            return e.KEY_BACKSPACE
        # 矢印キー
        if n == 'left':
            return e.KEY_LEFT
        if n == 'right':
            return e.KEY_RIGHT
        if n == 'up':
            return e.KEY_UP
        if n == 'down':
            return e.KEY_DOWN
        attr = 'KEY_' + n.upper()
        return getattr(e, attr, None)

    class FastKeySender:
        def __init__(self, keys):
            if UInput is None:
                raise RuntimeError('evdev not available')
            self.keys = keys
            self.keycodes = []
            for k in keys:
                code = _keycode_from_name(k)
                if code is None:
                    raise ValueError(f"Unsupported key name: {k}")
                self.keycodes.append(code)
            caps = {e.EV_KEY: list(set(self.keycodes))}
            self.ui = UInput(caps, name="keyclicker-uinput")

        def press(self, key_name):
            code = _keycode_from_name(key_name)
            if code is None:
                raise ValueError(f"Unsupported key name: {key_name}")
            self.ui.write(e.EV_KEY, code, 1)
            self.ui.syn()
            self.ui.write(e.EV_KEY, code, 0)
            self.ui.syn()

        def close(self):
            try:
                self.ui.close()
            except Exception:
                pass

elif PLATFORM == 'windows':
    import ctypes
    from ctypes import wintypes

    # constants for keybd_event / SendInput
    KEYEVENTF_KEYUP = 0x0002

    # 简易 mapping of names to virtual-key codes
    VK_MAP = {}
    for c in range(ord('A'), ord('Z')+1):
        VK_MAP[chr(c).lower()] = c
    for n in range(0, 10):
        VK_MAP[str(n)] = ord(str(n))
    VK_MAP.update({
        'space': 0x20,
        'enter': 0x0D, 'return': 0x0D,
        'tab': 0x09,
        'esc': 0x1B, 'escape': 0x1B,
        'backspace': 0x08,
        'left': 0x25, 'up': 0x26, 'right': 0x27, 'down': 0x28,
    })

    def _vk_from_name(name: str):
        return VK_MAP.get(name.lower())

    class FastKeySender:
        def __init__(self, keys):
            # keys is used only for validation here
            for k in keys:
                if _vk_from_name(k) is None:
                    raise ValueError(f"Unsupported key name for Windows: {k}")

        def press(self, key_name):
            vk = _vk_from_name(key_name)
            if vk is None:
                raise ValueError(f"Unsupported key name for Windows: {key_name}")
            # key down
            ctypes.windll.user32.keybd_event(vk, 0, 0, 0)
            # key up
            ctypes.windll.user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)

        def close(self):
            return

else:
    # Unsupported platform: provide a stub that raises on use
    class FastKeySender:
        def __init__(self, keys):
            raise RuntimeError(f'fast_input not supported on {PLATFORM}')

