"""
fast_input.py
Linux 向けに /dev/uinput を使ってキーボード入力を直接注入するモジュール。
root 権限または uinput グループの許可が必要です。
"""
from evdev import UInput, ecodes as e

# 簡易マッピング: 英字、数字、space, enter
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
    # デフォルト: try lookup KEY_{NAME}
    attr = 'KEY_' + n.upper()
    return getattr(e, attr, None)

class FastKeySender:
    def __init__(self, keys):
        # keys: list of key name strings
        self.keys = keys
        self.keycodes = []
        for k in keys:
            code = _keycode_from_name(k)
            if code is None:
                raise ValueError(f"Unsupported key name: {k}")
            self.keycodes.append(code)
        # UInput に必要な capabilities を設定
        caps = {e.EV_KEY: list(set(self.keycodes))}
        self.ui = UInput(caps, name="keyclicker-uinput")

    def press(self, key_name):
        code = _keycode_from_name(key_name)
        if code is None:
            raise ValueError(f"Unsupported key name: {key_name}")
        # key down
        self.ui.write(e.EV_KEY, code, 1)
        self.ui.syn()
        # key up
        self.ui.write(e.EV_KEY, code, 0)
        self.ui.syn()

    def close(self):
        try:
            self.ui.close()
        except Exception:
            pass
