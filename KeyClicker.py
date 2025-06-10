import tkinter as tk
from tkinter import messagebox
import threading
import time
import pyautogui
import pygetwindow as gw  # 追加

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

    def repeater(self, keys, interval):
        idx = 0
        change_count = 0
        last_title = None

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
                pyautogui.press(keys[idx])
                idx = (idx + 1) % len(keys)
                time.sleep(interval)
            else:
                time.sleep(0.05)

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
        self.repeat_thread = threading.Thread(target=self.repeater, args=(keys, interval), daemon=True)
        self.repeat_thread.start()
        # 注意ウィンドウは表示しない

    def stop_repeater(self):
        self.running = False
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")
        self.key_entry.config(state="normal")           # 入力欄を有効化
        self.interval_entry.config(state="normal")      # 入力欄を有効化

if __name__ == "__main__":
    root = tk.Tk()
    app = KeyRepeaterApp(root)
    root.mainloop()
