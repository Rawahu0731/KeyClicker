import tkinter as tk
from tkinter import messagebox
import threading
import time
import pyautogui
import pygetwindow as gw  # 追加
import platform

# Linux の場合は fast_input を使って uinput から直接送信できる
try:
    from fast_input import FastKeySender
    FAST_INPUT_AVAILABLE = True
except Exception:
    FastKeySender = None
    FAST_INPUT_AVAILABLE = False

# pyautogui の内部のデフォルト待機を無効にする
pyautogui.PAUSE = 0
class KeyRepeaterApp:
    def __init__(self, master):
        self.master = master
        self.master.title("キー連打アプリ")
        self.running = False
        self.repeat_thread = None
        self.target_title = None  # 追加: 連打対象ウィンドウタイトル

        # キー入力欄
        tk.Label(master, text="連打したいキー（例: a, space, enter）").pack(pady=5)
        self.key_entry = tk.Entry(master, width=20)
        self.key_entry.pack(pady=5)

        # 開始・停止ボタン
        self.start_btn = tk.Button(master, text="開始", command=self.start_repeater)
        self.start_btn.pack(side="left", padx=10, pady=10)
        self.stop_btn = tk.Button(master, text="停止", command=self.stop_repeater, state="disabled")
        self.stop_btn.pack(side="left", padx=10, pady=10)

        # 間隔設定
        tk.Label(master, text="連打間隔（秒）").pack(pady=5)
        self.interval_entry = tk.Entry(master, width=10)
        self.interval_entry.insert(0, "0.05")
        self.interval_entry.pack(pady=5)

        # 最高速オプション（Linux uinput）
        self.fast_mode_var = tk.BooleanVar(value=False)
        cb_text = "最高速モード (uinput, Linux のみ)"
        self.fast_mode_cb = tk.Checkbutton(master, text=cb_text, variable=self.fast_mode_var)
        self.fast_mode_cb.pack(pady=5)

        # クリック数表示
        self.click_count = 0
        self.clicks_label = tk.Label(master, text="送信数: 0 / 秒")
        self.clicks_label.pack(pady=5)

    def repeater(self, keys, interval):
        idx = 0
        change_count = 0
        last_title = None
        # for fast mode
        use_fast = bool(self.fast_mode_var.get()) and FAST_INPUT_AVAILABLE and platform.system().lower() == 'linux'
        fast_sender = None
        if use_fast:
            try:
                fast_sender = FastKeySender(keys)
            except Exception as e:
                # 失敗したらフォールバック
                use_fast = False
                fast_sender = None

        # 1回目のウィンドウ変更で連打開始、2回目で停止
        while self.running:
            try:
                win = gw.getActiveWindow()
                current_title = win.title if win else None
            except Exception:
                current_title = None

            # ウィンドウタイトルが変わったらカウント
            if current_title != last_title:
                if last_title is not None:
                    change_count += 1
                last_title = current_title

                # 1回目の変更で連打対象を記録
                if change_count == 1:
                    self.target_title = current_title

                # 2回目の変更で停止
                elif change_count == 2:
                    self.running = False
                    self.master.after(0, self.stop_repeater)
                    break

            # 連打対象ウィンドウのときだけキー送信
            if self.target_title and current_title == self.target_title:
                if use_fast and fast_sender is not None:
                    # 最高速: uinput で可能な限り速く送信（sleep しない、ただし time.sleep(0) でスケジューリング）
                    fast_sender.press(keys[idx])
                    idx = (idx + 1) % len(keys)
                    self.click_count += 1
                    # 最小限のイールド
                    time.sleep(0)
                else:
                    # pyautogui 経由: システム安定のため最短1フレームに制限
                    min_interval = 1.0 / 60.0
                    sleep_time = max(interval, min_interval)
                    pyautogui.press(keys[idx])
                    idx = (idx + 1) % len(keys)
                    self.click_count += 1
                    time.sleep(sleep_time)
            else:
                time.sleep(0.05)

        # クリーンアップ
        if fast_sender is not None:
            try:
                fast_sender.close()
            except Exception:
                pass

    def start_repeater(self):
        key_input = self.key_entry.get().strip()
        try:
            interval = float(self.interval_entry.get())
        except ValueError:
            messagebox.showerror("エラー", "間隔は数値で入力してください")
            return

        if not key_input:
            messagebox.showerror("エラー", "キーを入力してください")
            return

        # カンマ区切りでキーを分割し、空白を除去
        keys = [k.strip() for k in key_input.split(",") if k.strip()]
        if not keys:
            messagebox.showerror("エラー", "有効なキーを入力してください")
            return

        self.running = True
        self.target_title = None  # 連打対象ウィンドウタイトルをリセット
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self.key_entry.config(state="disabled")
        self.interval_entry.config(state="disabled")
        self.fast_mode_cb.config(state="disabled")
        # クリックカウンタの更新を開始
        self.click_count = 0
        self._update_clicks_label()
        self.repeat_thread = threading.Thread(target=self.repeater, args=(keys, interval), daemon=True)
        self.repeat_thread.start()
        # 注意ウィンドウは表示しない

    def stop_repeater(self):
        self.running = False
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")
        self.key_entry.config(state="normal")           # 入力欄を有効化
        self.interval_entry.config(state="normal")      # 入力欄を有効化
        self.fast_mode_cb.config(state="normal")

    def _update_clicks_label(self):
        # 1秒ごとにラベルを更新してカウンタをリセット
        count = self.click_count
        self.clicks_label.config(text=f"送信数: {count} / 秒")
        self.click_count = 0
        if self.running:
            self.master.after(1000, self._update_clicks_label)

if __name__ == "__main__":
    root = tk.Tk()
    app = KeyRepeaterApp(root)
    root.mainloop()
