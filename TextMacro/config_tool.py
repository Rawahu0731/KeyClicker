"""
Text Macro Configuration Tool
文字認識マクロシステムの設定ツール（GUI版）
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import json
import pyautogui
from PIL import Image, ImageTk
import threading

class ConfigTool:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Text Macro Configuration Tool")
        self.root.geometry("800x600")
        
        self.config_file = "config.json"
        self.config = self.load_config()
        
        self.setup_ui()
        
    def load_config(self):
        """設定ファイルを読み込む"""
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            return {
                "monitoring_regions": [],
                "check_interval": 1.0,
                "ocr_language": "jpn+eng"
            }
    
    def save_config(self):
        """設定ファイルを保存"""
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, ensure_ascii=False, indent=2)
    
    def setup_ui(self):
        """UIを設定"""
        # メニューバー
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="ファイル", menu=file_menu)
        file_menu.add_command(label="設定を開く", command=self.load_config_file)
        file_menu.add_command(label="設定を保存", command=self.save_config_file)
        file_menu.add_separator()
        file_menu.add_command(label="終了", command=self.root.quit)
        
        # メインフレーム
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 設定項目
        settings_frame = ttk.LabelFrame(main_frame, text="基本設定", padding="5")
        settings_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        
        ttk.Label(settings_frame, text="チェック間隔 (秒):").grid(row=0, column=0, sticky=tk.W)
        self.interval_var = tk.DoubleVar(value=self.config.get("check_interval", 1.0))
        ttk.Entry(settings_frame, textvariable=self.interval_var, width=10).grid(row=0, column=1, sticky=tk.W, padx=(5, 0))
        
        ttk.Label(settings_frame, text="OCR言語:").grid(row=1, column=0, sticky=tk.W)
        self.language_var = tk.StringVar(value=self.config.get("ocr_language", "jpn+eng"))
        ttk.Entry(settings_frame, textvariable=self.language_var, width=20).grid(row=1, column=1, sticky=tk.W, padx=(5, 0))
        
        # 監視領域リスト
        regions_frame = ttk.LabelFrame(main_frame, text="監視領域", padding="5")
        regions_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        
        # リストボックス
        self.regions_listbox = tk.Listbox(regions_frame, height=8)
        self.regions_listbox.grid(row=0, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 5))
        self.regions_listbox.bind('<<ListboxSelect>>', self.on_region_select)
        
        # ボタン
        ttk.Button(regions_frame, text="新規追加", command=self.add_region).grid(row=1, column=0, padx=(0, 5))
        ttk.Button(regions_frame, text="編集", command=self.edit_region).grid(row=1, column=1, padx=(0, 5))
        ttk.Button(regions_frame, text="削除", command=self.delete_region).grid(row=1, column=2)
        
        # 座標選択ボタン
        ttk.Button(regions_frame, text="座標を選択", command=self.select_coordinates).grid(row=2, column=0, columnspan=3, pady=(5, 0))
        
        # 保存・実行ボタン
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=2, column=0, columnspan=2, pady=(10, 0))
        
        ttk.Button(button_frame, text="設定を保存", command=self.save_settings).grid(row=0, column=0, padx=(0, 5))
        ttk.Button(button_frame, text="マクロを実行", command=self.run_macro).grid(row=0, column=1)
        
        # 初期データを読み込み
        self.refresh_regions_list()
        
        # ウィンドウのリサイズ設定
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(1, weight=1)
        regions_frame.columnconfigure(0, weight=1)
    
    def refresh_regions_list(self):
        """監視領域リストを更新"""
        self.regions_listbox.delete(0, tk.END)
        for region in self.config["monitoring_regions"]:
            self.regions_listbox.insert(tk.END, f"{region['name']} - '{region['target_text']}'")
    
    def on_region_select(self, event):
        """領域選択時の処理"""
        pass
    
    def add_region(self):
        """新しい監視領域を追加"""
        self.show_region_dialog()
    
    def edit_region(self):
        """選択された監視領域を編集"""
        selection = self.regions_listbox.curselection()
        if not selection:
            messagebox.showwarning("警告", "編集する領域を選択してください")
            return
        
        index = selection[0]
        self.show_region_dialog(index)
    
    def delete_region(self):
        """選択された監視領域を削除"""
        selection = self.regions_listbox.curselection()
        if not selection:
            messagebox.showwarning("警告", "削除する領域を選択してください")
            return
        
        if messagebox.askyesno("確認", "選択された領域を削除しますか？"):
            index = selection[0]
            del self.config["monitoring_regions"][index]
            self.refresh_regions_list()
    
    def show_region_dialog(self, edit_index=None):
        """監視領域設定ダイアログを表示"""
        dialog = tk.Toplevel(self.root)
        dialog.title("監視領域設定")
        dialog.geometry("400x500")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # 編集モードの場合は既存データを読み込み
        if edit_index is not None:
            region_data = self.config["monitoring_regions"][edit_index]
        else:
            region_data = {
                "name": "",
                "x": 0, "y": 0, "width": 100, "height": 100,
                "target_text": "",
                "actions": []
            }
        
        # フォーム要素
        ttk.Label(dialog, text="名前:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        name_var = tk.StringVar(value=region_data["name"])
        ttk.Entry(dialog, textvariable=name_var, width=30).grid(row=0, column=1, padx=5, pady=5)
        
        ttk.Label(dialog, text="X座標:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        x_var = tk.IntVar(value=region_data["x"])
        ttk.Entry(dialog, textvariable=x_var, width=30).grid(row=1, column=1, padx=5, pady=5)
        
        ttk.Label(dialog, text="Y座標:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        y_var = tk.IntVar(value=region_data["y"])
        ttk.Entry(dialog, textvariable=y_var, width=30).grid(row=2, column=1, padx=5, pady=5)
        
        ttk.Label(dialog, text="幅:").grid(row=3, column=0, sticky=tk.W, padx=5, pady=5)
        width_var = tk.IntVar(value=region_data["width"])
        ttk.Entry(dialog, textvariable=width_var, width=30).grid(row=3, column=1, padx=5, pady=5)
        
        ttk.Label(dialog, text="高さ:").grid(row=4, column=0, sticky=tk.W, padx=5, pady=5)
        height_var = tk.IntVar(value=region_data["height"])
        ttk.Entry(dialog, textvariable=height_var, width=30).grid(row=4, column=1, padx=5, pady=5)
        
        ttk.Label(dialog, text="検索文字:").grid(row=5, column=0, sticky=tk.W, padx=5, pady=5)
        text_var = tk.StringVar(value=region_data["target_text"])
        ttk.Entry(dialog, textvariable=text_var, width=30).grid(row=5, column=1, padx=5, pady=5)
        
        # アクション設定（簡易版）
        ttk.Label(dialog, text="アクション (JSON):").grid(row=6, column=0, sticky=tk.NW, padx=5, pady=5)
        actions_text = tk.Text(dialog, width=40, height=10)
        actions_text.grid(row=6, column=1, padx=5, pady=5)
        actions_text.insert('1.0', json.dumps(region_data["actions"], ensure_ascii=False, indent=2))
        
        # ボタン
        button_frame = ttk.Frame(dialog)
        button_frame.grid(row=7, column=0, columnspan=2, pady=10)
        
        def save_region():
            try:
                actions_json = actions_text.get('1.0', tk.END).strip()
                actions = json.loads(actions_json) if actions_json else []
                
                new_region = {
                    "name": name_var.get(),
                    "x": x_var.get(),
                    "y": y_var.get(),
                    "width": width_var.get(),
                    "height": height_var.get(),
                    "target_text": text_var.get(),
                    "actions": actions
                }
                
                if edit_index is not None:
                    self.config["monitoring_regions"][edit_index] = new_region
                else:
                    self.config["monitoring_regions"].append(new_region)
                
                self.refresh_regions_list()
                dialog.destroy()
                
            except json.JSONDecodeError:
                messagebox.showerror("エラー", "アクションのJSON形式が正しくありません")
        
        ttk.Button(button_frame, text="保存", command=save_region).grid(row=0, column=0, padx=5)
        ttk.Button(button_frame, text="キャンセル", command=dialog.destroy).grid(row=0, column=1, padx=5)
    
    def select_coordinates(self):
        """マウスで座標を選択"""
        messagebox.showinfo("座標選択", "3秒後にマウスカーソルの位置を取得します。\n目的の位置にカーソルを合わせてください。")
        
        def get_position():
            time.sleep(3)
            x, y = pyautogui.position()
            messagebox.showinfo("座標取得完了", f"取得した座標: X={x}, Y={y}")
        
        import time
        threading.Thread(target=get_position, daemon=True).start()
    
    def save_settings(self):
        """設定を保存"""
        self.config["check_interval"] = self.interval_var.get()
        self.config["ocr_language"] = self.language_var.get()
        self.save_config()
        messagebox.showinfo("保存完了", "設定を保存しました")
    
    def load_config_file(self):
        """設定ファイルを開く"""
        filename = filedialog.askopenfilename(
            title="設定ファイルを選択",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if filename:
            self.config_file = filename
            self.config = self.load_config()
            self.interval_var.set(self.config.get("check_interval", 1.0))
            self.language_var.set(self.config.get("ocr_language", "jpn+eng"))
            self.refresh_regions_list()
    
    def save_config_file(self):
        """設定ファイルを名前を付けて保存"""
        filename = filedialog.asksaveasfilename(
            title="設定ファイルを保存",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if filename:
            self.config_file = filename
            self.save_settings()
    
    def run_macro(self):
        """マクロシステムを実行"""
        messagebox.showinfo("実行", "コマンドラインからtext_macro.pyを実行してください")
    
    def run(self):
        """GUIを開始"""
        self.root.mainloop()


if __name__ == "__main__":
    app = ConfigTool()
    app.run()