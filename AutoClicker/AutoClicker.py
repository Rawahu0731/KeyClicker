import tkinter as tk
from tkinter import ttk, messagebox
import pyautogui
import threading
import time
from PIL import Image, ImageTk
import math
import keyboard
import json
import os

class AutoClickerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("自動クリッカー")
        self.root.geometry("600x900")
        self.root.resizable(True, True)
        
        # 変数の初期化
        self.is_clicking = False
        self.click_thread = None
        self.circle_x = 200
        self.circle_y = 200
        self.circle_radius = 30
        self.is_selecting_position = False
        self.positions = []
        self.current_position_index = 0
        
        # 座標セット管理
        self.coordinate_sets = {}  # 座標セットの辞書
        self.current_set_name = "デフォルト"
        self.max_sets = 10  # 最大保存数
        
        # 座標データファイルのパス
        self.positions_file = "AutoClicker/positions.json"
        
        # 保存された座標を読み込み
        self.load_positions()
        
        # GUIの作成
        self.create_widgets()
        
        # 円の描画
        self.draw_circle()
        
        # ショートカットキーの設定
        self.setup_shortcuts()
        
        # マウス位置の追跡
        self.canvas.bind("<Motion>", self.update_mouse_position)
        self.canvas.bind("<Button-1>", self.set_circle_position)
        
        # 座標リストを表示
        self.update_positions_list()
        
        # 座標セットリストを更新
        self.update_sets_list()
        
    def setup_shortcuts(self):
        """ショートカットキーを設定"""
        try:
            # グローバルホットキーを設定（suppress=Trueで他のアプリに影響しない）
            keyboard.add_hotkey('f6', self.toggle_clicking, suppress=True)
            keyboard.add_hotkey('f7', self.start_position_selection, suppress=True)
            keyboard.add_hotkey('f8', self.emergency_stop, suppress=True)
            keyboard.add_hotkey('ctrl+alt+x', self.emergency_stop, suppress=True)
            
            # 追加の緊急停止ショートカット
            keyboard.add_hotkey('ctrl+shift+z', self.emergency_stop, suppress=True)
            keyboard.add_hotkey('esc', self.emergency_stop, suppress=True)
            
        except Exception as e:
            print(f"ショートカットキー設定エラー: {e}")
            messagebox.showwarning("警告", "ショートカットキーの設定に失敗しました。管理者権限で実行してください。")
        
    def toggle_clicking(self):
        """ショートカットキーでクリック開始/停止を切り替え"""
        try:
            if self.is_clicking:
                self.stop_clicking()
                self.show_notification("自動クリックを停止しました")
            else:
                self.start_clicking()
                self.show_notification("自動クリックを開始しました")
        except Exception as e:
            print(f"トグルクリックエラー: {e}")
            
    def emergency_stop(self):
        """緊急停止"""
        try:
            stopped_something = False
            
            if self.is_clicking:
                self.stop_clicking()
                stopped_something = True
                
            if self.is_selecting_position:
                self.cancel_position_selection()
                stopped_something = True
                
            if stopped_something:
                self.show_notification("緊急停止しました")
        except Exception as e:
            print(f"緊急停止エラー: {e}")
            
    def show_notification(self, message):
        """通知を表示"""
        try:
            # 通知ウィンドウを作成
            notification = tk.Toplevel(self.root)
            notification.title("通知")
            notification.geometry("300x100")
            notification.resizable(False, False)
            
            # 通知ウィンドウを配置
            notification.geometry("+%d+%d" % (self.root.winfo_x() + 50, self.root.winfo_y() + 50))
            
            # 通知メッセージ
            label = ttk.Label(notification, text=message, font=("Arial", 12))
            label.pack(expand=True)
            
            # 2秒後に自動で閉じる
            notification.after(2000, notification.destroy)
            
            # 通知ウィンドウを最前面に表示
            notification.lift()
            notification.focus_force()
            
        except Exception as e:
            print(f"通知表示エラー: {e}")
            messagebox.showinfo("通知", message)
        
    def create_widgets(self):
        # スクロール可能なメインフレームの作成
        self.create_scrollable_frame()
        
        # メインフレーム
        main_frame = ttk.Frame(self.scrollable_frame, padding="15")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # タイトル
        title_label = ttk.Label(main_frame, text="自動クリッカー", font=("Arial", 18, "bold"))
        title_label.grid(row=0, column=0, columnspan=2, pady=(0, 20))
        
        # ショートカットキー情報
        shortcut_frame = ttk.LabelFrame(main_frame, text="ショートカットキー", padding="10")
        shortcut_frame.grid(row=1, column=0, columnspan=2, pady=(0, 20), sticky=(tk.W, tk.E))
        
        shortcut_text = """
F6: 自動クリック開始/停止  |  F7: 座標選択開始  |  F8: 緊急停止  |  Ctrl+Alt+X: 緊急停止
Ctrl+Shift+Z: 緊急停止  |  ESC: 緊急停止
        """
        shortcut_label = ttk.Label(shortcut_frame, text=shortcut_text, font=("Arial", 10, "bold"))
        shortcut_label.grid(row=0, column=0)
        
        # 座標セット管理
        sets_frame = ttk.LabelFrame(main_frame, text="座標セット管理", padding="15")
        sets_frame.grid(row=2, column=0, columnspan=2, pady=(0, 20), sticky=(tk.W, tk.E))
        
        # 現在のセット名表示
        ttk.Label(sets_frame, text="現在のセット:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        self.current_set_label = ttk.Label(sets_frame, text=self.current_set_name, font=("Arial", 11, "bold"))
        self.current_set_label.grid(row=0, column=1, sticky=tk.W, padx=(0, 20))
        
        # セット名入力
        ttk.Label(sets_frame, text="セット名:").grid(row=0, column=2, sticky=tk.W, padx=(20, 10))
        self.set_name_var = tk.StringVar(value="新しいセット")
        set_name_entry = ttk.Entry(sets_frame, textvariable=self.set_name_var, width=15)
        set_name_entry.grid(row=0, column=3, sticky=tk.W, padx=(0, 10))
        
        # セット操作ボタン
        sets_buttons_frame = ttk.Frame(sets_frame)
        sets_buttons_frame.grid(row=1, column=0, columnspan=4, pady=(10, 0))
        
        self.save_set_btn = ttk.Button(sets_buttons_frame, text="現在の座標を保存", 
                                      command=self.save_current_set, style="Accent.TButton")
        self.save_set_btn.grid(row=0, column=0, padx=(0, 10))
        
        self.load_set_btn = ttk.Button(sets_buttons_frame, text="セットを読み込み", 
                                      command=self.load_selected_set)
        self.load_set_btn.grid(row=0, column=1, padx=(0, 10))
        
        self.delete_set_btn = ttk.Button(sets_buttons_frame, text="セットを削除", 
                                        command=self.delete_selected_set)
        self.delete_set_btn.grid(row=0, column=2, padx=(0, 10))
        
        self.clear_current_btn = ttk.Button(sets_buttons_frame, text="現在の座標をクリア", 
                                           command=self.clear_current_positions)
        self.clear_current_btn.grid(row=0, column=3)
        
        # 座標セットリスト
        sets_list_frame = ttk.Frame(sets_frame)
        sets_list_frame.grid(row=2, column=0, columnspan=4, pady=(10, 0), sticky=(tk.W, tk.E))
        
        # 座標セットのTreeview
        sets_columns = ("セット名", "座標数", "作成日時")
        self.sets_tree = ttk.Treeview(sets_list_frame, columns=sets_columns, show="headings", height=4)
        
        # 列の設定
        self.sets_tree.heading("セット名", text="セット名")
        self.sets_tree.heading("座標数", text="座標数")
        self.sets_tree.heading("作成日時", text="作成日時")
        
        self.sets_tree.column("セット名", width=150)
        self.sets_tree.column("座標数", width=80)
        self.sets_tree.column("作成日時", width=120)
        
        self.sets_tree.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # スクロールバー
        sets_scrollbar = ttk.Scrollbar(sets_list_frame, orient="vertical", command=self.sets_tree.yview)
        sets_scrollbar.grid(row=0, column=1, sticky="ns")
        self.sets_tree.configure(yscrollcommand=sets_scrollbar.set)
        
        # 円の表示エリア
        canvas_frame = ttk.LabelFrame(main_frame, text="クリック位置の表示", padding="10")
        canvas_frame.grid(row=3, column=0, columnspan=2, pady=(0, 20), sticky=(tk.W, tk.E))
        
        self.canvas = tk.Canvas(canvas_frame, width=500, height=300, bg="white", relief="solid", bd=2)
        self.canvas.grid(row=0, column=0, pady=5)
        
        # 現在の座標表示
        self.coord_label = ttk.Label(canvas_frame, text="現在の座標: (200, 200)", font=("Arial", 11))
        self.coord_label.grid(row=1, column=0, pady=(5, 0))
        
        # 座標選択ボタン
        select_frame = ttk.Frame(canvas_frame)
        select_frame.grid(row=2, column=0, pady=(10, 0))
        
        self.select_btn = ttk.Button(select_frame, text="座標を追加 (F7)", 
                                    command=self.start_position_selection, style="Accent.TButton")
        self.select_btn.grid(row=0, column=0, padx=(0, 10))
        
        self.cancel_select_btn = ttk.Button(select_frame, text="選択キャンセル", 
                                           command=self.cancel_position_selection, state="disabled")
        self.cancel_select_btn.grid(row=0, column=1, padx=(0, 10))
        
        self.clear_all_btn = ttk.Button(select_frame, text="全座標クリア", 
                                       command=self.clear_all_positions)
        self.clear_all_btn.grid(row=0, column=2)
        
        # 座標リスト表示
        positions_frame = ttk.LabelFrame(main_frame, text="座標リスト", padding="15")
        positions_frame.grid(row=4, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 15))
        
        # 座標リストのTreeview
        columns = ("番号", "X座標", "Y座標", "操作")
        self.positions_tree = ttk.Treeview(positions_frame, columns=columns, show="headings", height=6)
        
        # 列の設定
        self.positions_tree.heading("番号", text="番号")
        self.positions_tree.heading("X座標", text="X座標")
        self.positions_tree.heading("Y座標", text="Y座標")
        self.positions_tree.heading("操作", text="操作")
        
        self.positions_tree.column("番号", width=50)
        self.positions_tree.column("X座標", width=80)
        self.positions_tree.column("Y座標", width=80)
        self.positions_tree.column("操作", width=100)
        
        self.positions_tree.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # スクロールバー
        tree_scrollbar = ttk.Scrollbar(positions_frame, orient="vertical", command=self.positions_tree.yview)
        tree_scrollbar.grid(row=0, column=2, sticky="ns")
        self.positions_tree.configure(yscrollcommand=tree_scrollbar.set)
        
        # 座標操作ボタン
        position_buttons_frame = ttk.Frame(positions_frame)
        position_buttons_frame.grid(row=1, column=0, columnspan=2, pady=(0, 10))
        
        self.delete_selected_btn = ttk.Button(position_buttons_frame, text="選択削除", 
                                             command=self.delete_selected_position)
        self.delete_selected_btn.grid(row=0, column=0, padx=(0, 10))
        
        self.move_up_btn = ttk.Button(position_buttons_frame, text="上に移動", 
                                     command=self.move_position_up)
        self.move_up_btn.grid(row=0, column=1, padx=(0, 10))
        
        self.move_down_btn = ttk.Button(position_buttons_frame, text="下に移動", 
                                       command=self.move_position_down)
        self.move_down_btn.grid(row=0, column=2, padx=(0, 10))
        
        self.select_position_btn = ttk.Button(position_buttons_frame, text="この座標を選択", 
                                             command=self.select_position_from_list)
        self.select_position_btn.grid(row=0, column=3)
        
        # 円の位置設定
        position_frame = ttk.LabelFrame(main_frame, text="現在の座標設定", padding="15")
        position_frame.grid(row=5, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 15))
        
        # X座標
        ttk.Label(position_frame, text="X座標:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        self.x_var = tk.StringVar(value=str(self.circle_x))
        x_entry = ttk.Entry(position_frame, textvariable=self.x_var, width=15)
        x_entry.grid(row=0, column=1, padx=(0, 20), sticky=tk.W)
        
        # Y座標
        ttk.Label(position_frame, text="Y座標:").grid(row=0, column=2, sticky=tk.W, padx=(20, 10))
        self.y_var = tk.StringVar(value=str(self.circle_y))
        y_entry = ttk.Entry(position_frame, textvariable=self.y_var, width=15)
        y_entry.grid(row=0, column=3, sticky=tk.W)
        
        # 半径
        ttk.Label(position_frame, text="半径:").grid(row=1, column=0, sticky=tk.W, padx=(0, 10), pady=(10, 0))
        self.radius_var = tk.StringVar(value=str(self.circle_radius))
        radius_entry = ttk.Entry(position_frame, textvariable=self.radius_var, width=15)
        radius_entry.grid(row=1, column=1, padx=(0, 20), pady=(10, 0), sticky=tk.W)
        
        # 更新ボタン
        update_btn = ttk.Button(position_frame, text="位置を更新", command=self.update_circle_position)
        update_btn.grid(row=1, column=2, columnspan=2, padx=(20, 0), pady=(10, 0))
        
        # クリック設定
        click_frame = ttk.LabelFrame(main_frame, text="クリック設定", padding="15")
        click_frame.grid(row=6, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 15))
        
        # クリック間隔
        ttk.Label(click_frame, text="クリック間隔 (秒):").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        self.interval_var = tk.StringVar(value="0.1")
        interval_entry = ttk.Entry(click_frame, textvariable=self.interval_var, width=15)
        interval_entry.grid(row=0, column=1, padx=(0, 20), sticky=tk.W)
        
        # クリック回数
        ttk.Label(click_frame, text="クリック回数 (0=無限):").grid(row=0, column=2, sticky=tk.W, padx=(20, 10))
        self.count_var = tk.StringVar(value="0")
        count_entry = ttk.Entry(click_frame, textvariable=self.count_var, width=15)
        count_entry.grid(row=0, column=3, sticky=tk.W)
        
        # クリックモード
        ttk.Label(click_frame, text="クリックモード:").grid(row=1, column=0, sticky=tk.W, padx=(0, 10), pady=(10, 0))
        self.click_mode_var = tk.StringVar(value="sequence")
        click_mode_combo = ttk.Combobox(click_frame, textvariable=self.click_mode_var, 
                                       values=["single", "sequence"], width=15, state="readonly")
        click_mode_combo.grid(row=1, column=1, padx=(0, 20), pady=(10, 0), sticky=tk.W)
        click_mode_combo.set("sequence")
        
        # ボタンフレーム
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=7, column=0, columnspan=2, pady=(15, 0))
        
        # 開始ボタン
        self.start_btn = ttk.Button(button_frame, text="クリック開始 (F6)", command=self.start_clicking, style="Accent.TButton")
        self.start_btn.grid(row=0, column=0, padx=(0, 15))
        
        # 停止ボタン
        self.stop_btn = ttk.Button(button_frame, text="クリック停止 (F6)", command=self.stop_clicking, state="disabled")
        self.stop_btn.grid(row=0, column=1, padx=(0, 15))
        
        # 緊急停止ボタン
        self.emergency_btn = ttk.Button(button_frame, text="緊急停止 (F8)", command=self.emergency_stop)
        self.emergency_btn.grid(row=0, column=2)
        
        # 説明テキスト
        info_frame = ttk.LabelFrame(main_frame, text="使用方法", padding="15")
        info_frame.grid(row=8, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(20, 0))
        
        info_text = """
1. 「座標を追加」ボタンをクリック (または F7)
2. マウスを目的の位置に移動して Ctrl+Shift+C を押す
3. 複数の座標を追加できます
4. 「現在の座標を保存」で座標セットを保存（最大10個）
5. 「セットを読み込み」で保存した座標セットを復元
6. クリックモードを選択：
   - single: 現在選択中の座標のみクリック
   - sequence: 座標リストの順番でクリック
7. クリック間隔と回数を設定
8. 「クリック開始」ボタンで自動クリック開始 (または F6)
9. 緊急停止方法：
   - マウスを画面左上隅に移動
   - F8 キーを押す
   - Ctrl+Alt+X を押す
   - Ctrl+Shift+Z を押す
   - ESC キーを押す
        """
        
        info_label = ttk.Label(info_frame, text=info_text, justify=tk.LEFT, font=("Arial", 10))
        info_label.grid(row=0, column=0, sticky=tk.W)
        
    def create_scrollable_frame(self):
        """スクロール可能なメインフレームを作成"""
        # メインキャンバス
        self.main_canvas = tk.Canvas(self.root)
        self.scrollbar = ttk.Scrollbar(self.root, orient="vertical", command=self.main_canvas.yview)
        self.scrollable_frame = ttk.Frame(self.main_canvas)
        
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.main_canvas.configure(scrollregion=self.main_canvas.bbox("all"))
        )
        
        self.main_canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.main_canvas.configure(yscrollcommand=self.scrollbar.set)
        
        # グリッド配置
        self.main_canvas.grid(row=0, column=0, sticky="nsew")
        self.scrollbar.grid(row=0, column=1, sticky="ns")
        
        # ウィンドウのリサイズ設定
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=1)
        
        # マウスホイールでスクロール
        self.main_canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        
    def _on_mousewheel(self, event):
        """マウスホイールでスクロール"""
        self.main_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        
    def save_current_set(self):
        """現在の座標をセットとして保存"""
        set_name = self.set_name_var.get().strip()
        if not set_name:
            messagebox.showerror("エラー", "セット名を入力してください")
            return
            
        if len(self.positions) == 0:
            messagebox.showerror("エラー", "保存する座標がありません")
            return
            
        # 最大保存数チェック
        if len(self.coordinate_sets) >= self.max_sets and set_name not in self.coordinate_sets:
            messagebox.showerror("エラー", f"座標セットは最大{self.max_sets}個まで保存できます")
            return
            
        # 座標セットを保存
        import datetime
        self.coordinate_sets[set_name] = {
            'positions': self.positions.copy(),
            'created_at': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        self.current_set_name = set_name
        self.current_set_label.config(text=set_name)
        self.update_sets_list()
        self.save_positions()
        
        messagebox.showinfo("成功", f"座標セット '{set_name}' を保存しました")
        
    def load_selected_set(self):
        """選択されたセットを読み込み"""
        selected = self.sets_tree.selection()
        if not selected:
            messagebox.showerror("エラー", "読み込むセットを選択してください")
            return
            
        item = selected[0]
        set_name = self.sets_tree.item(item, "values")[0]
        
        if set_name in self.coordinate_sets:
            self.positions = self.coordinate_sets[set_name]['positions'].copy()
            self.current_set_name = set_name
            self.current_set_label.config(text=set_name)
            
            # 最初の座標を現在の座標に設定
            if self.positions:
                self.circle_x = self.positions[0][0]
                self.circle_y = self.positions[0][1]
                self.x_var.set(str(self.circle_x))
                self.y_var.set(str(self.circle_y))
                self.current_position_index = 0
            
            self.update_positions_list()
            self.draw_circle()
            
            messagebox.showinfo("成功", f"座標セット '{set_name}' を読み込みました")
        else:
            messagebox.showerror("エラー", "選択されたセットが見つかりません")
            
    def delete_selected_set(self):
        """選択されたセットを削除"""
        selected = self.sets_tree.selection()
        if not selected:
            messagebox.showerror("エラー", "削除するセットを選択してください")
            return
            
        item = selected[0]
        set_name = self.sets_tree.item(item, "values")[0]
        
        if messagebox.askyesno("確認", f"座標セット '{set_name}' を削除しますか？"):
            if set_name in self.coordinate_sets:
                del self.coordinate_sets[set_name]
                
                # 現在のセットが削除された場合、デフォルトに戻す
                if self.current_set_name == set_name:
                    self.current_set_name = "デフォルト"
                    self.current_set_label.config(text=self.current_set_name)
                    
                self.update_sets_list()
                self.save_positions()
                
                messagebox.showinfo("成功", f"座標セット '{set_name}' を削除しました")
                
    def clear_current_positions(self):
        """現在の座標をクリア"""
        if messagebox.askyesno("確認", "現在の座標をすべてクリアしますか？"):
            self.positions.clear()
            self.update_positions_list()
            self.draw_circle()
            self.save_positions()
            
    def update_sets_list(self):
        """座標セットリストを更新"""
        # 既存のアイテムを削除
        for item in self.sets_tree.get_children():
            self.sets_tree.delete(item)
        
        # 新しいアイテムを追加
        for set_name, set_data in self.coordinate_sets.items():
            positions_count = len(set_data['positions'])
            created_at = set_data['created_at']
            self.sets_tree.insert("", "end", values=(set_name, positions_count, created_at))
            
    def add_position(self, x, y):
        """座標をリストに追加"""
        self.positions.append((x, y))
        self.update_positions_list()
        self.save_positions()  # 自動保存
        
    def update_positions_list(self):
        """座標リストを更新"""
        # 既存のアイテムを削除
        for item in self.positions_tree.get_children():
            self.positions_tree.delete(item)
        
        # 新しいアイテムを追加
        for i, (x, y) in enumerate(self.positions, 1):
            self.positions_tree.insert("", "end", values=(i, x, y, "削除"))
            
    def delete_selected_position(self):
        """選択された座標を削除"""
        selected = self.positions_tree.selection()
        if selected:
            item = selected[0]
            index = int(self.positions_tree.item(item, "values")[0]) - 1
            if 0 <= index < len(self.positions):
                del self.positions[index]
                self.update_positions_list()
                self.save_positions()  # 自動保存
                
    def move_position_up(self):
        """座標を上に移動"""
        selected = self.positions_tree.selection()
        if selected:
            item = selected[0]
            index = int(self.positions_tree.item(item, "values")[0]) - 1
            if index > 0:
                self.positions[index], self.positions[index-1] = self.positions[index-1], self.positions[index]
                self.update_positions_list()
                self.save_positions()  # 自動保存
                
    def move_position_down(self):
        """座標を下に移動"""
        selected = self.positions_tree.selection()
        if selected:
            item = selected[0]
            index = int(self.positions_tree.item(item, "values")[0]) - 1
            if index < len(self.positions) - 1:
                self.positions[index], self.positions[index+1] = self.positions[index+1], self.positions[index]
                self.update_positions_list()
                self.save_positions()  # 自動保存
                
    def select_position_from_list(self):
        """リストから座標を選択"""
        selected = self.positions_tree.selection()
        if selected:
            item = selected[0]
            index = int(self.positions_tree.item(item, "values")[0]) - 1
            if 0 <= index < len(self.positions):
                x, y = self.positions[index]
                self.circle_x = x
                self.circle_y = y
                self.x_var.set(str(x))
                self.y_var.set(str(y))
                self.current_position_index = index
                self.draw_circle()
                
    def clear_all_positions(self):
        """すべての座標をクリア"""
        if messagebox.askyesno("確認", "すべての座標を削除しますか？"):
            self.positions.clear()
            self.update_positions_list()
            self.save_positions()  # 自動保存
        
    def start_position_selection(self):
        """画面座標選択を開始"""
        if self.is_clicking:
            # クリック中は何もしない（エラーメッセージも表示しない）
            return
            
        self.is_selecting_position = True
        self.select_btn.config(state="disabled")
        self.cancel_select_btn.config(state="normal")
        self.coord_label.config(text="マウスを移動して Ctrl+Shift+C で座標を追加")
        # 別スレッドで座標選択を実行
        selection_thread = threading.Thread(target=self.position_selection_worker)
        selection_thread.daemon = True
        selection_thread.start()

    def position_selection_worker(self):
        """座標選択処理を実行するワーカースレッド"""
        try:
            if not self.is_selecting_position:
                return
            # 座標選択の説明
            self.root.after(0, lambda: self.coord_label.config(text="マウスを移動して Ctrl+Shift+C で座標を追加"))
            # キーボードショートカットの設定
            def capture_position():
                if self.is_selecting_position:
                    x, y = pyautogui.position()
                    self.add_position(x, y)
                    self.circle_x = x
                    self.circle_y = y
                    self.x_var.set(str(x))
                    self.y_var.set(str(y))
                    self.root.after(0, self.draw_circle)
                    self.root.after(0, lambda: self.coord_label.config(text=f"座標を追加しました: ({x}, {y}) - 合計: {len(self.positions)}個"))
                    self.is_selecting_position = False
                    self.select_btn.config(state="normal")
                    self.cancel_select_btn.config(state="disabled")
                    try:
                        keyboard.remove_hotkey('ctrl+shift+c')
                    except:
                        pass
            keyboard.add_hotkey('ctrl+shift+c', capture_position)
            while self.is_selecting_position:
                try:
                    x, y = pyautogui.position()
                    self.root.after(0, lambda: self.coord_label.config(text=f"マウス位置: ({x}, {y}) - Ctrl+Shift+C で追加"))
                    time.sleep(0.1)
                except Exception as e:
                    print(f"座標選択エラー: {e}")
                    break
        except Exception as e:
            messagebox.showerror("エラー", f"座標選択中にエラーが発生しました: {str(e)}")
        finally:
            self.is_selecting_position = False
            self.root.after(0, lambda: self.select_btn.config(state="normal"))
            self.root.after(0, lambda: self.cancel_select_btn.config(state="disabled"))
            self.root.after(0, lambda: self.coord_label.config(text=f"現在の座標: ({self.circle_x}, {self.circle_y}) - 座標数: {len(self.positions)}"))
            try:
                keyboard.remove_hotkey('ctrl+shift+c')
            except:
                pass
        
    def draw_circle(self):
        """円を描画"""
        self.canvas.delete("circle")
        
        # すべての座標に小さな円を描画
        for i, (x, y) in enumerate(self.positions):
            color = "blue" if i == self.current_position_index else "lightblue"
            self.canvas.create_oval(x-10, y-10, x+10, y+10, fill=color, outline="darkblue", width=1, tags="circle")
            self.canvas.create_text(x, y-20, text=str(i+1), fill="darkblue", font=("Arial", 8, "bold"), tags="circle")
        
        # 現在選択中の座標に大きな円を描画
        x1 = self.circle_x - self.circle_radius
        y1 = self.circle_y - self.circle_radius
        x2 = self.circle_x + self.circle_radius
        y2 = self.circle_y + self.circle_radius
        
        # 円を描画
        self.canvas.create_oval(x1, y1, x2, y2, fill="red", outline="darkred", width=2, tags="circle")
        
        # 中心にテキストを追加
        self.canvas.create_text(self.circle_x, self.circle_y, text="現在位置", 
                               fill="white", font=("Arial", 10, "bold"), tags="circle")
        
        # 座標表示を更新
        self.coord_label.config(text=f"現在の座標: ({self.circle_x}, {self.circle_y}) - 座標数: {len(self.positions)}")
        
    def update_circle_position(self):
        """円の位置を更新"""
        try:
            self.circle_x = int(self.x_var.get())
            self.circle_y = int(self.y_var.get())
            self.circle_radius = int(self.radius_var.get())
            
            # 範囲チェック
            if self.circle_radius <= 0:
                messagebox.showerror("エラー", "半径は0より大きい値を入力してください")
                return
                
            self.draw_circle()
        except ValueError:
            messagebox.showerror("エラー", "数値を入力してください")
            
    def set_circle_position(self, event):
        """マウスクリックで円の位置を設定"""
        self.circle_x = event.x
        self.circle_y = event.y
        self.x_var.set(str(self.circle_x))
        self.y_var.set(str(self.circle_y))
        self.draw_circle()
        
    def update_mouse_position(self, event):
        """マウス位置を更新"""
        if not self.is_selecting_position:
            self.coord_label.config(text=f"マウス位置: ({event.x}, {event.y}) - 座標数: {len(self.positions)}")
        
    def start_clicking(self):
        """自動クリックを開始"""
        if self.is_selecting_position:
            messagebox.showwarning("警告", "座標選択中はクリック開始できません")
            return
            
        try:
            interval = float(self.interval_var.get())
            count = int(self.count_var.get())
            click_mode = self.click_mode_var.get()
            
            if interval <= 0:
                messagebox.showerror("エラー", "クリック間隔は0より大きい値を入力してください")
                return
                
            if count < 0:
                messagebox.showerror("エラー", "クリック回数は0以上の値を入力してください")
                return
                
            if click_mode == "sequence" and len(self.positions) == 0:
                messagebox.showerror("エラー", "シーケンスモードでは座標を追加してください")
                return
                
            self.is_clicking = True
            self.start_btn.config(state="disabled")
            self.stop_btn.config(state="normal")
            
            # 別スレッドでクリック実行
            self.click_thread = threading.Thread(target=self.click_worker, args=(interval, count, click_mode))
            self.click_thread.daemon = True
            self.click_thread.start()
            
        except ValueError:
            messagebox.showerror("エラー", "正しい数値を入力してください")
            
    def stop_clicking(self):
        """自動クリックを停止"""
        self.is_clicking = False
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")
        # 強制的に停止状態を設定
        self.root.after(0, lambda: self.coord_label.config(text=f"現在の座標: ({self.circle_x}, {self.circle_y}) - 座標数: {len(self.positions)}"))

    def cancel_position_selection(self):
        """座標選択をキャンセル"""
        self.is_selecting_position = False
        self.select_btn.config(state="normal")
        self.cancel_select_btn.config(state="disabled")
        self.coord_label.config(text=f"現在の座標: ({self.circle_x}, {self.circle_y}) - 座標数: {len(self.positions)}")

    def load_positions(self):
        """保存された座標を読み込み"""
        try:
            if os.path.exists(self.positions_file):
                with open(self.positions_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.positions = data.get('positions', [])
                    self.coordinate_sets = data.get('coordinate_sets', {})
                    # 現在の座標も復元
                    if self.positions:
                        self.circle_x = self.positions[0][0]
                        self.circle_y = self.positions[0][1]
                    print(f"座標を読み込みました: {len(self.positions)}個")
                    print(f"座標セットを読み込みました: {len(self.coordinate_sets)}個")
        except Exception as e:
            print(f"座標読み込みエラー: {e}")
            self.positions = []
            self.coordinate_sets = {}
            
    def save_positions(self):
        """座標リストを保存"""
        try:
            data = {
                'positions': self.positions,
                'coordinate_sets': self.coordinate_sets
            }
            with open(self.positions_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"座標を保存しました: {len(self.positions)}個")
            print(f"座標セットを保存しました: {len(self.coordinate_sets)}個")
        except Exception as e:
            print(f"座標保存エラー: {e}")
            messagebox.showerror("エラー", f"座標の保存に失敗しました: {str(e)}")

    def click_worker(self, interval, count, click_mode):
        """クリック処理を実行するワーカースレッド"""
        try:
            clicks_done = 0
            position_index = 0
            
            while self.is_clicking:
                # 停止チェックを頻繁に行う
                if not self.is_clicking:
                    break
                    
                if count > 0 and clicks_done >= count:
                    break
                    
                if click_mode == "single":
                    pyautogui.click(self.circle_x, self.circle_y)
                    clicks_done += 1
                    if count > 0:
                        self.root.after(0, lambda: self.coord_label.config(
                            text=f"クリック中: {clicks_done}/{count} - 座標: ({self.circle_x}, {self.circle_y})"))
                    else:
                        self.root.after(0, lambda: self.coord_label.config(
                            text=f"クリック中: {clicks_done}回目 - 座標: ({self.circle_x}, {self.circle_y})"))
                            
                elif click_mode == "sequence":
                    if len(self.positions) > 0:
                        x, y = self.positions[position_index]
                        pyautogui.click(x, y)
                        clicks_done += 1
                        position_index = (position_index + 1) % len(self.positions)
                        if count > 0:
                            self.root.after(0, lambda: self.coord_label.config(
                                text=f"クリック中: {clicks_done}/{count} - 座標{position_index+1}: ({x}, {y})"))
                        else:
                            self.root.after(0, lambda: self.coord_label.config(
                                text=f"クリック中: {clicks_done}回目 - 座標{position_index+1}: ({x}, {y})"))
                
                # 間隔を短く分割して停止チェックを頻繁に行う
                for _ in range(int(interval * 10)):  # 0.1秒ごとにチェック
                    if not self.is_clicking:
                        break
                    time.sleep(0.1)
                    
        except Exception as e:
            messagebox.showerror("エラー", f"クリック中にエラーが発生しました: {str(e)}")
        finally:
            # GUIスレッドでボタン状態を更新
            self.root.after(0, self.stop_clicking)
            self.root.after(0, lambda: self.coord_label.config(text=f"現在の座標: ({self.circle_x}, {self.circle_y}) - 座標数: {len(self.positions)}"))

def main():
    # pyautoguiの設定
    pyautogui.FAILSAFE = True  # マウスを画面の左上隅に移動すると停止
    
    root = tk.Tk()
    app = AutoClickerApp(root)
    
    # 終了時の処理
    def on_closing():
        app.stop_clicking()
        app.cancel_position_selection()
        # ショートカットキーを削除
        try:
            keyboard.remove_hotkey('f6')
            keyboard.remove_hotkey('f7')
            keyboard.remove_hotkey('f8')
            keyboard.remove_hotkey('ctrl+alt+x')
            keyboard.remove_hotkey('ctrl+shift+z')
            keyboard.remove_hotkey('esc')
        except:
            pass
        root.destroy()
    
    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()

if __name__ == "__main__":
    main()