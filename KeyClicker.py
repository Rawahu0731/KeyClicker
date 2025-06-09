import tkinter as tk
from tkinter import messagebox
import threading
import time
import pyautogui

class KeyRepeaterApp:
    def __init__(self, master):
        self.master = master
        self.master.title("キー連打アプリ")
        self.running = False
        self.repeat_thread = None

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
        while self.running:
            pyautogui.press(keys[idx])
            idx = (idx + 1) % len(keys)
            time.sleep(interval)

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
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self.key_entry.config(state="disabled")
        self.interval_entry.config(state="disabled")
        self.repeat_thread = threading.Thread(target=self.repeater, args=(keys, interval), daemon=True)
        self.repeat_thread.start()

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
