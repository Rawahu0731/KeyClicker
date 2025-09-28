"""
Text Recognition Macro System - GUI版
画面の指定領域の文字を読み取り、一致した場合にマクロを実行するシステム（tkinter GUI）
AutoClickerの設計を参考にした改良版
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import numpy as np
import pyautogui
import pynput
from pynput import mouse, keyboard as pynput_keyboard
import json
import time
import threading
from PIL import Image, ImageGrab, ImageTk
import os
import subprocess
import sys
import platform
import datetime

# Tesseractの動的インポート
TESSERACT_AVAILABLE = False
try:
    import pytesseract
    TESSERACT_AVAILABLE = True
except ImportError:
    print("警告: pytesseractがインストールされていません")

# EasyOCRの動的インポート（代替OCRエンジン）
EASYOCR_AVAILABLE = False
try:
    import easyocr
    EASYOCR_AVAILABLE = True
except ImportError:
    pass

class TextMacroGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Text Recognition Macro System - 改良版")
        self.root.geometry("1200x800")
        self.root.resizable(True, True)
        
        # ファイル管理
        self.config_file = "config.json"
        self.regions_file = "regions.json"
        
        # データ管理
        self.config = self.load_config()
        self.monitoring_regions = {}  # 監視領域セット
        self.current_region_set = "デフォルト"
        self.max_region_sets = 20
        
        # 監視状態
        self.running = False
        self.monitoring_thread = None
        
        # 領域選択状態
        self.selection_window = None
        self.is_selecting_region = False
        self.is_selecting_action_position = False
        self.start_x = None
        self.start_y = None
        self.end_x = None
        self.end_y = None
        self.current_action_vars = None  # アクション設定用の変数を保持
        
        # OCRエンジンの初期化
        self.ocr_engine = None
        self.setup_ocr()
        
        # pyautoguiの設定
        pyautogui.FAILSAFE = True
        pyautogui.PAUSE = 0.1
        
        # 保存された領域データを読み込み
        self.load_regions()
        
        # GUI作成
        self.setup_ui()
        
        # ショートカットキー設定
        self.setup_shortcuts()
        
        # データ表示を更新
        self.update_region_sets_list()
        self.update_regions_list()
    
    def setup_shortcuts(self):
        """ショートカットキーを設定"""
        try:
            import keyboard
            # グローバルホットキーを設定
            keyboard.add_hotkey('f6', self.toggle_monitoring, suppress=True)
            keyboard.add_hotkey('f7', self.quick_add_region, suppress=True)
            keyboard.add_hotkey('f8', self.emergency_stop, suppress=True)
            keyboard.add_hotkey('ctrl+alt+x', self.emergency_stop, suppress=True)
            keyboard.add_hotkey('esc', self.emergency_stop, suppress=True)
        except Exception as e:
            print(f"ショートカットキー設定エラー: {e}")
            
    def toggle_monitoring(self):
        """監視開始/停止を切り替え"""
        if self.running:
            self.stop_monitoring()
        else:
            self.start_monitoring()
            
    def quick_add_region(self):
        """クイック領域追加"""
        if not self.is_selecting_region:
            self.add_region()
            
    def emergency_stop(self):
        """緊急停止"""
        if self.running:
            self.stop_monitoring()
        if self.is_selecting_region:
            self.cancel_region_selection()
        if self.is_selecting_action_position:
            self.cancel_action_selection()
        self.show_notification("緊急停止しました")
        
    def show_notification(self, message):
        """通知を表示"""
        try:
            notification = tk.Toplevel(self.root)
            notification.title("通知")
            notification.geometry("300x100")
            notification.resizable(False, False)
            notification.geometry("+%d+%d" % (self.root.winfo_x() + 50, self.root.winfo_y() + 50))
            
            label = ttk.Label(notification, text=message, font=("Arial", 12))
            label.pack(expand=True)
            
            notification.after(2000, notification.destroy)
            notification.lift()
            notification.focus_force()
        except Exception as e:
            print(f"通知表示エラー: {e}")
            messagebox.showinfo("通知", message)
    
    def setup_ocr(self):
        """OCRエンジンをセットアップ"""
        global TESSERACT_AVAILABLE, EASYOCR_AVAILABLE
        
        # Tesseractの設定を試行
        if TESSERACT_AVAILABLE:
            try:
                # Windowsでの一般的なTesseractパスを試行
                possible_paths = [
                    r'C:\Program Files\Tesseract-OCR\tesseract.exe',
                    r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
                    r'C:\Users\{}\AppData\Local\Programs\Tesseract-OCR\tesseract.exe'.format(os.environ.get('USERNAME', '')),
                ]
                
                for path in possible_paths:
                    if os.path.exists(path):
                        pytesseract.pytesseract.tesseract_cmd = path
                        # テスト実行
                        test_img = Image.new('RGB', (100, 30), color='white')
                        pytesseract.image_to_string(test_img)
                        self.ocr_engine = 'tesseract'
                        print(f"Tesseract を設定しました: {path}")
                        return
                
                # パスが見つからない場合、デフォルトで試行
                test_img = Image.new('RGB', (100, 30), color='white')
                pytesseract.image_to_string(test_img)
                self.ocr_engine = 'tesseract'
                print("Tesseract をデフォルト設定で使用します")
                return
                
            except Exception as e:
                print(f"Tesseract設定エラー: {e}")
                TESSERACT_AVAILABLE = False
        
        # EasyOCRを試行
        if EASYOCR_AVAILABLE:
            try:
                self.easyocr_reader = easyocr.Reader(['ja', 'en'])
                self.ocr_engine = 'easyocr'
                print("EasyOCR を使用します")
                return
            except Exception as e:
                print(f"EasyOCR設定エラー: {e}")
                EASYOCR_AVAILABLE = False
        
        # OCRが利用できない場合
        self.ocr_engine = None
        print("警告: OCRエンジンが利用できません")
        
    def load_config(self):
        """設定ファイルを読み込む"""
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            return {
                "check_interval": 1.0,
                "ocr_language": "jpn+eng",
                "window_geometry": "1200x800"
            }
    
    def load_regions(self):
        """監視領域データを読み込み"""
        try:
            if os.path.exists(self.regions_file):
                with open(self.regions_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.monitoring_regions = data.get('region_sets', {})
                    self.current_region_set = data.get('current_set', "デフォルト")
                    print(f"監視領域データを読み込みました: {len(self.monitoring_regions)}セット")
        except Exception as e:
            print(f"監視領域データ読み込みエラー: {e}")
            self.monitoring_regions = {}
            self.current_region_set = "デフォルト"
    
    def save_config(self):
        """設定ファイルを保存"""
        # ウィンドウサイズも保存
        self.config["window_geometry"] = self.root.geometry()
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, ensure_ascii=False, indent=2)
    
    def save_regions(self):
        """監視領域データを保存"""
        try:
            data = {
                'region_sets': self.monitoring_regions,
                'current_set': self.current_region_set,
                'last_saved': datetime.datetime.now().isoformat()
            }
            with open(self.regions_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"監視領域データを保存しました: {len(self.monitoring_regions)}セット")
        except Exception as e:
            print(f"監視領域データ保存エラー: {e}")
            messagebox.showerror("エラー", f"データの保存に失敗しました: {e}")
    
    def get_current_regions(self):
        """現在選択中の監視領域リストを取得"""
        return self.monitoring_regions.get(self.current_region_set, [])
    
    def setup_ui(self):
        """UIを設定"""
        # メニューバー
        self.create_menu()
        
        # スクロール可能なメインフレーム
        self.create_scrollable_frame()
        
        # メインフレーム
        main_frame = ttk.Frame(self.scrollable_frame, padding="15")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # タイトル
        title_label = ttk.Label(main_frame, text="Text Recognition Macro System", 
                               font=("Arial", 18, "bold"))
        title_label.grid(row=0, column=0, columnspan=2, pady=(0, 20))
        
        # ショートカットキー情報
        self.create_shortcuts_info(main_frame, row=1)
        
        # 基本設定パネル
        self.create_settings_panel(main_frame, row=2)
        
        # 監視領域セット管理
        self.create_region_sets_panel(main_frame, row=3)
        
        # 監視領域管理
        self.create_regions_panel(main_frame, row=4)
        
        # 制御ボタン
        self.create_control_panel(main_frame, row=5)
        
        # ログ表示
        self.create_log_panel(main_frame, row=6)
        
        # 使用方法
        self.create_help_panel(main_frame, row=7)
        
    def create_menu(self):
        """メニューバーを作成"""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # ファイルメニュー
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="ファイル", menu=file_menu)
        file_menu.add_command(label="設定をインポート", command=self.import_config)
        file_menu.add_command(label="設定をエクスポート", command=self.export_config)
        file_menu.add_separator()
        file_menu.add_command(label="領域データをバックアップ", command=self.backup_regions)
        file_menu.add_command(label="領域データを復元", command=self.restore_regions)
        file_menu.add_separator()
        file_menu.add_command(label="終了", command=self.on_closing)
        
        # ヘルプメニュー
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="ヘルプ", menu=help_menu)
        help_menu.add_command(label="使用方法", command=self.show_help)
        help_menu.add_command(label="OCRセットアップ", command=self.install_ocr_engine)
        help_menu.add_command(label="バージョン情報", command=self.show_about)
    
    def create_scrollable_frame(self):
        """スクロール可能なメインフレームを作成"""
        self.main_canvas = tk.Canvas(self.root)
        self.scrollbar = ttk.Scrollbar(self.root, orient="vertical", command=self.main_canvas.yview)
        self.scrollable_frame = ttk.Frame(self.main_canvas)
        
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.main_canvas.configure(scrollregion=self.main_canvas.bbox("all"))
        )
        
        self.main_canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.main_canvas.configure(yscrollcommand=self.scrollbar.set)
        
        self.main_canvas.grid(row=0, column=0, sticky="nsew")
        self.scrollbar.grid(row=0, column=1, sticky="ns")
        
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=1)
        
        # マウスホイールでスクロール
        self.main_canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        
    def _on_mousewheel(self, event):
        """マウスホイールでスクロール"""
        self.main_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
    
    def create_shortcuts_info(self, parent, row):
        """ショートカットキー情報を作成"""
        shortcuts_frame = ttk.LabelFrame(parent, text="ショートカットキー", padding="10")
        shortcuts_frame.grid(row=row, column=0, columnspan=2, pady=(0, 15), sticky=(tk.W, tk.E))
        
        shortcuts_text = """F6: 監視開始/停止  |  F7: 領域追加  |  F8: 緊急停止  |  Ctrl+Alt+X: 緊急停止  |  ESC: 緊急停止"""
        
        ttk.Label(shortcuts_frame, text=shortcuts_text, font=("Arial", 10, "bold")).pack()
    
    def create_settings_panel(self, parent, row):
        """基本設定パネルを作成"""
        settings_frame = ttk.LabelFrame(parent, text="基本設定", padding="15")
        settings_frame.grid(row=row, column=0, columnspan=2, pady=(0, 15), sticky=(tk.W, tk.E))
        
        # チェック間隔
        ttk.Label(settings_frame, text="チェック間隔 (秒):").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        self.interval_var = tk.DoubleVar(value=self.config.get("check_interval", 1.0))
        ttk.Entry(settings_frame, textvariable=self.interval_var, width=10).grid(row=0, column=1, padx=(0, 20))
        
        # OCR言語
        ttk.Label(settings_frame, text="OCR言語:").grid(row=0, column=2, sticky=tk.W, padx=(0, 10))
        self.language_var = tk.StringVar(value=self.config.get("ocr_language", "jpn+eng"))
        ttk.Entry(settings_frame, textvariable=self.language_var, width=15).grid(row=0, column=3, padx=(0, 20))
        
        # OCRエンジン状態
        ttk.Label(settings_frame, text="OCRエンジン:").grid(row=0, column=4, sticky=tk.W, padx=(0, 10))
        ocr_status = self.ocr_engine if self.ocr_engine else "未設定"
        ocr_color = "green" if self.ocr_engine else "red"
        self.ocr_status_label = ttk.Label(settings_frame, text=ocr_status, foreground=ocr_color)
        self.ocr_status_label.grid(row=0, column=5, sticky=tk.W)
        
        if not self.ocr_engine:
            ttk.Button(settings_frame, text="OCRセットアップ", 
                      command=self.install_ocr_engine).grid(row=1, column=0, columnspan=2, pady=(10, 0), sticky=tk.W)
        
        # 設定保存ボタン
        ttk.Button(settings_frame, text="設定を保存", 
                  command=self.save_settings).grid(row=1, column=4, columnspan=2, pady=(10, 0), sticky=tk.E)
    
    def create_region_sets_panel(self, parent, row):
        """監視領域セット管理パネルを作成"""
        sets_frame = ttk.LabelFrame(parent, text="監視領域セット管理", padding="15")
        sets_frame.grid(row=row, column=0, columnspan=2, pady=(0, 15), sticky=(tk.W, tk.E))
        
        # 現在のセット表示
        current_frame = ttk.Frame(sets_frame)
        current_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(current_frame, text="現在のセット:").pack(side=tk.LEFT, padx=(0, 10))
        self.current_set_label = ttk.Label(current_frame, text=self.current_region_set, 
                                          font=("Arial", 11, "bold"))
        self.current_set_label.pack(side=tk.LEFT, padx=(0, 20))
        
        # セット名入力
        ttk.Label(current_frame, text="新しいセット名:").pack(side=tk.LEFT, padx=(20, 10))
        self.set_name_var = tk.StringVar(value="新しいセット")
        ttk.Entry(current_frame, textvariable=self.set_name_var, width=20).pack(side=tk.LEFT, padx=(0, 10))
        
        # セット操作ボタン
        buttons_frame = ttk.Frame(sets_frame)
        buttons_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Button(buttons_frame, text="現在の領域を保存", 
                  command=self.save_current_region_set, style="Accent.TButton").pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(buttons_frame, text="セットを読み込み", 
                  command=self.load_selected_region_set).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(buttons_frame, text="セットを削除", 
                  command=self.delete_selected_region_set).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(buttons_frame, text="現在の領域をクリア", 
                  command=self.clear_current_regions).pack(side=tk.LEFT)
        
        # セットリスト
        list_frame = ttk.Frame(sets_frame)
        list_frame.pack(fill=tk.BOTH, expand=True)
        
        columns = ("セット名", "領域数", "作成日時")
        self.sets_tree = ttk.Treeview(list_frame, columns=columns, show="headings", height=4)
        
        self.sets_tree.heading("セット名", text="セット名")
        self.sets_tree.heading("領域数", text="領域数")
        self.sets_tree.heading("作成日時", text="作成日時")
        
        self.sets_tree.column("セット名", width=200)
        self.sets_tree.column("領域数", width=80)
        self.sets_tree.column("作成日時", width=150)
        
        self.sets_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        sets_scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.sets_tree.yview)
        sets_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.sets_tree.configure(yscrollcommand=sets_scrollbar.set)
    
    def create_regions_panel(self, parent, row):
        """監視領域管理パネルを作成"""
        regions_frame = ttk.LabelFrame(parent, text="監視領域管理", padding="15")
        regions_frame.grid(row=row, column=0, columnspan=2, pady=(0, 15), sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 領域操作ボタン
        region_buttons_frame = ttk.Frame(regions_frame)
        region_buttons_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Button(region_buttons_frame, text="新しい領域を追加 (F7)", 
                  command=self.add_region, style="Accent.TButton").pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(region_buttons_frame, text="領域を編集", 
                  command=self.edit_region).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(region_buttons_frame, text="領域を削除", 
                  command=self.delete_region).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(region_buttons_frame, text="領域をテスト", 
                  command=self.test_region).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(region_buttons_frame, text="領域をプレビュー", 
                  command=self.preview_region).pack(side=tk.LEFT)
        
        # 領域リスト
        regions_list_frame = ttk.Frame(regions_frame)
        regions_list_frame.pack(fill=tk.BOTH, expand=True)
        
        columns = ("名前", "座標", "検索文字", "アクション数", "状態")
        self.regions_tree = ttk.Treeview(regions_list_frame, columns=columns, show="headings", height=8)
        
        self.regions_tree.heading("名前", text="名前")
        self.regions_tree.heading("座標", text="座標 (X,Y,W,H)")
        self.regions_tree.heading("検索文字", text="検索文字")
        self.regions_tree.heading("アクション数", text="アクション数")
        self.regions_tree.heading("状態", text="状態")
        
        self.regions_tree.column("名前", width=150)
        self.regions_tree.column("座標", width=120)
        self.regions_tree.column("検索文字", width=150)
        self.regions_tree.column("アクション数", width=80)
        self.regions_tree.column("状態", width=80)
        
        self.regions_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        regions_scrollbar = ttk.Scrollbar(regions_list_frame, orient=tk.VERTICAL, command=self.regions_tree.yview)
        regions_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.regions_tree.configure(yscrollcommand=regions_scrollbar.set)
        
        # ダブルクリックで編集
        self.regions_tree.bind("<Double-1>", lambda e: self.edit_region())
    
    def create_control_panel(self, parent, row):
        """制御パネルを作成"""
        control_frame = ttk.LabelFrame(parent, text="監視制御", padding="15")
        control_frame.grid(row=row, column=0, columnspan=2, pady=(0, 15), sticky=(tk.W, tk.E))
        
        # ステータス表示
        status_frame = ttk.Frame(control_frame)
        status_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(status_frame, text="ステータス:").pack(side=tk.LEFT, padx=(0, 10))
        self.status_var = tk.StringVar(value="待機中")
        self.status_label = ttk.Label(status_frame, textvariable=self.status_var, 
                                     font=("Arial", 11, "bold"), foreground="blue")
        self.status_label.pack(side=tk.LEFT)
        
        # 制御ボタン
        button_frame = ttk.Frame(control_frame)
        button_frame.pack(fill=tk.X)
        
        self.start_button = ttk.Button(button_frame, text="監視開始 (F6)", 
                                      command=self.start_monitoring, style="Accent.TButton")
        self.start_button.pack(side=tk.LEFT, padx=(0, 10))
        
        self.stop_button = ttk.Button(button_frame, text="監視停止 (F6)", 
                                     command=self.stop_monitoring, state=tk.DISABLED)
        self.stop_button.pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Button(button_frame, text="緊急停止 (F8)", 
                  command=self.emergency_stop).pack(side=tk.LEFT)
    
    def create_log_panel(self, parent, row):
        """ログパネルを作成"""
        log_frame = ttk.LabelFrame(parent, text="ログ", padding="10")
        log_frame.grid(row=row, column=0, columnspan=2, pady=(0, 15), sticky=(tk.W, tk.E))
        
        log_container = ttk.Frame(log_frame)
        log_container.pack(fill=tk.BOTH, expand=True)
        
        self.log_text = tk.Text(log_container, height=6, wrap=tk.WORD)
        log_scrollbar = ttk.Scrollbar(log_container, orient=tk.VERTICAL, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=log_scrollbar.set)
        
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        log_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # ログクリアボタン
        ttk.Button(log_frame, text="ログをクリア", command=self.clear_log).pack(pady=(5, 0))
    
    def create_help_panel(self, parent, row):
        """ヘルプパネルを作成"""
        help_frame = ttk.LabelFrame(parent, text="使用方法", padding="15")
        help_frame.grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E))
        
        help_text = """
📋 基本的な使用方法:
1. 「新しい領域を追加」をクリック (またはF7)
2. 画面上で監視したい領域をドラッグして選択
3. 検索したい文字とアクション（クリック位置など）を設定
4. 「監視開始」で自動監視を開始

🔧 高度な機能:
• 監視領域セット: 複数の設定を保存・切り替え可能
• 複数のアクション: クリック、キー入力、テキスト入力、待機など
• リアルタイムプレビュー: 領域の文字認識をテスト可能
• バックアップ・復元: 設定の完全なバックアップが可能

⚡ ショートカットキー:
F6: 監視開始/停止  |  F7: 領域追加  |  F8: 緊急停止
        """
        
        ttk.Label(help_frame, text=help_text, justify=tk.LEFT, 
                 font=("Arial", 10)).pack(anchor=tk.W)
        
        # ウィンドウクローズイベント
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
    
    # ===== ログ機能 =====
    def log(self, message):
        """ログを表示"""
        timestamp = time.strftime("%H:%M:%S")
        log_message = f"[{timestamp}] {message}\n"
        self.log_text.insert(tk.END, log_message)
        self.log_text.see(tk.END)
        self.root.update_idletasks()
        
    def clear_log(self):
        """ログをクリア"""
        self.log_text.delete('1.0', tk.END)
        self.log("ログをクリアしました")
    
    # ===== 設定管理 =====
    def save_settings(self):
        """設定を保存"""
        self.config["check_interval"] = self.interval_var.get()
        self.config["ocr_language"] = self.language_var.get()
        self.save_config()
        self.save_regions()
        self.log("設定を保存しました")
        messagebox.showinfo("保存完了", "設定を保存しました")
    
    # ===== データ管理 =====
    def update_region_sets_list(self):
        """監視領域セットリストを更新"""
        for item in self.sets_tree.get_children():
            self.sets_tree.delete(item)
        
        for set_name, regions in self.monitoring_regions.items():
            region_count = len(regions)
            # 作成日時は仮の値（実際は保存時に記録）
            created_at = "未記録"
            self.sets_tree.insert("", tk.END, values=(set_name, region_count, created_at))
    
    def update_regions_list(self):
        """現在の監視領域リストを更新"""
        for item in self.regions_tree.get_children():
            self.regions_tree.delete(item)
        
        current_regions = self.get_current_regions()
        for i, region in enumerate(current_regions):
            coordinates = f"({region['x']},{region['y']},{region['width']},{region['height']})"
            actions_count = len(region.get('actions', []))
            status = "有効" if region.get('enabled', True) else "無効"
            
            self.regions_tree.insert("", tk.END, values=(
                region['name'],
                coordinates,
                region['target_text'],
                actions_count,
                status
            ))
    
    # ===== 監視領域セット管理 =====
    def save_current_region_set(self):
        """現在の監視領域をセットとして保存"""
        set_name = self.set_name_var.get().strip()
        if not set_name:
            messagebox.showerror("エラー", "セット名を入力してください")
            return
            
        current_regions = self.get_current_regions()
        if len(current_regions) == 0:
            messagebox.showerror("エラー", "保存する監視領域がありません")
            return
            
        # 最大保存数チェック
        if len(self.monitoring_regions) >= self.max_region_sets and set_name not in self.monitoring_regions:
            messagebox.showerror("エラー", f"監視領域セットは最大{self.max_region_sets}個まで保存できます")
            return
        
        # セットを保存
        self.monitoring_regions[set_name] = current_regions.copy()
        self.current_region_set = set_name
        self.current_set_label.config(text=set_name)
        
        self.update_region_sets_list()
        self.save_regions()
        
        self.log(f"監視領域セット '{set_name}' を保存しました")
        messagebox.showinfo("成功", f"監視領域セット '{set_name}' を保存しました")
    
    def load_selected_region_set(self):
        """選択されたセットを読み込み"""
        selected = self.sets_tree.selection()
        if not selected:
            messagebox.showerror("エラー", "読み込むセットを選択してください")
            return
            
        item = selected[0]
        set_name = self.sets_tree.item(item, "values")[0]
        
        if set_name in self.monitoring_regions:
            self.current_region_set = set_name
            self.current_set_label.config(text=set_name)
            
            self.update_regions_list()
            self.log(f"監視領域セット '{set_name}' を読み込みました")
            messagebox.showinfo("成功", f"監視領域セット '{set_name}' を読み込みました")
        else:
            messagebox.showerror("エラー", "選択されたセットが見つかりません")
    
    def delete_selected_region_set(self):
        """選択されたセットを削除"""
        selected = self.sets_tree.selection()
        if not selected:
            messagebox.showerror("エラー", "削除するセットを選択してください")
            return
            
        item = selected[0]
        set_name = self.sets_tree.item(item, "values")[0]
        
        if messagebox.askyesno("確認", f"監視領域セット '{set_name}' を削除しますか？"):
            if set_name in self.monitoring_regions:
                del self.monitoring_regions[set_name]
                
                # 現在のセットが削除された場合、デフォルトに戻す
                if self.current_region_set == set_name:
                    self.current_region_set = "デフォルト"
                    self.current_set_label.config(text=self.current_region_set)
                    if "デフォルト" not in self.monitoring_regions:
                        self.monitoring_regions["デフォルト"] = []
                
                self.update_region_sets_list()
                self.update_regions_list()
                self.save_regions()
                
                self.log(f"監視領域セット '{set_name}' を削除しました")
                messagebox.showinfo("成功", f"監視領域セット '{set_name}' を削除しました")
    
    def clear_current_regions(self):
        """現在の監視領域をクリア"""
        if messagebox.askyesno("確認", "現在の監視領域をすべてクリアしますか？"):
            if self.current_region_set not in self.monitoring_regions:
                self.monitoring_regions[self.current_region_set] = []
            else:
                self.monitoring_regions[self.current_region_set].clear()
            
            self.update_regions_list()
            self.update_region_sets_list()
            self.save_regions()
            self.log("現在の監視領域をクリアしました")
    
    # ===== 監視領域管理 =====
    def add_region(self):
        """新しい監視領域を追加"""
        if self.is_selecting_region:
            self.log("既に領域選択中です")
            return
            
        self.is_selecting_region = True
        self.log("領域選択を開始します。画面上でドラッグして領域を選択してください...")
        self.select_region()
    
    def edit_region(self):
        """選択された監視領域を編集"""
        selected = self.regions_tree.selection()
        if not selected:
            messagebox.showerror("エラー", "編集する領域を選択してください")
            return
        
        item = selected[0]
        region_index = self.regions_tree.index(item)
        current_regions = self.get_current_regions()
        
        if 0 <= region_index < len(current_regions):
            region_data = current_regions[region_index]
            self.show_region_config_dialog(region_data, region_index)
    
    def delete_region(self):
        """選択された監視領域を削除"""
        selected = self.regions_tree.selection()
        if not selected:
            messagebox.showerror("エラー", "削除する領域を選択してください")
            return
        
        item = selected[0]
        region_index = self.regions_tree.index(item)
        current_regions = self.get_current_regions()
        
        if 0 <= region_index < len(current_regions):
            region_name = current_regions[region_index]['name']
            if messagebox.askyesno("確認", f"監視領域 '{region_name}' を削除しますか？"):
                del current_regions[region_index]
                
                # 現在のセットに変更を反映
                self.monitoring_regions[self.current_region_set] = current_regions
                
                self.update_regions_list()
                self.update_region_sets_list()
                self.save_regions()
                self.log(f"監視領域 '{region_name}' を削除しました")
    
    def test_region(self):
        """選択された監視領域をテスト"""
        selected = self.regions_tree.selection()
        if not selected:
            messagebox.showerror("エラー", "テストする領域を選択してください")
            return
        
        item = selected[0]
        region_index = self.regions_tree.index(item)
        current_regions = self.get_current_regions()
        
        if 0 <= region_index < len(current_regions):
            region = current_regions[region_index]
            
            try:
                # 領域をキャプチャ
                image = self.capture_region(region["x"], region["y"], region["width"], region["height"])
                text = self.extract_text_from_image(image)
                
                result = f"領域: {region['name']}\n"
                result += f"座標: ({region['x']}, {region['y']}, {region['width']}, {region['height']})\n"
                result += f"検索文字: '{region['target_text']}'\n"
                result += f"検出された文字: '{text}'\n"
                result += f"一致: {'はい' if self.check_text_match(text, region['target_text']) else 'いいえ'}"
                
                messagebox.showinfo("テスト結果", result)
                self.log(f"テスト実行: {region['name']} - 検出文字: '{text}'")
                
            except Exception as e:
                messagebox.showerror("エラー", f"テストに失敗しました: {e}")
    
    def preview_region(self):
        """選択された監視領域をプレビュー"""
        selected = self.regions_tree.selection()
        if not selected:
            messagebox.showerror("エラー", "プレビューする領域を選択してください")
            return
        
        item = selected[0]
        region_index = self.regions_tree.index(item)
        current_regions = self.get_current_regions()
        
        if 0 <= region_index < len(current_regions):
            region = current_regions[region_index]
            self.show_region_preview(region)
    
    # ===== 監視制御 =====
    def start_monitoring(self):
        """監視を開始"""
        if self.running:
            self.log("すでに監視中です")
            return
            
        current_regions = self.get_current_regions()
        if not current_regions:
            messagebox.showwarning("警告", "監視する領域が設定されていません")
            return
        
        if not self.ocr_engine:
            if not messagebox.askyesno("確認", "OCRエンジンが設定されていません。簡易モードで続行しますか？"):
                return
        
        self.running = True
        self.monitoring_thread = threading.Thread(target=self.monitor_worker)
        self.monitoring_thread.daemon = True
        self.monitoring_thread.start()
        
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        self.status_var.set("監視中")
        self.status_label.config(foreground="green")
        
        self.log("監視を開始しました")
        self.show_notification("監視を開始しました")
    
    def stop_monitoring(self):
        """監視を停止"""
        if not self.running:
            self.log("監視は実行されていません")
            return
        
        self.running = False
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=2)
        
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self.status_var.set("停止")
        self.status_label.config(foreground="red")
        
        self.log("監視を停止しました")
        self.show_notification("監視を停止しました")
    
    def monitor_worker(self):
        """監視のメインループ"""
        self.log("監視ループを開始しました")
        
        while self.running:
            try:
                current_regions = self.get_current_regions()
                for region in current_regions:
                    if not self.running:
                        break
                    
                    # 無効な領域はスキップ
                    if not region.get('enabled', True):
                        continue
                    
                    name = region["name"]
                    x, y = region["x"], region["y"]
                    width, height = region["width"], region["height"]
                    target_text = region["target_text"]
                    actions = region.get("actions", [])
                    
                    # 領域をキャプチャ
                    image = self.capture_region(x, y, width, height)
                    
                    # 文字を抽出
                    detected_text = self.extract_text_from_image(
                        image, 
                        self.config.get("ocr_language", "jpn+eng")
                    )
                    
                    # 文字が一致したかチェック
                    if detected_text and self.check_text_match(detected_text, target_text):
                        self.root.after(0, lambda: self.log(f"[{name}] 文字が一致: '{detected_text}' → アクション実行"))
                        
                        # アクションを実行
                        for action in actions:
                            if not self.running:
                                break
                            self.execute_action(action)
                            time.sleep(0.1)
                
                # 次のチェックまで待機
                time.sleep(self.config.get("check_interval", 1.0))
                
            except Exception as e:
                self.root.after(0, lambda: self.log(f"監視エラー: {e}"))
                time.sleep(1)
        
        self.root.after(0, lambda: self.log("監視ループを終了しました"))
    
    # ===== 新しい領域設定ダイアログ（AutoClickerスタイル） =====
    def show_region_config_dialog(self, region_data=None, region_index=None):
        """監視領域設定ダイアログを表示（AutoClickerスタイル）"""
        dialog = tk.Toplevel(self.root)
        dialog.title("監視領域設定")
        dialog.geometry("800x700")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # スクロール可能なフレーム
        canvas = tk.Canvas(dialog)
        scrollbar = ttk.Scrollbar(dialog, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        main_frame = ttk.Frame(scrollable_frame, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # デフォルトデータ
        if region_data is None:
            if hasattr(self, 'selected_region'):
                region_data = {
                    "name": "",
                    "x": self.selected_region["x"],
                    "y": self.selected_region["y"],
                    "width": self.selected_region["width"],
                    "height": self.selected_region["height"],
                    "target_text": "",
                    "enabled": True,
                    "actions": []
                }
            else:
                region_data = {
                    "name": "",
                    "x": 0, "y": 0, "width": 100, "height": 50,
                    "target_text": "",
                    "enabled": True,
                    "actions": []
                }
        
        # タイトル
        title_text = "監視領域を編集" if region_index is not None else "新しい監視領域を追加"
        ttk.Label(main_frame, text=title_text, font=("Arial", 16, "bold")).pack(pady=(0, 20))
        
        # 基本設定
        basic_frame = ttk.LabelFrame(main_frame, text="基本設定", padding="15")
        basic_frame.pack(fill=tk.X, pady=(0, 15))
        
        # 名前
        ttk.Label(basic_frame, text="名前:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10), pady=5)
        name_var = tk.StringVar(value=region_data["name"])
        ttk.Entry(basic_frame, textvariable=name_var, width=40).grid(row=0, column=1, sticky=tk.W, pady=5)
        
        # 有効/無効
        enabled_var = tk.BooleanVar(value=region_data.get("enabled", True))
        ttk.Checkbutton(basic_frame, text="この領域を有効にする", variable=enabled_var).grid(row=0, column=2, padx=(20, 0), pady=5)
        
        # 座標設定
        coord_frame = ttk.LabelFrame(main_frame, text="監視領域座標", padding="15")
        coord_frame.pack(fill=tk.X, pady=(0, 15))
        
        ttk.Label(coord_frame, text="X座標:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        x_var = tk.IntVar(value=region_data["x"])
        ttk.Entry(coord_frame, textvariable=x_var, width=15).grid(row=0, column=1, padx=(0, 20))
        
        ttk.Label(coord_frame, text="Y座標:").grid(row=0, column=2, sticky=tk.W, padx=(0, 10))
        y_var = tk.IntVar(value=region_data["y"])
        ttk.Entry(coord_frame, textvariable=y_var, width=15).grid(row=0, column=3, padx=(0, 20))
        
        ttk.Label(coord_frame, text="幅:").grid(row=1, column=0, sticky=tk.W, padx=(0, 10), pady=(10, 0))
        width_var = tk.IntVar(value=region_data["width"])
        ttk.Entry(coord_frame, textvariable=width_var, width=15).grid(row=1, column=1, padx=(0, 20), pady=(10, 0))
        
        ttk.Label(coord_frame, text="高さ:").grid(row=1, column=2, sticky=tk.W, padx=(0, 10), pady=(10, 0))
        height_var = tk.IntVar(value=region_data["height"])
        ttk.Entry(coord_frame, textvariable=height_var, width=15).grid(row=1, column=3, pady=(10, 0))
        
        # 領域再選択ボタン
        ttk.Button(coord_frame, text="領域を再選択", 
                  command=lambda: self.reselect_region(dialog, x_var, y_var, width_var, height_var)).grid(row=2, column=0, columnspan=2, pady=(15, 0))
        
        # プレビューボタン
        ttk.Button(coord_frame, text="領域をプレビュー", 
                  command=lambda: self.preview_coordinates(x_var.get(), y_var.get(), width_var.get(), height_var.get())).grid(row=2, column=2, columnspan=2, pady=(15, 0))
        
        # 検索文字設定
        text_frame = ttk.LabelFrame(main_frame, text="検索文字設定", padding="15")
        text_frame.pack(fill=tk.X, pady=(0, 15))
        
        ttk.Label(text_frame, text="検索する文字:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        target_text_var = tk.StringVar(value=region_data["target_text"])
        ttk.Entry(text_frame, textvariable=target_text_var, width=40).grid(row=0, column=1, sticky=tk.W)
        
        # OCRテストボタン
        ttk.Button(text_frame, text="OCRテスト", 
                  command=lambda: self.test_ocr_current(x_var.get(), y_var.get(), width_var.get(), height_var.get())).grid(row=0, column=2, padx=(20, 0))
        
        # アクション設定
        self.create_action_settings(main_frame, region_data.get("actions", []))
        
        # 保存・キャンセルボタン
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(20, 0))
        
        def save_region():
            try:
                new_region = {
                    "name": name_var.get(),
                    "x": x_var.get(),
                    "y": y_var.get(),
                    "width": width_var.get(),
                    "height": height_var.get(),
                    "target_text": target_text_var.get(),
                    "enabled": enabled_var.get(),
                    "actions": self.get_actions_from_settings()
                }
                
                # 現在のセットを取得・更新
                current_regions = self.get_current_regions()
                if self.current_region_set not in self.monitoring_regions:
                    self.monitoring_regions[self.current_region_set] = []
                    current_regions = []
                
                if region_index is not None:
                    # 編集の場合
                    current_regions[region_index] = new_region
                    self.log(f"監視領域 '{new_region['name']}' を更新しました")
                else:
                    # 新規追加の場合
                    current_regions.append(new_region)
                    self.log(f"監視領域 '{new_region['name']}' を追加しました")
                
                # データを保存
                self.monitoring_regions[self.current_region_set] = current_regions
                
                self.update_regions_list()
                self.update_region_sets_list()
                self.save_regions()
                
                dialog.destroy()
                
                # 選択された領域情報をクリア
                if hasattr(self, 'selected_region'):
                    delattr(self, 'selected_region')
                
            except Exception as e:
                messagebox.showerror("エラー", f"設定の保存に失敗しました: {e}")
        
        ttk.Button(button_frame, text="保存", command=save_region, style="Accent.TButton").pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(button_frame, text="キャンセル", command=dialog.destroy).pack(side=tk.LEFT)
    
    def create_action_settings(self, parent, existing_actions):
        """アクション設定UI（AutoClickerスタイル）を作成"""
        action_frame = ttk.LabelFrame(parent, text="アクション設定", padding="15")
        action_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 15))
        
        # アクションリスト
        actions_list_frame = ttk.Frame(action_frame)
        actions_list_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 15))
        
        # アクション一覧のTreeview
        columns = ("順番", "種類", "詳細", "座標")
        self.actions_tree = ttk.Treeview(actions_list_frame, columns=columns, show="headings", height=6)
        
        self.actions_tree.heading("順番", text="順番")
        self.actions_tree.heading("種類", text="アクション種類")
        self.actions_tree.heading("詳細", text="詳細")
        self.actions_tree.heading("座標", text="座標")
        
        self.actions_tree.column("順番", width=50)
        self.actions_tree.column("種類", width=100)
        self.actions_tree.column("詳細", width=200)
        self.actions_tree.column("座標", width=100)
        
        self.actions_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        actions_scrollbar = ttk.Scrollbar(actions_list_frame, orient=tk.VERTICAL, command=self.actions_tree.yview)
        actions_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.actions_tree.configure(yscrollcommand=actions_scrollbar.set)
        
        # アクション操作ボタン
        action_buttons_frame = ttk.Frame(action_frame)
        action_buttons_frame.pack(fill=tk.X, pady=(0, 15))
        
        ttk.Button(action_buttons_frame, text="アクションを追加", 
                  command=self.add_action).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(action_buttons_frame, text="アクションを編集", 
                  command=self.edit_action).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(action_buttons_frame, text="アクションを削除", 
                  command=self.delete_action).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(action_buttons_frame, text="上に移動", 
                  command=self.move_action_up).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(action_buttons_frame, text="下に移動", 
                  command=self.move_action_down).pack(side=tk.LEFT)
        
        # アクションデータを保存するリスト
        self.current_actions = existing_actions.copy() if existing_actions else []
        self.update_actions_list()
    
    def update_actions_list(self):
        """アクションリストを更新"""
        # 既存のアイテムを削除
        for item in self.actions_tree.get_children():
            self.actions_tree.delete(item)
        
        # 新しいアイテムを追加
        for i, action in enumerate(self.current_actions, 1):
            action_type = action.get("type", "")
            details = self.get_action_details_text(action)
            coordinates = self.get_action_coordinates_text(action)
            
            self.actions_tree.insert("", tk.END, values=(i, action_type, details, coordinates))
    
    def get_action_details_text(self, action):
        """アクションの詳細テキストを取得"""
        action_type = action.get("type", "")
        
        if action_type == "click":
            return f"クリック"
        elif action_type == "key":
            return f"キー: {action.get('key', '')}"
        elif action_type == "hotkey":
            keys = action.get('keys', [])
            return f"ホットキー: {'+'.join(keys)}"
        elif action_type == "type":
            text = action.get('text', '')
            return f"テキスト: {text[:20]}" + ("..." if len(text) > 20 else "")
        elif action_type == "move":
            return "マウス移動"
        elif action_type == "wait":
            return f"待機: {action.get('duration', 0)}秒"
        else:
            return action_type
    
    def get_action_coordinates_text(self, action):
        """アクションの座標テキストを取得"""
        action_type = action.get("type", "")
        
        if action_type in ["click", "move"]:
            x = action.get('x', 0)
            y = action.get('y', 0)
            return f"({x}, {y})"
        else:
            return "-"
    
    def add_action(self):
        """新しいアクションを追加"""
        self.show_action_dialog()
    
    def edit_action(self):
        """選択されたアクションを編集"""
        selected = self.actions_tree.selection()
        if not selected:
            messagebox.showerror("エラー", "編集するアクションを選択してください")
            return
        
        item = selected[0]
        action_index = int(self.actions_tree.item(item, "values")[0]) - 1
        
        if 0 <= action_index < len(self.current_actions):
            self.show_action_dialog(self.current_actions[action_index], action_index)
    
    def delete_action(self):
        """選択されたアクションを削除"""
        selected = self.actions_tree.selection()
        if not selected:
            messagebox.showerror("エラー", "削除するアクションを選択してください")
            return
        
        item = selected[0]
        action_index = int(self.actions_tree.item(item, "values")[0]) - 1
        
        if 0 <= action_index < len(self.current_actions):
            if messagebox.askyesno("確認", "選択されたアクションを削除しますか？"):
                del self.current_actions[action_index]
                self.update_actions_list()
    
    def move_action_up(self):
        """アクションを上に移動"""
        selected = self.actions_tree.selection()
        if not selected:
            return
        
        item = selected[0]
        action_index = int(self.actions_tree.item(item, "values")[0]) - 1
        
        if action_index > 0:
            self.current_actions[action_index], self.current_actions[action_index-1] = \
                self.current_actions[action_index-1], self.current_actions[action_index]
            self.update_actions_list()
    
    def move_action_down(self):
        """アクションを下に移動"""
        selected = self.actions_tree.selection()
        if not selected:
            return
        
        item = selected[0]
        action_index = int(self.actions_tree.item(item, "values")[0]) - 1
        
        if action_index < len(self.current_actions) - 1:
            self.current_actions[action_index], self.current_actions[action_index+1] = \
                self.current_actions[action_index+1], self.current_actions[action_index]
            self.update_actions_list()
    
    def get_actions_from_settings(self):
        """設定からアクションリストを取得"""
        return self.current_actions.copy()
    
    def show_action_dialog(self, action_data=None, action_index=None):
        """アクション設定ダイアログを表示（AutoClickerスタイル）"""
        dialog = tk.Toplevel(self.root)
        dialog.title("アクション設定")
        dialog.geometry("600x500")
        dialog.transient(self.root)
        dialog.grab_set()
        
        main_frame = ttk.Frame(dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # デフォルトデータ
        if action_data is None:
            action_data = {"type": "click", "x": 100, "y": 100}
        
        # タイトル
        title_text = "アクションを編集" if action_index is not None else "新しいアクションを追加"
        ttk.Label(main_frame, text=title_text, font=("Arial", 14, "bold")).pack(pady=(0, 20))
        
        # アクション種類選択
        type_frame = ttk.LabelFrame(main_frame, text="アクション種類", padding="15")
        type_frame.pack(fill=tk.X, pady=(0, 15))
        
        action_type_var = tk.StringVar(value=action_data.get("type", "click"))
        action_types = [
            ("click", "クリック"),
            ("key", "キー入力"),
            ("hotkey", "ホットキー"),
            ("type", "テキスト入力"),
            ("move", "マウス移動"),
            ("wait", "待機")
        ]
        
        for i, (value, text) in enumerate(action_types):
            ttk.Radiobutton(type_frame, text=text, variable=action_type_var, 
                           value=value).grid(row=i//2, column=i%2, sticky=tk.W, padx=(0, 20), pady=2)
        
        # 詳細設定フレーム
        detail_frame = ttk.LabelFrame(main_frame, text="詳細設定", padding="15")
        detail_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 15))
        
        # 詳細設定用の変数
        x_var = tk.IntVar(value=action_data.get("x", 100))
        y_var = tk.IntVar(value=action_data.get("y", 100))
        key_var = tk.StringVar(value=action_data.get("key", "space"))
        text_var = tk.StringVar(value=action_data.get("text", "Hello"))
        wait_var = tk.DoubleVar(value=action_data.get("duration", 1.0))
        hotkeys_var = tk.StringVar(value="+".join(action_data.get("keys", ["ctrl", "c"])))
        
        self.current_action_vars = {
            'x': x_var, 'y': y_var, 'key': key_var, 
            'text': text_var, 'wait': wait_var, 'hotkeys': hotkeys_var
        }
        
        def update_detail_settings(*args):
            # 詳細フレームをクリア
            for widget in detail_frame.winfo_children():
                widget.destroy()
            
            action_type = action_type_var.get()
            
            if action_type == "click":
                ttk.Label(detail_frame, text="X座標:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
                ttk.Entry(detail_frame, textvariable=x_var, width=15).grid(row=0, column=1, padx=(0, 20))
                ttk.Label(detail_frame, text="Y座標:").grid(row=0, column=2, sticky=tk.W, padx=(0, 10))
                ttk.Entry(detail_frame, textvariable=y_var, width=15).grid(row=0, column=3)
                
                ttk.Button(detail_frame, text="座標を選択", 
                          command=lambda: self.select_action_position(dialog, action_type_var.get(), x_var, y_var)).grid(row=1, column=0, columnspan=2, pady=(10, 0))
                
            elif action_type == "key":
                ttk.Label(detail_frame, text="キー:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
                ttk.Entry(detail_frame, textvariable=key_var, width=30).grid(row=0, column=1)
                ttk.Label(detail_frame, text="例: space, enter, f1, ctrl").grid(row=1, column=0, columnspan=2, sticky=tk.W, pady=(5, 0))
                
            elif action_type == "hotkey":
                ttk.Label(detail_frame, text="ホットキー:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
                ttk.Entry(detail_frame, textvariable=hotkeys_var, width=30).grid(row=0, column=1)
                ttk.Label(detail_frame, text="例: ctrl+c, alt+tab, ctrl+shift+n (+ で区切る)").grid(row=1, column=0, columnspan=2, sticky=tk.W, pady=(5, 0))
                
            elif action_type == "type":
                ttk.Label(detail_frame, text="入力するテキスト:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
                text_entry = tk.Text(detail_frame, width=40, height=4)
                text_entry.grid(row=1, column=0, columnspan=2, pady=(5, 0))
                text_entry.insert('1.0', text_var.get())
                
                # テキスト変更を監視
                def update_text_var(*args):
                    text_var.set(text_entry.get('1.0', tk.END).strip())
                text_entry.bind('<KeyRelease>', update_text_var)
                
            elif action_type == "move":
                ttk.Label(detail_frame, text="X座標:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
                ttk.Entry(detail_frame, textvariable=x_var, width=15).grid(row=0, column=1, padx=(0, 20))
                ttk.Label(detail_frame, text="Y座標:").grid(row=0, column=2, sticky=tk.W, padx=(0, 10))
                ttk.Entry(detail_frame, textvariable=y_var, width=15).grid(row=0, column=3)
                
                ttk.Button(detail_frame, text="座標を選択", 
                          command=lambda: self.select_action_position(dialog, action_type_var.get(), x_var, y_var)).grid(row=1, column=0, columnspan=2, pady=(10, 0))
                
            elif action_type == "wait":
                ttk.Label(detail_frame, text="待機時間 (秒):").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
                ttk.Entry(detail_frame, textvariable=wait_var, width=15).grid(row=0, column=1)
        
        action_type_var.trace('w', update_detail_settings)
        update_detail_settings()  # 初期表示
        
        # 保存・キャンセルボタン
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(20, 0))
        
        def save_action():
            try:
                action_type = action_type_var.get()
                new_action = {"type": action_type}
                
                if action_type == "click":
                    new_action.update({"x": x_var.get(), "y": y_var.get()})
                elif action_type == "key":
                    new_action.update({"key": key_var.get()})
                elif action_type == "hotkey":
                    keys = [k.strip() for k in hotkeys_var.get().split('+')]
                    new_action.update({"keys": keys})
                elif action_type == "type":
                    new_action.update({"text": text_var.get()})
                elif action_type == "move":
                    new_action.update({"x": x_var.get(), "y": y_var.get()})
                elif action_type == "wait":
                    new_action.update({"duration": wait_var.get()})
                
                if action_index is not None:
                    self.current_actions[action_index] = new_action
                else:
                    self.current_actions.append(new_action)
                
                self.update_actions_list()
                dialog.destroy()
                
            except Exception as e:
                messagebox.showerror("エラー", f"アクションの保存に失敗しました: {e}")
        
        ttk.Button(button_frame, text="保存", command=save_action, style="Accent.TButton").pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(button_frame, text="キャンセル", command=dialog.destroy).pack(side=tk.LEFT)
    
    def select_action_position(self, parent_dialog, action_type, x_var, y_var):
        """アクション用の座標を選択"""
        if self.is_selecting_action_position:
            return
        
        self.is_selecting_action_position = True
        parent_dialog.withdraw()  # 親ダイアログを隠す
        
        self.log(f"{action_type} の座標選択を開始します...")
        
        def capture_position():
            try:
                if self.is_selecting_action_position:
                    x, y = pyautogui.position()
                    x_var.set(x)
                    y_var.set(y)
                    self.log(f"座標を設定しました: ({x}, {y})")
                    self.is_selecting_action_position = False
                    parent_dialog.deiconify()  # 親ダイアログを表示
                    try:
                        import keyboard
                        keyboard.remove_hotkey('ctrl+shift+c')
                    except:
                        pass
            except Exception as e:
                self.log(f"座標選択エラー: {e}")
        
        try:
            import keyboard
            keyboard.add_hotkey('ctrl+shift+c', capture_position)
            self.show_notification("Ctrl+Shift+C で座標を選択してください")
        except Exception as e:
            self.log(f"座標選択機能エラー: {e}")
            self.is_selecting_action_position = False
            parent_dialog.deiconify()
    
    def cancel_action_selection(self):
        """アクション座標選択をキャンセル"""
        self.is_selecting_action_position = False
        try:
            import keyboard
            keyboard.remove_hotkey('ctrl+shift+c')
        except:
            pass
    
    def select_region(self):
        """画面領域選択を開始"""
        self.root.withdraw()  # メインウィンドウを隠す
        self.is_selecting_region = True
        
        # 全画面キャプチャ用のウィンドウを作成
        self.selection_window = tk.Toplevel(self.root)
        self.selection_window.attributes('-fullscreen', True)
        self.selection_window.attributes('-alpha', 0.3)
        self.selection_window.configure(bg='gray')
        self.selection_window.attributes('-topmost', True)
        
        # キャンバスを作成
        self.canvas = tk.Canvas(self.selection_window, highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        # マウスイベントをバインド
        self.canvas.bind('<Button-1>', self.on_mouse_down)
        self.canvas.bind('<B1-Motion>', self.on_mouse_drag)
        self.canvas.bind('<ButtonRelease-1>', self.on_mouse_up)
        
        # ESCキーでキャンセル
        self.selection_window.bind('<Escape>', lambda e: self.cancel_region_selection())
        self.selection_window.focus_set()
        
        # 選択開始位置
        self.start_x = None
        self.start_y = None
        self.rect_id = None
        
        self.log("画面上で領域をドラッグして選択してください（ESCでキャンセル）")
    
    def on_mouse_down(self, event):
        """マウスボタン押下時"""
        self.start_x = event.x_root
        self.start_y = event.y_root
        
        # 既存の選択矩形を削除
        if self.rect_id:
            self.canvas.delete(self.rect_id)
    
    def on_mouse_drag(self, event):
        """マウスドラッグ時"""
        if self.start_x is None or self.start_y is None:
            return
        
        # 既存の選択矩形を削除
        if self.rect_id:
            self.canvas.delete(self.rect_id)
        
        # 新しい選択矩形を描画
        self.rect_id = self.canvas.create_rectangle(
            self.start_x, self.start_y, event.x_root, event.y_root,
            outline='red', width=2, fill='', dash=(5, 5)
        )
    
    def on_mouse_up(self, event):
        """マウスボタン離上時"""
        if self.start_x is None or self.start_y is None:
            return
        
        # 選択領域の座標を計算
        end_x = event.x_root
        end_y = event.y_root
        
        x = min(self.start_x, end_x)
        y = min(self.start_y, end_y)
        width = abs(end_x - self.start_x)
        height = abs(end_y - self.start_y)
        
        # 最小サイズチェック
        if width < 10 or height < 10:
            messagebox.showwarning("警告", "選択領域が小さすぎます。もう一度選択してください。")
            self.cancel_region_selection()
            return
        
        # 選択された領域を保存
        self.selected_region = {
            'x': x,
            'y': y,
            'width': width,
            'height': height
        }
        
        # 選択ウィンドウを閉じる
        self.selection_window.destroy()
        self.selection_window = None
        self.root.deiconify()
        self.is_selecting_region = False
        
        # コールバックがあれば実行
        if hasattr(self, 'region_selection_callback') and self.region_selection_callback:
            self.region_selection_callback()
        else:
            # デフォルトの動作：新しい領域追加ダイアログを表示
            self.show_add_region_dialog()
        
        self.log(f"領域を選択しました: ({x}, {y}, {width}, {height})")
    
    def show_add_region_dialog(self):
        """新しい領域追加ダイアログを表示"""
        if not hasattr(self, 'selected_region'):
            messagebox.showerror("エラー", "領域が選択されていません")
            return
        
        region = self.selected_region
        
        # ダイアログウィンドウを作成
        dialog = tk.Toplevel(self.root)
        dialog.title("新しい領域を追加")
        dialog.geometry("500x600")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # 領域情報表示
        info_frame = ttk.LabelFrame(dialog, text="選択された領域")
        info_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Label(info_frame, text=f"座標: ({region['x']}, {region['y']})").pack(anchor=tk.W, padx=5)
        ttk.Label(info_frame, text=f"サイズ: {region['width']} x {region['height']}").pack(anchor=tk.W, padx=5)
        
        # 領域名入力
        name_frame = ttk.LabelFrame(dialog, text="領域設定")
        name_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Label(name_frame, text="領域名:").pack(anchor=tk.W, padx=5)
        name_var = tk.StringVar(value=f"領域_{len(self.get_current_regions()) + 1}")
        name_entry = ttk.Entry(name_frame, textvariable=name_var, width=40)
        name_entry.pack(fill=tk.X, padx=5, pady=2)
        
        # 検索文字入力
        ttk.Label(name_frame, text="検索する文字:").pack(anchor=tk.W, padx=5)
        search_var = tk.StringVar()
        search_entry = ttk.Entry(name_frame, textvariable=search_var, width=40)
        search_entry.pack(fill=tk.X, padx=5, pady=2)
        
        # OCRテストボタン
        test_frame = ttk.Frame(name_frame)
        test_frame.pack(fill=tk.X, padx=5, pady=5)
        
        def test_ocr():
            try:
                image = self.capture_region(region['x'], region['y'], region['width'], region['height'])
                text = self.extract_text_from_image(image)
                messagebox.showinfo("OCRテスト結果", f"検出されたテキスト:\n'{text}'")
                if text and not search_var.get():
                    search_var.set(text.strip())
            except Exception as e:
                messagebox.showerror("エラー", f"OCRテストに失敗しました: {e}")
        
        ttk.Button(test_frame, text="OCRテスト", command=test_ocr).pack(side=tk.LEFT)
        
        # アクション設定
        action_frame = ttk.LabelFrame(dialog, text="アクション設定")
        action_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # アクションリスト
        actions_list = tk.Listbox(action_frame, height=6)
        actions_list.pack(fill=tk.BOTH, expand=True, padx=5, pady=2)
        
        actions_data = []
        
        def add_action():
            action_dialog = self.create_action_dialog(dialog)
            if action_dialog:
                actions_data.append(action_dialog)
                actions_list.insert(tk.END, f"{action_dialog['type']}: {action_dialog.get('description', '')}")
        
        def edit_action():
            selected = actions_list.curselection()
            if not selected:
                messagebox.showwarning("警告", "編集するアクションを選択してください")
                return
            
            index = selected[0]
            action_data = actions_data[index]
            
            edited_action = self.create_action_dialog(dialog, action_data)
            if edited_action:
                actions_data[index] = edited_action
                actions_list.delete(index)
                actions_list.insert(index, f"{edited_action['type']}: {edited_action.get('description', '')}")
        
        def remove_action():
            selected = actions_list.curselection()
            if not selected:
                messagebox.showwarning("警告", "削除するアクションを選択してください")
                return
            
            index = selected[0]
            actions_list.delete(index)
            actions_data.pop(index)
        
        # アクション操作ボタン
        action_btn_frame = ttk.Frame(action_frame)
        action_btn_frame.pack(fill=tk.X, padx=5, pady=2)
        
        ttk.Button(action_btn_frame, text="追加", command=add_action).pack(side=tk.LEFT, padx=2)
        ttk.Button(action_btn_frame, text="編集", command=edit_action).pack(side=tk.LEFT, padx=2)
        ttk.Button(action_btn_frame, text="削除", command=remove_action).pack(side=tk.LEFT, padx=2)
        
        # デフォルトアクションを追加
        default_action = {
            'type': 'click',
            'x': region['x'] + region['width'] // 2,
            'y': region['y'] + region['height'] // 2,
            'button': 'left',
            'description': f"座標 ({region['x'] + region['width'] // 2}, {region['y'] + region['height'] // 2}) をクリック"
        }
        actions_data.append(default_action)
        actions_list.insert(tk.END, f"{default_action['type']}: {default_action['description']}")
        
        # ボタン
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(fill=tk.X, padx=10, pady=10)
        
        def save_region():
            if not name_var.get().strip():
                messagebox.showwarning("警告", "領域名を入力してください")
                return
            
            if not search_var.get().strip():
                messagebox.showwarning("警告", "検索する文字を入力してください")
                return
            
            if not actions_data:
                messagebox.showwarning("警告", "少なくとも1つのアクションを設定してください")
                return
            
            # 新しい領域を作成
            new_region = {
                'name': name_var.get().strip(),
                'x': region['x'],
                'y': region['y'],
                'width': region['width'],
                'height': region['height'],
                'search_text': search_var.get().strip(),
                'actions': actions_data.copy(),
                'enabled': True
            }
            
            # 現在のセットに追加
            current_regions = self.get_current_regions()
            current_regions.append(new_region)
            
            # UIを更新
            self.update_regions_list()
            self.save_regions()
            
            self.log(f"新しい領域を追加しました: {new_region['name']}")
            dialog.destroy()
        
        ttk.Button(btn_frame, text="保存", command=save_region).pack(side=tk.RIGHT, padx=5)
        ttk.Button(btn_frame, text="キャンセル", command=dialog.destroy).pack(side=tk.RIGHT)
        
        # フォーカスを名前入力欄に設定
        name_entry.focus_set()
    
    def create_action_dialog(self, parent=None, action_data=None):
        """アクション設定ダイアログを作成"""
        dialog = tk.Toplevel(parent or self.root)
        dialog.title("アクション設定")
        dialog.geometry("400x500")
        dialog.transient(parent or self.root)
        dialog.grab_set()
        
        result = {}
        
        # アクションタイプ選択
        type_frame = ttk.LabelFrame(dialog, text="アクションタイプ")
        type_frame.pack(fill=tk.X, padx=10, pady=5)
        
        action_type = tk.StringVar(value=action_data.get('type', 'click') if action_data else 'click')
        
        ttk.Radiobutton(type_frame, text="マウスクリック", variable=action_type, value="click").pack(anchor=tk.W, padx=5)
        ttk.Radiobutton(type_frame, text="キーボード入力", variable=action_type, value="key").pack(anchor=tk.W, padx=5)
        ttk.Radiobutton(type_frame, text="待機", variable=action_type, value="wait").pack(anchor=tk.W, padx=5)
        ttk.Radiobutton(type_frame, text="複合アクション", variable=action_type, value="compound").pack(anchor=tk.W, padx=5)
        
        # 共通設定フレーム（動的に変更）
        settings_frame = ttk.LabelFrame(dialog, text="設定")
        settings_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # 設定変数
        x_var = tk.IntVar(value=action_data.get('x', 0) if action_data else 0)
        y_var = tk.IntVar(value=action_data.get('y', 0) if action_data else 0)
        button_var = tk.StringVar(value=action_data.get('button', 'left') if action_data else 'left')
        key_var = tk.StringVar(value=action_data.get('key', '') if action_data else '')
        text_var = tk.StringVar(value=action_data.get('text', '') if action_data else '')
        wait_var = tk.DoubleVar(value=action_data.get('duration', 1.0) if action_data else 1.0)
        
        def update_settings_frame():
            """設定フレームの内容を更新"""
            # 既存のウィジェットを削除
            for widget in settings_frame.winfo_children():
                widget.destroy()
            
            action_t = action_type.get()
            
            if action_t == 'click':
                # マウスクリック設定
                coord_frame = ttk.Frame(settings_frame)
                coord_frame.pack(fill=tk.X, padx=5, pady=2)
                
                ttk.Label(coord_frame, text="X座標:").pack(side=tk.LEFT)
                ttk.Entry(coord_frame, textvariable=x_var, width=10).pack(side=tk.LEFT, padx=5)
                ttk.Label(coord_frame, text="Y座標:").pack(side=tk.LEFT, padx=(10,0))
                ttk.Entry(coord_frame, textvariable=y_var, width=10).pack(side=tk.LEFT, padx=5)
                
                def select_coordinates():
                    self.select_action_coordinates(dialog, x_var, y_var)
                
                ttk.Button(coord_frame, text="座標選択", command=select_coordinates).pack(side=tk.RIGHT)
                
                # ボタン選択
                button_frame = ttk.Frame(settings_frame)
                button_frame.pack(fill=tk.X, padx=5, pady=2)
                
                ttk.Label(button_frame, text="ボタン:").pack(side=tk.LEFT)
                button_combo = ttk.Combobox(button_frame, textvariable=button_var, 
                                           values=['left', 'right', 'middle'], state='readonly', width=10)
                button_combo.pack(side=tk.LEFT, padx=5)
                
            elif action_t == 'key':
                # キーボード入力設定
                ttk.Label(settings_frame, text="キー入力:").pack(anchor=tk.W, padx=5)
                key_entry = ttk.Entry(settings_frame, textvariable=key_var, width=30)
                key_entry.pack(fill=tk.X, padx=5, pady=2)
                
                ttk.Label(settings_frame, text="テキスト入力:").pack(anchor=tk.W, padx=5, pady=(10,0))
                text_entry = ttk.Entry(settings_frame, textvariable=text_var, width=30)
                text_entry.pack(fill=tk.X, padx=5, pady=2)
                
                # ヘルプテキスト
                help_text = "例: 'ctrl+c', 'enter', 'space', 'f1' など\nテキスト入力欄にはそのまま入力したい文字を入力"
                ttk.Label(settings_frame, text=help_text, font=('TkDefaultFont', 8)).pack(anchor=tk.W, padx=5, pady=5)
                
            elif action_t == 'wait':
                # 待機設定
                wait_frame = ttk.Frame(settings_frame)
                wait_frame.pack(fill=tk.X, padx=5, pady=2)
                
                ttk.Label(wait_frame, text="待機時間(秒):").pack(side=tk.LEFT)
                ttk.Entry(wait_frame, textvariable=wait_var, width=10).pack(side=tk.LEFT, padx=5)
                
            elif action_t == 'compound':
                # 複合アクション設定
                ttk.Label(settings_frame, text="複合アクション（改行区切り）:").pack(anchor=tk.W, padx=5)
                
                compound_text = tk.Text(settings_frame, height=8, width=40)
                compound_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=2)
                
                if action_data and 'compound_actions' in action_data:
                    compound_text.insert('1.0', '\n'.join(action_data['compound_actions']))
                
                # ヘルプ
                help_text = "例:\nclick:100,200,left\nkey:ctrl+c\nwait:1.0\ntext:Hello World"
                ttk.Label(settings_frame, text=help_text, font=('TkDefaultFont', 8)).pack(anchor=tk.W, padx=5, pady=5)
        
        # タイプ変更時にフレームを更新
        action_type.trace('w', lambda *args: update_settings_frame())
        update_settings_frame()
        
        # ボタン
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(fill=tk.X, padx=10, pady=10)
        
        def save_action():
            action_t = action_type.get()
            
            if action_t == 'click':
                result.update({
                    'type': 'click',
                    'x': x_var.get(),
                    'y': y_var.get(),
                    'button': button_var.get(),
                    'description': f"座標 ({x_var.get()}, {y_var.get()}) を{button_var.get()}クリック"
                })
                
            elif action_t == 'key':
                key_text = key_var.get().strip()
                text_text = text_var.get().strip()
                
                if key_text:
                    result.update({
                        'type': 'key',
                        'key': key_text,
                        'description': f"キー入力: {key_text}"
                    })
                elif text_text:
                    result.update({
                        'type': 'text',
                        'text': text_text,
                        'description': f"テキスト入力: {text_text}"
                    })
                else:
                    messagebox.showwarning("警告", "キー入力またはテキスト入力を指定してください")
                    return
                    
            elif action_t == 'wait':
                result.update({
                    'type': 'wait',
                    'duration': wait_var.get(),
                    'description': f"{wait_var.get()}秒待機"
                })
                
            elif action_t == 'compound':
                compound_text_widget = None
                for widget in settings_frame.winfo_children():
                    if isinstance(widget, tk.Text):
                        compound_text_widget = widget
                        break
                
                if compound_text_widget:
                    compound_actions = compound_text_widget.get('1.0', tk.END).strip().split('\n')
                    compound_actions = [action.strip() for action in compound_actions if action.strip()]
                    
                    if compound_actions:
                        result.update({
                            'type': 'compound',
                            'compound_actions': compound_actions,
                            'description': f"複合アクション ({len(compound_actions)}個)"
                        })
                    else:
                        messagebox.showwarning("警告", "複合アクションを入力してください")
                        return
            
            dialog.result = result
            dialog.destroy()
        
        def cancel_action():
            dialog.result = None
            dialog.destroy()
        
        ttk.Button(btn_frame, text="OK", command=save_action).pack(side=tk.RIGHT, padx=5)
        ttk.Button(btn_frame, text="キャンセル", command=cancel_action).pack(side=tk.RIGHT)
        
        # ダイアログの結果を待つ
        dialog.result = None
        dialog.wait_window()
        
        return dialog.result
    
    def select_action_coordinates(self, parent_dialog, x_var, y_var):
        """アクション用の座標を選択"""
        parent_dialog.withdraw()
        
        def on_coordinate_selected(x, y):
            x_var.set(x)
            y_var.set(y)
            parent_dialog.deiconify()
        
        # 座標選択用の透明ウィンドウ
        coord_window = tk.Toplevel(self.root)
        coord_window.attributes('-fullscreen', True)
        coord_window.attributes('-alpha', 0.1)
        coord_window.configure(bg='red')
        coord_window.attributes('-topmost', True)
        
        # 情報ラベル
        info_label = tk.Label(coord_window, text="クリックする座標を選択してください（ESCでキャンセル）", 
                             font=('TkDefaultFont', 14), fg='white', bg='red')
        info_label.pack(pady=50)
        
        def on_click(event):
            on_coordinate_selected(event.x_root, event.y_root)
            coord_window.destroy()
        
        def on_cancel(event):
            coord_window.destroy()
            parent_dialog.deiconify()
        
        coord_window.bind('<Button-1>', on_click)
        coord_window.bind('<Escape>', on_cancel)
        coord_window.focus_set()
    
    # ===== ヘルパー関数 =====
    def reselect_region(self, parent_dialog, x_var, y_var, width_var, height_var):
        """領域を再選択"""
        parent_dialog.withdraw()
        self.is_selecting_region = True
        
        def on_region_selected():
            if hasattr(self, 'selected_region'):
                x_var.set(self.selected_region['x'])
                y_var.set(self.selected_region['y'])
                width_var.set(self.selected_region['width'])
                height_var.set(self.selected_region['height'])
                parent_dialog.deiconify()
        
        # 領域選択後のコールバック
        self.region_selection_callback = on_region_selected
        self.select_region()
    
    def preview_coordinates(self, x, y, width, height):
        """座標をプレビュー"""
        try:
            image = self.capture_region(x, y, width, height)
            text = self.extract_text_from_image(image)
            messagebox.showinfo("プレビュー", f"座標: ({x}, {y}, {width}, {height})\n検出されたテキスト: '{text}'")
        except Exception as e:
            messagebox.showerror("エラー", f"プレビューに失敗しました: {e}")
    
    def test_ocr_current(self, x, y, width, height):
        """現在の座標でOCRテスト"""
        try:
            image = self.capture_region(x, y, width, height)
            text = self.extract_text_from_image(image)
            self.log(f"OCRテスト結果: '{text}'")
            messagebox.showinfo("OCRテスト結果", f"検出されたテキスト:\n'{text}'")
        except Exception as e:
            messagebox.showerror("エラー", f"OCRテストに失敗しました: {e}")
    
    def show_region_preview(self, region):
        """領域プレビューを表示"""
        try:
            image = self.capture_region(region["x"], region["y"], region["width"], region["height"])
            
            # プレビューウィンドウを作成
            preview_window = tk.Toplevel(self.root)
            preview_window.title(f"領域プレビュー - {region['name']}")
            preview_window.geometry("400x300")
            
            # 画像を表示
            pil_image = Image.fromarray(image)
            pil_image = pil_image.resize((300, 200), Image.Resampling.NEAREST)
            photo = ImageTk.PhotoImage(pil_image)
            
            image_label = tk.Label(preview_window, image=photo)
            image_label.image = photo  # 参照を保持
            image_label.pack(pady=10)
            
            # OCRテスト
            text = self.extract_text_from_image(image)
            result_text = f"検出されたテキスト: '{text}'"
            ttk.Label(preview_window, text=result_text, wraplength=350).pack(pady=10)
            
        except Exception as e:
            messagebox.showerror("エラー", f"プレビューに失敗しました: {e}")
    
    # ===== メニュー機能 =====
    def import_config(self):
        """設定をインポート"""
        filename = filedialog.askopenfilename(
            title="設定ファイルを選択",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if filename:
            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                if 'region_sets' in data:
                    self.monitoring_regions = data['region_sets']
                    self.current_region_set = data.get('current_set', "デフォルト")
                    self.update_region_sets_list()
                    self.update_regions_list()
                    self.current_set_label.config(text=self.current_region_set)
                
                if 'config' in data:
                    self.config.update(data['config'])
                    self.interval_var.set(self.config.get("check_interval", 1.0))
                    self.language_var.set(self.config.get("ocr_language", "jpn+eng"))
                
                self.save_regions()
                self.save_config()
                
                self.log(f"設定をインポートしました: {filename}")
                messagebox.showinfo("成功", "設定をインポートしました")
            except Exception as e:
                messagebox.showerror("エラー", f"設定のインポートに失敗しました: {e}")
    
    def export_config(self):
        """設定をエクスポート"""
        filename = filedialog.asksaveasfilename(
            title="設定ファイルを保存",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if filename:
            try:
                data = {
                    'region_sets': self.monitoring_regions,
                    'current_set': self.current_region_set,
                    'config': self.config,
                    'exported_at': datetime.datetime.now().isoformat()
                }
                
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                
                self.log(f"設定をエクスポートしました: {filename}")
                messagebox.showinfo("成功", "設定をエクスポートしました")
            except Exception as e:
                messagebox.showerror("エラー", f"設定のエクスポートに失敗しました: {e}")
    
    def backup_regions(self):
        """領域データをバックアップ"""
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"regions_backup_{timestamp}.json"
        
        try:
            data = {
                'region_sets': self.monitoring_regions,
                'current_set': self.current_region_set,
                'backup_date': datetime.datetime.now().isoformat()
            }
            
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            self.log(f"領域データをバックアップしました: {filename}")
            messagebox.showinfo("成功", f"領域データをバックアップしました:\n{filename}")
        except Exception as e:
            messagebox.showerror("エラー", f"バックアップに失敗しました: {e}")
    
    def restore_regions(self):
        """領域データを復元"""
        filename = filedialog.askopenfilename(
            title="バックアップファイルを選択",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if filename:
            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                self.monitoring_regions = data.get('region_sets', {})
                self.current_region_set = data.get('current_set', "デフォルト")
                
                self.update_region_sets_list()
                self.update_regions_list()
                self.current_set_label.config(text=self.current_region_set)
                self.save_regions()
                
                self.log(f"領域データを復元しました: {filename}")
                messagebox.showinfo("成功", "領域データを復元しました")
            except Exception as e:
                messagebox.showerror("エラー", f"復元に失敗しました: {e}")
    
    def show_help(self):
        """ヘルプを表示"""
        help_text = """
🔍 Text Recognition Macro System - 使用方法

📋 基本的な使用手順:
1. 「新しい領域を追加」をクリック (F7)
2. 画面上で監視したい領域をドラッグ選択
3. 検索文字とアクション（クリック等）を設定
4. 「監視開始」で自動実行開始 (F6)

🛠️ 高度な機能:
• 監視領域セット: 複数の設定パターンを保存可能
• 複数アクション: 1つの領域に複数の動作を設定
• 座標選択: クリック位置も画面上で直感的に選択
• リアルタイムプレビュー: OCR結果を事前確認

⚡ ショートカットキー:
F6: 監視開始/停止
F7: 新しい領域追加
F8: 緊急停止
Ctrl+Shift+C: 座標選択（座標設定中）

💾 データ管理:
• 設定は自動保存されます
• バックアップ・復元機能あり
• 設定のインポート・エクスポート可能

❓ トラブルシューティング:
• OCRが認識しない → 文字のサイズ・コントラストを確認
• アクションが実行されない → 座標を再確認
• 緊急停止 → F8キーまたはマウスを左上角に移動
        """
        
        help_window = tk.Toplevel(self.root)
        help_window.title("使用方法")
        help_window.geometry("600x500")
        
        text_widget = tk.Text(help_window, wrap=tk.WORD, padx=20, pady=20)
        text_widget.pack(fill=tk.BOTH, expand=True)
        text_widget.insert('1.0', help_text)
        text_widget.config(state=tk.DISABLED)
        
        scrollbar = ttk.Scrollbar(help_window, orient=tk.VERTICAL, command=text_widget.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        text_widget.configure(yscrollcommand=scrollbar.set)
    
    def show_about(self):
        """バージョン情報を表示"""
        about_text = """
Text Recognition Macro System
Version 2.0 - 改良版

AutoClickerの設計を参考にした
高機能文字認識マクロシステム

Features:
• OCR文字認識 (Tesseract/EasyOCR)
• 複数監視領域対応
• 設定セット管理
• 直感的なGUI操作
• 自動保存機能

Developed with Python + Tkinter
        """
        
        messagebox.showinfo("バージョン情報", about_text)
    
    def install_ocr_engine(self):
        """OCRエンジンのセットアップを実行"""
        try:
            import subprocess
            import os
            
            # setup_ocr.pyのパスを取得
            setup_path = os.path.join(os.path.dirname(__file__), "setup_ocr.py")
            
            if os.path.exists(setup_path):
                result = messagebox.askyesno(
                    "OCRセットアップ", 
                    "OCRエンジンのセットアップを実行しますか？\n\n"
                    "このプロセスには時間がかかる場合があります。\n"
                    "セットアップ中はアプリケーションが一時的に応答しなくなります。"
                )
                
                if result:
                    self.log("OCRセットアップを開始しています...")
                    
                    # 新しいコマンドプロンプトでsetup_ocr.pyを実行
                    subprocess.Popen([
                        'cmd', '/c', 'start', 'cmd', '/k', 
                        f'python "{setup_path}" && echo セットアップが完了しました。Enterキーを押して閉じてください。 && pause'
                    ])
                    
                    messagebox.showinfo(
                        "OCRセットアップ", 
                        "OCRセットアップが新しいウィンドウで開始されました。\n"
                        "完了後、アプリケーションを再起動してください。"
                    )
            else:
                messagebox.showerror(
                    "エラー", 
                    f"setup_ocr.pyが見つかりません。\nパス: {setup_path}"
                )
                
        except Exception as e:
            messagebox.showerror("エラー", f"OCRセットアップの実行に失敗しました: {e}")
            self.log(f"OCRセットアップエラー: {e}")
    
    def cancel_region_selection(self):
        """領域選択をキャンセル"""
        if self.selection_window:
            self.selection_window.destroy()
            self.selection_window = None
        self.root.deiconify()
        self.is_selecting_region = False
        self.log("領域選択をキャンセルしました")
    
    def on_closing(self):
        """アプリケーション終了時の処理"""
        if self.running:
            self.stop_monitoring()
        
        # ショートカットキーを削除
        try:
            import keyboard
            keyboard.unhook_all()
        except:
            pass
        
        # 設定を保存
        self.save_config()
        self.save_regions()
        
        self.root.destroy()
    
    def run(self):
        """GUIを開始"""
        # ウィンドウサイズを復元
        geometry = self.config.get("window_geometry", "1200x800")
        self.root.geometry(geometry)
        
        self.root.mainloop()


if __name__ == "__main__":
    app = TextMacroGUI()
    app.run()
        """画面上で領域を選択"""
        self.log("領域選択モードを開始します...")
        self.root.withdraw()  # メインウィンドウを隠す
        
        # 全画面キャプチャ
        screenshot = ImageGrab.grab()
        
        # 選択ウィンドウを作成
        self.selection_window = tk.Toplevel()
        self.selection_window.title("領域を選択してください")
        self.selection_window.attributes('-fullscreen', True)
        self.selection_window.attributes('-alpha', 0.3)
        self.selection_window.configure(bg='red')
        
        # キャンバスを作成
        canvas = tk.Canvas(self.selection_window, highlightthickness=0)
        canvas.pack(fill=tk.BOTH, expand=True)
        
        # スクリーンショットを背景に設定
        screen_width = self.selection_window.winfo_screenwidth()
        screen_height = self.selection_window.winfo_screenheight()
        
        # PILイメージをtkinterで使用可能な形式に変換
        screenshot_resized = screenshot.resize((screen_width, screen_height), Image.Resampling.LANCZOS)
        self.screenshot_photo = ImageTk.PhotoImage(screenshot_resized)
        canvas.create_image(0, 0, anchor=tk.NW, image=self.screenshot_photo)
        
        # 選択用の矩形を描画するための変数
        self.selection_rect = None
        self.start_x = None
        self.start_y = None
        
        # マウスイベントをバインド
        canvas.bind("<Button-1>", self.on_selection_start)
        canvas.bind("<B1-Motion>", self.on_selection_drag)
        canvas.bind("<ButtonRelease-1>", self.on_selection_end)
        
        # ESCキーで選択をキャンセル
        self.selection_window.bind("<Escape>", self.cancel_selection)
        self.selection_window.focus_set()
        
        # 説明ラベル
        info_label = tk.Label(self.selection_window, 
                            text="ドラッグして領域を選択してください (ESCキー: キャンセル)",
                            bg="yellow", fg="black", font=("Arial", 14))
        info_label.place(x=10, y=10)
    
    def on_selection_start(self, event):
        """選択開始"""
        self.start_x = event.x
        self.start_y = event.y
        
        if self.selection_rect:
            self.selection_window.children['!canvas'].delete(self.selection_rect)
        
        self.selection_rect = self.selection_window.children['!canvas'].create_rectangle(
            self.start_x, self.start_y, self.start_x, self.start_y,
            outline="red", width=2, fill=""
        )
    
    def on_selection_drag(self, event):
        """選択中のドラッグ"""
        if self.selection_rect and self.start_x is not None and self.start_y is not None:
            self.selection_window.children['!canvas'].coords(
                self.selection_rect,
                self.start_x, self.start_y, event.x, event.y
            )
    
    def on_selection_end(self, event):
        """選択終了"""
        if self.start_x is not None and self.start_y is not None:
            self.end_x = event.x
            self.end_y = event.y
            
            # 座標を正規化（左上が小さい値になるように）
            x1 = min(self.start_x, self.end_x)
            y1 = min(self.start_y, self.end_y)
            x2 = max(self.start_x, self.end_x)
            y2 = max(self.start_y, self.end_y)
            
            width = x2 - x1
            height = y2 - y1
            
            if width > 10 and height > 10:  # 最小サイズチェック
                self.selected_region = {
                    "x": x1,
                    "y": y1,
                    "width": width,
                    "height": height
                }
                
                self.close_selection_window()
                self.show_region_config_dialog()
            else:
                messagebox.showwarning("警告", "選択した領域が小さすぎます")
                self.cancel_selection()
    
    def cancel_selection(self, event=None):
        """選択をキャンセル"""
        self.close_selection_window()
        self.log("領域選択をキャンセルしました")
    
    def close_selection_window(self):
        """選択ウィンドウを閉じる"""
        if self.selection_window:
            self.selection_window.destroy()
            self.selection_window = None
        self.root.deiconify()  # メインウィンドウを表示
    
    def show_region_config_dialog(self, edit_index=None):
        """監視領域設定ダイアログを表示"""
        dialog = tk.Toplevel(self.root)
        dialog.title("監視領域設定")
        dialog.geometry("500x600")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # 編集モードまたは新規作成
        if edit_index is not None:
            region_data = self.config["monitoring_regions"][edit_index]
        elif hasattr(self, 'selected_region'):
            region_data = {
                "name": "",
                "x": self.selected_region["x"],
                "y": self.selected_region["y"],
                "width": self.selected_region["width"],
                "height": self.selected_region["height"],
                "target_text": "",
                "actions": [{"type": "click", "x": 100, "y": 100}]
            }
        else:
            region_data = {
                "name": "",
                "x": 0, "y": 0, "width": 100, "height": 100,
                "target_text": "",
                "actions": [{"type": "click", "x": 100, "y": 100}]
            }
        
        # フォーム要素
        row = 0
        
        ttk.Label(dialog, text="名前:").grid(row=row, column=0, sticky=tk.W, padx=5, pady=5)
        name_var = tk.StringVar(value=region_data["name"])
        ttk.Entry(dialog, textvariable=name_var, width=40).grid(row=row, column=1, padx=5, pady=5)
        row += 1
        
        ttk.Label(dialog, text="X座標:").grid(row=row, column=0, sticky=tk.W, padx=5, pady=5)
        x_var = tk.IntVar(value=region_data["x"])
        ttk.Entry(dialog, textvariable=x_var, width=40).grid(row=row, column=1, padx=5, pady=5)
        row += 1
        
        ttk.Label(dialog, text="Y座標:").grid(row=row, column=0, sticky=tk.W, padx=5, pady=5)
        y_var = tk.IntVar(value=region_data["y"])
        ttk.Entry(dialog, textvariable=y_var, width=40).grid(row=row, column=1, padx=5, pady=5)
        row += 1
        
        ttk.Label(dialog, text="幅:").grid(row=row, column=0, sticky=tk.W, padx=5, pady=5)
        width_var = tk.IntVar(value=region_data["width"])
        ttk.Entry(dialog, textvariable=width_var, width=40).grid(row=row, column=1, padx=5, pady=5)
        row += 1
        
        ttk.Label(dialog, text="高さ:").grid(row=row, column=0, sticky=tk.W, padx=5, pady=5)
        height_var = tk.IntVar(value=region_data["height"])
        ttk.Entry(dialog, textvariable=height_var, width=40).grid(row=row, column=1, padx=5, pady=5)
        row += 1
        
        ttk.Label(dialog, text="検索文字:").grid(row=row, column=0, sticky=tk.W, padx=5, pady=5)
        text_var = tk.StringVar(value=region_data["target_text"])
        ttk.Entry(dialog, textvariable=text_var, width=40).grid(row=row, column=1, padx=5, pady=5)
        row += 1
        
        # アクション設定
        ttk.Label(dialog, text="アクション設定:").grid(row=row, column=0, sticky=tk.NW, padx=5, pady=5)
        row += 1
        
        # アクションフレーム
        action_frame = ttk.LabelFrame(dialog, text="アクション", padding="5")
        action_frame.grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5, pady=5)
        
        # アクションタイプ選択
        ttk.Label(action_frame, text="アクション種類:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        action_type_var = tk.StringVar(value="click")
        action_type_combo = ttk.Combobox(action_frame, textvariable=action_type_var, 
                                       values=["click", "key", "hotkey", "type", "move", "wait"], width=15)
        action_type_combo.grid(row=0, column=1, padx=5, pady=5)
        
        # アクション詳細設定用のフレーム
        detail_frame = ttk.Frame(action_frame)
        detail_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), padx=5, pady=5)
        
        # アクション詳細の変数
        action_x_var = tk.IntVar(value=100)
        action_y_var = tk.IntVar(value=100)
        action_key_var = tk.StringVar(value="space")
        action_text_var = tk.StringVar(value="Hello")
        action_wait_var = tk.DoubleVar(value=1.0)
        
        def update_action_details(*args):
            # 詳細フレームをクリア
            for widget in detail_frame.winfo_children():
                widget.destroy()
            
            action_type = action_type_var.get()
            
            if action_type == "click":
                ttk.Label(detail_frame, text="X座標:").grid(row=0, column=0, sticky=tk.W, padx=5)
                ttk.Entry(detail_frame, textvariable=action_x_var, width=10).grid(row=0, column=1, padx=5)
                ttk.Label(detail_frame, text="Y座標:").grid(row=0, column=2, sticky=tk.W, padx=5)
                ttk.Entry(detail_frame, textvariable=action_y_var, width=10).grid(row=0, column=3, padx=5)
                
            elif action_type == "key":
                ttk.Label(detail_frame, text="キー:").grid(row=0, column=0, sticky=tk.W, padx=5)
                ttk.Entry(detail_frame, textvariable=action_key_var, width=20).grid(row=0, column=1, padx=5)
                
            elif action_type == "type":
                ttk.Label(detail_frame, text="テキスト:").grid(row=0, column=0, sticky=tk.W, padx=5)
                ttk.Entry(detail_frame, textvariable=action_text_var, width=30).grid(row=0, column=1, padx=5)
                
            elif action_type == "wait":
                ttk.Label(detail_frame, text="秒数:").grid(row=0, column=0, sticky=tk.W, padx=5)
                ttk.Entry(detail_frame, textvariable=action_wait_var, width=10).grid(row=0, column=1, padx=5)
        
        action_type_var.trace('w', update_action_details)
        update_action_details()  # 初期表示
        
        row += 2
        
        # ボタン
        button_frame = ttk.Frame(dialog)
        button_frame.grid(row=row, column=0, columnspan=2, pady=20)
        
        def save_region():
            try:
                # アクションを構築
                action_type = action_type_var.get()
                action = {"type": action_type}
                
                if action_type == "click":
                    action.update({"x": action_x_var.get(), "y": action_y_var.get()})
                elif action_type == "key":
                    action.update({"key": action_key_var.get()})
                elif action_type == "type":
                    action.update({"text": action_text_var.get()})
                elif action_type == "wait":
                    action.update({"duration": action_wait_var.get()})
                
                new_region = {
                    "name": name_var.get(),
                    "x": x_var.get(),
                    "y": y_var.get(),
                    "width": width_var.get(),
                    "height": height_var.get(),
                    "target_text": text_var.get(),
                    "actions": [action]
                }
                
                if edit_index is not None:
                    self.config["monitoring_regions"][edit_index] = new_region
                    self.log(f"監視領域 '{new_region['name']}' を更新しました")
                else:
                    self.config["monitoring_regions"].append(new_region)
                    self.log(f"監視領域 '{new_region['name']}' を追加しました")
                
                self.refresh_regions_list()
                dialog.destroy()
                
                # 選択された領域情報をクリア
                if hasattr(self, 'selected_region'):
                    delattr(self, 'selected_region')
                
            except Exception as e:
                messagebox.showerror("エラー", f"設定の保存に失敗しました: {e}")
        
        ttk.Button(button_frame, text="保存", command=save_region).grid(row=0, column=0, padx=5)
        ttk.Button(button_frame, text="キャンセル", command=dialog.destroy).grid(row=0, column=1, padx=5)
        
        # プレビューボタン
        def preview_region():
            try:
                x, y, w, h = x_var.get(), y_var.get(), width_var.get(), height_var.get()
                image = self.capture_region(x, y, w, h)
                text = self.extract_text_from_image(image)
                messagebox.showinfo("プレビュー", f"検出されたテキスト:\n'{text}'")
            except Exception as e:
                messagebox.showerror("エラー", f"プレビューに失敗しました: {e}")
        
        ttk.Button(button_frame, text="プレビュー", command=preview_region).grid(row=0, column=2, padx=5)
    
    def add_region(self):
        """新しい監視領域を追加"""
        self.show_region_config_dialog()
    
    def edit_region(self):
        """選択された監視領域を編集"""
        selected = self.regions_tree.selection()
        if not selected:
            messagebox.showwarning("警告", "編集する領域を選択してください")
            return
        
        # 選択されたアイテムのインデックスを取得
        index = self.regions_tree.index(selected[0])
        self.show_region_config_dialog(index)
    
    def delete_region(self):
        """選択された監視領域を削除"""
        selected = self.regions_tree.selection()
        if not selected:
            messagebox.showwarning("警告", "削除する領域を選択してください")
            return
        
        if messagebox.askyesno("確認", "選択された領域を削除しますか？"):
            index = self.regions_tree.index(selected[0])
            region_name = self.config["monitoring_regions"][index]["name"]
            del self.config["monitoring_regions"][index]
            self.refresh_regions_list()
            self.log(f"監視領域 '{region_name}' を削除しました")
    
    def test_region(self):
        """選択された監視領域をテスト"""
        selected = self.regions_tree.selection()
        if not selected:
            messagebox.showwarning("警告", "テストする領域を選択してください")
            return
        
        index = self.regions_tree.index(selected[0])
        region = self.config["monitoring_regions"][index]
        
        try:
            # 領域をキャプチャ
            image = self.capture_region(region["x"], region["y"], region["width"], region["height"])
            text = self.extract_text_from_image(image)
            
            result = f"領域: {region['name']}\n"
            result += f"座標: ({region['x']}, {region['y']}, {region['width']}, {region['height']})\n"
            result += f"検索文字: '{region['target_text']}'\n"
            result += f"検出された文字: '{text}'\n"
            result += f"一致: {'はい' if self.check_text_match(text, region['target_text']) else 'いいえ'}"
            
            messagebox.showinfo("テスト結果", result)
            self.log(f"テスト実行: {region['name']} - 検出文字: '{text}'")
            
        except Exception as e:
            messagebox.showerror("エラー", f"テストに失敗しました: {e}")
    
    def capture_region(self, x, y, width, height):
        """指定領域をキャプチャ"""
        screenshot = ImageGrab.grab(bbox=(x, y, x + width, y + height))
        return np.array(screenshot)
    
    def extract_text_from_image(self, image, language="jpn+eng"):
        """画像から文字を抽出"""
        if self.ocr_engine is None:
            self.log("OCRエンジンが利用できません")
            return ""
        
        try:
            if self.ocr_engine == 'tesseract':
                text = pytesseract.image_to_string(
                    Image.fromarray(image), 
                    lang=language,
                    config='--psm 6'
                ).strip()
                return text
            
            elif self.ocr_engine == 'easyocr':
                # EasyOCRを使用
                results = self.easyocr_reader.readtext(image)
                text = ' '.join([result[1] for result in results])
                return text.strip()
            
            else:
                # 簡易的な色ベースのテキスト検出（OCRなし）
                return self.simple_text_detection(image)
                
        except Exception as e:
            self.log(f"OCRエラー: {e}")
            # OCRが失敗した場合の代替手段を提供
            return self.fallback_text_detection(image)
    
    def simple_text_detection(self, image):
        """簡易的なテキスト検出（OCRエンジンがない場合の代替）"""
        try:
            # 画像の特徴を基にした簡易判定
            # これは完全な文字認識ではなく、パターンマッチングに近い
            gray = np.mean(image, axis=2)
            text_regions = np.where(gray < 128)  # 暗い部分を文字とみなす
            
            if len(text_regions[0]) > 10:  # 十分な暗い領域がある場合
                return "text_detected"  # 簡易的な検出結果
            else:
                return ""
        except:
            return ""
    
    def fallback_text_detection(self, image):
        """OCR失敗時のフォールバック処理"""
        try:
            # 色の分析による簡易判定
            if np.std(image) > 30:  # 画像に十分なコントラストがある
                return "content_detected"
            return ""
        except:
            return ""
    
    def install_ocr_engine(self):
        """OCRエンジンのインストールを試行"""
        install_dialog = tk.Toplevel(self.root)
        install_dialog.title("OCRエンジンのセットアップ")
        install_dialog.geometry("500x400")
        install_dialog.transient(self.root)
        install_dialog.grab_set()
        
        instruction_text = """
OCRエンジン（文字認識）のセットアップ

現在利用可能なオプション:

1. Tesseract OCR (推奨)
   - 高精度な文字認識
   - 日本語・英語対応
   
2. EasyOCR (代替)
   - インストールが簡単
   - 多言語対応

3. 簡易モード
   - OCRエンジンなしで基本的な検出のみ
   - 限定的な機能

選択してください:
"""
        
        ttk.Label(install_dialog, text=instruction_text, justify=tk.LEFT).pack(padx=20, pady=20)
        
        button_frame = ttk.Frame(install_dialog)
        button_frame.pack(pady=20)
        
        def install_tesseract():
            self.log("Tesseractのインストール方法を表示します...")
            messagebox.showinfo("Tesseract インストール", 
                "1. https://github.com/UB-Mannheim/tesseract/wiki からTesseractをダウンロード\n"
                "2. インストール後、アプリケーションを再起動してください\n"
                "3. 日本語認識には追加の言語パックが必要です")
            install_dialog.destroy()
        
        def install_easyocr():
            try:
                self.log("EasyOCRをインストール中...")
                subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'easyocr'])
                self.log("EasyOCRのインストールが完了しました。アプリケーションを再起動してください。")
                messagebox.showinfo("完了", "EasyOCRのインストールが完了しました。\nアプリケーションを再起動してください。")
            except Exception as e:
                self.log(f"EasyOCRのインストールに失敗: {e}")
                messagebox.showerror("エラー", f"インストールに失敗しました: {e}")
            install_dialog.destroy()
        
        def use_simple_mode():
            self.ocr_engine = 'simple'
            self.log("簡易モードで動作します（文字認識機能は限定的です）")
            messagebox.showinfo("簡易モード", "簡易モードで動作します。\n文字認識機能は限定的になります。")
            install_dialog.destroy()
        
        ttk.Button(button_frame, text="Tesseractをインストール", command=install_tesseract).pack(pady=5)
        ttk.Button(button_frame, text="EasyOCRをインストール", command=install_easyocr).pack(pady=5)
        ttk.Button(button_frame, text="簡易モードで続行", command=use_simple_mode).pack(pady=5)
        ttk.Button(button_frame, text="キャンセル", command=install_dialog.destroy).pack(pady=5)
    
    def check_text_match(self, detected_text, target_text):
        """文字の一致をチェック"""
        return target_text.lower() in detected_text.lower()
    
    def execute_action(self, action):
        """アクションを実行"""
        action_type = action.get("type")
        
        try:
            if action_type == "click":
                x, y = action.get("x", 0), action.get("y", 0)
                pyautogui.click(x, y)
                self.log(f"クリック実行: ({x}, {y})")
                
            elif action_type == "key":
                key = action.get("key")
                pyautogui.press(key)
                self.log(f"キー入力: {key}")
                
            elif action_type == "type":
                text = action.get("text", "")
                pyautogui.write(text, interval=0.05)
                self.log(f"テキスト入力: {text}")
                
            elif action_type == "wait":
                duration = action.get("duration", 1)
                time.sleep(duration)
                self.log(f"待機: {duration}秒")
                
        except Exception as e:
            self.log(f"アクション実行エラー: {e}")
    
    def monitor_text(self):
        """文字監視のメインループ"""
        self.log("文字監視を開始しました")
        
        while self.running:
            try:
                for region in self.config["monitoring_regions"]:
                    if not self.running:
                        break
                        
                    name = region["name"]
                    x, y = region["x"], region["y"]
                    width, height = region["width"], region["height"]
                    target_text = region["target_text"]
                    actions = region["actions"]
                    
                    # 領域をキャプチャ
                    image = self.capture_region(x, y, width, height)
                    
                    # 文字を抽出
                    detected_text = self.extract_text_from_image(
                        image, 
                        self.config.get("ocr_language", "jpn+eng")
                    )
                    
                    # 文字が一致したかチェック
                    if detected_text and self.check_text_match(detected_text, target_text):
                        self.log(f"[{name}] 文字が一致: '{detected_text}' → マクロ実行")
                        
                        # アクションを実行
                        for action in actions:
                            if not self.running:
                                break
                            self.execute_action(action)
                            time.sleep(0.1)
                
                # 次のチェックまで待機
                time.sleep(self.config.get("check_interval", 1.0))
                
            except Exception as e:
                self.log(f"監視エラー: {e}")
                time.sleep(1)
        
        self.log("文字監視を停止しました")
    
    def start_monitoring(self):
        """監視を開始"""
        if not self.running and self.config["monitoring_regions"]:
            self.running = True
            self.monitoring_thread = threading.Thread(target=self.monitor_text)
            self.monitoring_thread.daemon = True
            self.monitoring_thread.start()
            
            self.start_button.config(state=tk.DISABLED)
            self.stop_button.config(state=tk.NORMAL)
            self.status_var.set("監視中")
            self.log("監視を開始しました")
        elif not self.config["monitoring_regions"]:
            messagebox.showwarning("警告", "監視する領域が設定されていません")
        else:
            messagebox.showinfo("情報", "すでに監視中です")
    
    def stop_monitoring(self):
        """監視を停止"""
        if self.running:
            self.running = False
            if self.monitoring_thread:
                self.monitoring_thread.join(timeout=2)
            
            self.start_button.config(state=tk.NORMAL)
            self.stop_button.config(state=tk.DISABLED)
            self.status_var.set("停止")
            self.log("監視を停止しました")
        else:
            messagebox.showinfo("情報", "監視は実行されていません")
    
    def save_settings(self):
        """設定を保存"""
        self.config["check_interval"] = self.interval_var.get()
        self.config["ocr_language"] = self.language_var.get()
        self.save_config()
        self.log("設定を保存しました")
        messagebox.showinfo("保存完了", "設定を保存しました")
    
    def load_config_file(self):
        """設定ファイルを開く"""
        filename = filedialog.askopenfilename(
            title="設定ファイルを選択",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if filename:
            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    self.config = json.load(f)
                self.config_file = filename
                self.interval_var.set(self.config.get("check_interval", 1.0))
                self.language_var.set(self.config.get("ocr_language", "jpn+eng"))
                self.refresh_regions_list()
                self.log(f"設定ファイルを読み込みました: {filename}")
            except Exception as e:
                messagebox.showerror("エラー", f"設定ファイルの読み込みに失敗しました: {e}")
    
    def save_config_file(self):
        """設定ファイルを名前を付けて保存"""
        filename = filedialog.asksaveasfilename(
            title="設定ファイルを保存",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if filename:
            try:
                self.config_file = filename
                self.save_config()
                self.log(f"設定ファイルを保存しました: {filename}")
            except Exception as e:
                messagebox.showerror("エラー", f"設定ファイルの保存に失敗しました: {e}")
    
    def on_closing(self):
        """ウィンドウを閉じる際の処理"""
        if self.running:
            self.stop_monitoring()
        self.root.destroy()
    
    def run(self):
        """GUIを開始"""
        self.root.mainloop()


if __name__ == "__main__":
    app = TextMacroGUI()
    app.run()