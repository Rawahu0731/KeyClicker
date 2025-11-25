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
        
        # EasyOCRを遅延インポートして試行（トップレベルでのimportは避ける）
        try:
            import easyocr
            try:
                self.easyocr_reader = easyocr.Reader(['ja', 'en'])
                self.ocr_engine = 'easyocr'
                print("EasyOCR を使用します")
                return
            except Exception as e:
                print(f"EasyOCR設定エラー: {e}")
        except ImportError:
            # easyocr がインストールされていない
            pass
        
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
                  command=self.save_current_region_set).pack(side=tk.LEFT, padx=(0, 10))
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
                  command=self.add_region).pack(side=tk.LEFT, padx=(0, 10))
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
                                      command=self.start_monitoring)
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
    
    # ===== 監視領域管理（残りのメソッドを追加する必要があります） =====
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
                # 主領域をキャプチャ
                image = self.capture_region(region["x"], region["y"], region["width"], region["height"])
                text = self.extract_text_from_image(image)

                result = f"領域: {region['name']}\n"
                result += f"座標: ({region['x']}, {region['y']}, {region['width']}, {region['height']})\n"
                result += f"検索文字: '{region.get('target_text', '')}'\n"
                result += f"検出された文字: '{text}'\n"

                # 比較領域が設定されている場合は追加で比較
                if region.get('compare_enabled') and region.get('compare_region'):
                    cr = region['compare_region']
                    cmp_img = self.capture_region(cr['x'], cr['y'], cr['width'], cr['height'])
                    cmp_text = self.extract_text_from_image(cmp_img)
                    match = self.compare_texts(text, cmp_text)
                    result += f"比較領域の検出文字: '{cmp_text}'\n"
                    result += f"主領域と比較領域の一致: {'はい' if match else 'いいえ'}\n"
                    result += f"比較のみでトリガー: {'はい' if region.get('compare_trigger_only') else 'いいえ'}"
                else:
                    result += f"一致: {'はい' if self.check_text_match(text, region.get('target_text', '')) else 'いいえ'}"

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
                    
                    # 比較領域が設定されている場合は、両方をOCRして一致判定
                    compare_cfg = region.get('compare_region')
                    compare_enabled = region.get('compare_enabled', False)
                    compare_trigger_only = region.get('compare_trigger_only', False)

                    should_trigger = False
                    if compare_enabled and compare_cfg:
                        try:
                            cmp_img = self.capture_region(compare_cfg['x'], compare_cfg['y'], compare_cfg['width'], compare_cfg['height'])
                            cmp_text = self.extract_text_from_image(cmp_img, self.config.get("ocr_language", "jpn+eng"))

                            # 比較のみでトリガーするオプションがある場合は一致のみで判定
                            if detected_text and self.compare_texts(detected_text, cmp_text):
                                should_trigger = True
                                self.root.after(0, lambda: self.log(f"[{name}] 比較領域と一致: '{detected_text}' == '{cmp_text}' -> アクション実行"))
                            elif not compare_trigger_only:
                                # 比較は有効だがターゲット文字列も指定されている場合はそれでも判定する
                                if detected_text and self.check_text_match(detected_text, target_text):
                                    should_trigger = True
                                    self.root.after(0, lambda: self.log(f"[{name}] 文字が一致: '{detected_text}' → アクション実行"))
                        except Exception as e:
                            self.root.after(0, lambda: self.log(f"[{name}] 比較領域OCRエラー: {e}"))
                    else:
                        # 通常のターゲット文字列照合
                        if detected_text and self.check_text_match(detected_text, target_text):
                            should_trigger = True
                            self.root.after(0, lambda: self.log(f"[{name}] 文字が一致: '{detected_text}' → アクション実行"))

                    if should_trigger:
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
    
    # ===== 基本機能（実装が必要な関数群） =====
    def capture_region(self, x, y, width, height):
        """画面の指定領域をキャプチャ"""
        try:
            image = ImageGrab.grab(bbox=(x, y, x + width, y + height))
            return np.array(image)
        except Exception as e:
            raise Exception(f"画面キャプチャエラー: {e}")
    
    def extract_text_from_image(self, image, language="jpn+eng"):
        """画像から文字を抽出"""
        if self.ocr_engine == 'tesseract':
            try:
                pil_image = Image.fromarray(image)
                text = pytesseract.image_to_string(pil_image, lang=language, config='--psm 6')
                return text.strip()
            except Exception as e:
                return f"OCRエラー: {e}"
        
        elif self.ocr_engine == 'easyocr':
            try:
                result = self.easyocr_reader.readtext(image)
                text = ' '.join([item[1] for item in result])
                return text.strip()
            except Exception as e:
                return f"OCRエラー: {e}"
        
        else:
            return "OCRエンジンが設定されていません"
    
    def check_text_match(self, detected_text, target_text):
        """文字の一致をチェック"""
        if not detected_text or not target_text:
            return False
        
        # 大文字小文字を無視して部分一致
        return target_text.lower() in detected_text.lower()

    def compare_texts(self, text_a, text_b):
        """2つの文字列を正規化して厳密（大文字小文字無視）一致を判定する

        空白や改行を除去して比較する簡易実装。
        """
        try:
            if not text_a or not text_b:
                return False
            a = ' '.join(str(text_a).split()).strip().lower()
            b = ' '.join(str(text_b).split()).strip().lower()
            return a == b
        except Exception:
            return False
    
    def execute_action(self, action):
        """アクションを実行"""
        try:
            action_type = action.get("type", "")
            
            if action_type == "click":
                x = action.get("x", 0)
                y = action.get("y", 0)
                pyautogui.click(x, y)
                self.log(f"クリック実行: ({x}, {y})")
                
            elif action_type == "key":
                key = action.get("key", "")
                pyautogui.press(key)
                self.log(f"キー入力実行: {key}")
                
            elif action_type == "hotkey":
                keys = action.get("keys", [])
                pyautogui.hotkey(*keys)
                self.log(f"ホットキー実行: {'+'.join(keys)}")
                
            elif action_type == "type":
                text = action.get("text", "")
                pyautogui.typewrite(text)
                self.log(f"テキスト入力実行: {text}")
                
            elif action_type == "move":
                x = action.get("x", 0)
                y = action.get("y", 0)
                pyautogui.moveTo(x, y)
                self.log(f"マウス移動実行: ({x}, {y})")
                
            elif action_type == "wait":
                duration = action.get("duration", 1.0)
                time.sleep(duration)
                self.log(f"待機実行: {duration}秒")
                
        except Exception as e:
            self.log(f"アクション実行エラー: {e}")
    
    # ===== 残りの未実装メソッド =====
    def show_region_config_dialog(self, region_data=None, region_index=None):
        """監視領域設定ダイアログを表示"""
        dialog = tk.Toplevel(self.root)
        dialog.title("監視領域設定")
        dialog.geometry("600x500")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # デフォルトデータ
        if region_data is None:
            region_data = {
                "name": "新しい領域",
                "x": 100, "y": 100, "width": 200, "height": 100,
                "target_text": "",
                # 比較用領域: {'x':..., 'y':..., 'width':..., 'height':...} または None
                "compare_region": None,
                "compare_enabled": False,
                "compare_trigger_only": False,
                "enabled": True,
                "actions": []
            }
        
        # タイトル
        title_text = "監視領域を編集" if region_index is not None else "新しい監視領域を追加"
        ttk.Label(dialog, text=title_text, font=("Arial", 14, "bold")).pack(pady=(10, 20))
        
        # 基本設定
        basic_frame = ttk.LabelFrame(dialog, text="基本設定", padding="15")
        basic_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # 名前
        name_frame = ttk.Frame(basic_frame)
        name_frame.pack(fill=tk.X, pady=2)
        ttk.Label(name_frame, text="名前:").pack(side=tk.LEFT, padx=(0, 10))
        name_var = tk.StringVar(value=region_data["name"])
        ttk.Entry(name_frame, textvariable=name_var, width=30).pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # 有効/無効
        enabled_var = tk.BooleanVar(value=region_data.get("enabled", True))
        ttk.Checkbutton(basic_frame, text="この領域を有効にする", variable=enabled_var).pack(anchor=tk.W, pady=5)
        
        # 座標設定
        coord_frame = ttk.LabelFrame(dialog, text="監視領域座標", padding="15")
        coord_frame.pack(fill=tk.X, padx=10, pady=5)
        
        coord_vars = {}
        coord_labels = [("X座標", "x"), ("Y座標", "y"), ("幅", "width"), ("高さ", "height")]
        
        for i, (label, key) in enumerate(coord_labels):
            row_frame = ttk.Frame(coord_frame)
            row_frame.pack(fill=tk.X, pady=2)
            ttk.Label(row_frame, text=f"{label}:").pack(side=tk.LEFT, padx=(0, 10))
            coord_vars[key] = tk.IntVar(value=region_data[key])
            ttk.Entry(row_frame, textvariable=coord_vars[key], width=15).pack(side=tk.LEFT)
        
        # 領域再選択ボタン
        def reselect_region():
            """領域を再選択"""
            dialog.withdraw()
            self.is_selecting_region = True
            
            def on_region_selected():
                if hasattr(self, 'selected_region'):
                    coord_vars["x"].set(self.selected_region['x'])
                    coord_vars["y"].set(self.selected_region['y'])
                    coord_vars["width"].set(self.selected_region['width'])
                    coord_vars["height"].set(self.selected_region['height'])
                    dialog.deiconify()
            
            # 領域選択後のコールバック
            self.region_selection_callback = on_region_selected
            self.select_region()
        
        coord_buttons_frame = ttk.Frame(coord_frame)
        coord_buttons_frame.pack(fill=tk.X, pady=(10, 0))
        
        ttk.Button(coord_buttons_frame, text="領域を再選択", command=reselect_region).pack(side=tk.LEFT, padx=(0, 10))
        
        def preview_coordinates():
            """座標をプレビュー"""
            try:
                x, y = coord_vars["x"].get(), coord_vars["y"].get()
                w, h = coord_vars["width"].get(), coord_vars["height"].get()
                image = self.capture_region(x, y, w, h)
                text = self.extract_text_from_image(image)
                messagebox.showinfo("プレビュー", f"座標: ({x}, {y}, {w}, {h})\n検出されたテキスト: '{text}'")
            except Exception as e:
                messagebox.showerror("エラー", f"プレビューに失敗しました: {e}")
        
        ttk.Button(coord_buttons_frame, text="座標をプレビュー", command=preview_coordinates).pack(side=tk.LEFT)
        
        # 検索文字設定
        text_frame = ttk.LabelFrame(dialog, text="検索文字設定", padding="15")
        text_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Label(text_frame, text="検索する文字:").pack(anchor=tk.W)
        target_text_var = tk.StringVar(value=region_data["target_text"])
        ttk.Entry(text_frame, textvariable=target_text_var, width=50).pack(fill=tk.X, pady=2)
        
        # OCRテストボタン
        def test_ocr_region():
            try:
                x, y = coord_vars["x"].get(), coord_vars["y"].get()
                w, h = coord_vars["width"].get(), coord_vars["height"].get()
                image = self.capture_region(x, y, w, h)
                text = self.extract_text_from_image(image)
                messagebox.showinfo("OCRテスト結果", f"検出されたテキスト:\n'{text}'")
            except Exception as e:
                messagebox.showerror("エラー", f"OCRテストに失敗しました: {e}")
        
        ttk.Button(text_frame, text="OCRテスト", command=test_ocr_region).pack(pady=5)

        # 比較領域設定
        compare_frame = ttk.LabelFrame(dialog, text="比較領域設定（オプション）", padding="15")
        compare_frame.pack(fill=tk.X, padx=10, pady=5)

        compare_enabled_var = tk.BooleanVar(value=region_data.get('compare_enabled', False))
        ttk.Checkbutton(compare_frame, text="比較を有効にする", variable=compare_enabled_var).pack(anchor=tk.W)

        # 比較によるトリガーのみ実行するかのオプション
        compare_trigger_only_var = tk.BooleanVar(value=region_data.get('compare_trigger_only', False))
        ttk.Checkbutton(compare_frame, text="比較一致のみでトリガーする", variable=compare_trigger_only_var).pack(anchor=tk.W, pady=(2,5))

        compare_coord_vars = {}
        compare_labels = [("X座標", "x"), ("Y座標", "y"), ("幅", "width"), ("高さ", "height")]
        # 初期値設定
        compare_region = region_data.get('compare_region') or {'x': region_data['x'] + region_data['width'] + 10,
                                                               'y': region_data['y'],
                                                               'width': region_data['width'],
                                                               'height': region_data['height']}

        for i, (label, key) in enumerate(compare_labels):
            row_frame = ttk.Frame(compare_frame)
            row_frame.pack(fill=tk.X, pady=2)
            ttk.Label(row_frame, text=f"比較領域 {label}:").pack(side=tk.LEFT, padx=(0, 10))
            compare_coord_vars[key] = tk.IntVar(value=compare_region.get(key, 0))
            ttk.Entry(row_frame, textvariable=compare_coord_vars[key], width=15).pack(side=tk.LEFT)

        def reselect_compare_region():
            """比較領域を画面上で再選択"""
            dialog.withdraw()
            self.is_selecting_region = True

            def on_compare_selected():
                if hasattr(self, 'selected_region'):
                    compare_coord_vars['x'].set(self.selected_region['x'])
                    compare_coord_vars['y'].set(self.selected_region['y'])
                    compare_coord_vars['width'].set(self.selected_region['width'])
                    compare_coord_vars['height'].set(self.selected_region['height'])
                    dialog.deiconify()

            # 領域選択後のコールバックを設定
            self.region_selection_callback = on_compare_selected
            self.select_region()

        coord_buttons_frame2 = ttk.Frame(compare_frame)
        coord_buttons_frame2.pack(fill=tk.X, pady=(10, 0))
        ttk.Button(coord_buttons_frame2, text="比較領域を再選択", command=reselect_compare_region).pack(side=tk.LEFT, padx=(0, 10))

        def test_compare_ocr():
            try:
                x, y = coord_vars["x"].get(), coord_vars["y"].get()
                w, h = coord_vars["width"].get(), coord_vars["height"].get()
                primary_img = self.capture_region(x, y, w, h)
                primary_text = self.extract_text_from_image(primary_img)

                if not compare_enabled_var.get():
                    messagebox.showinfo("OCR比較結果", f"主領域テキスト:\n'{primary_text}'\n\n比較は無効になっています")
                    return

                cx, cy = compare_coord_vars["x"].get(), compare_coord_vars["y"].get()
                cw, ch = compare_coord_vars["width"].get(), compare_coord_vars["height"].get()
                compare_img = self.capture_region(cx, cy, cw, ch)
                compare_text = self.extract_text_from_image(compare_img)

                match = self.compare_texts(primary_text, compare_text)

                message = f"主領域: '{primary_text}'\n比較領域: '{compare_text}'\n一致: {'はい' if match else 'いいえ'}"
                messagebox.showinfo("OCR比較結果", message)
            except Exception as e:
                messagebox.showerror("エラー", f"OCR比較に失敗しました: {e}")

        ttk.Button(compare_frame, text="比較OCRテスト", command=test_compare_ocr).pack(pady=5)
        
        # 保存・キャンセルボタン
        button_frame = ttk.Frame(dialog)
        button_frame.pack(fill=tk.X, padx=10, pady=10)
        
        def save_region():
            try:
                new_region = {
                    "name": name_var.get(),
                    "x": coord_vars["x"].get(),
                    "y": coord_vars["y"].get(),
                    "width": coord_vars["width"].get(),
                    "height": coord_vars["height"].get(),
                    "target_text": target_text_var.get(),
                    "enabled": enabled_var.get(),
                    "compare_enabled": compare_enabled_var.get(),
                    "compare_trigger_only": compare_trigger_only_var.get(),
                    "compare_region": ({
                        'x': compare_coord_vars['x'].get(),
                        'y': compare_coord_vars['y'].get(),
                        'width': compare_coord_vars['width'].get(),
                        'height': compare_coord_vars['height'].get()
                    } if compare_enabled_var.get() else None),
                    "actions": region_data.get("actions", [{
                        'type': 'click',
                        'x': coord_vars["x"].get() + coord_vars["width"].get() // 2,
                        'y': coord_vars["y"].get() + coord_vars["height"].get() // 2
                    }])
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
                messagebox.showinfo("成功", "領域設定を保存しました")
                
            except Exception as e:
                messagebox.showerror("エラー", f"設定の保存に失敗しました: {e}")
        
        ttk.Button(button_frame, text="保存", command=save_region).pack(side=tk.RIGHT, padx=(5, 0))
        ttk.Button(button_frame, text="キャンセル", command=dialog.destroy).pack(side=tk.RIGHT)
    
    def show_region_preview(self, region):
        """領域プレビューを表示"""
        try:
            image = self.capture_region(region["x"], region["y"], region["width"], region["height"])
            text = self.extract_text_from_image(image)
            messagebox.showinfo("プレビュー", f"検出されたテキスト: '{text}'")
        except Exception as e:
            messagebox.showerror("エラー", f"プレビューに失敗しました: {e}")
    
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
        # イベントを確実に受け取るようにグラブを設定
        try:
            self.selection_window.grab_set()
        except Exception:
            pass
        
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
    
    def cancel_region_selection(self):
        """領域選択をキャンセル"""
        if self.selection_window:
            self.selection_window.destroy()
            self.selection_window = None
        self.root.deiconify()
        self.is_selecting_region = False
        self.log("領域選択をキャンセルしました")
    
    def on_mouse_down(self, event):
        """マウスボタン押下時"""
        # スクリーン座標を保存
        self.start_x = event.x_root
        self.start_y = event.y_root
        # キャンバス原点(スクリーン座標)を取得
        try:
            self._sel_rootx = self.selection_window.winfo_rootx()
            self._sel_rooty = self.selection_window.winfo_rooty()
        except Exception:
            self._sel_rootx = 0
            self._sel_rooty = 0
        
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
        
        # 新しい選択矩形を描画（キャンバス座標に変換）
        try:
            ox = getattr(self, '_sel_rootx', self.selection_window.winfo_rootx())
            oy = getattr(self, '_sel_rooty', self.selection_window.winfo_rooty())
        except Exception:
            ox, oy = 0, 0

        x1 = self.start_x - ox
        y1 = self.start_y - oy
        x2 = event.x_root - ox
        y2 = event.y_root - oy

        self.rect_id = self.canvas.create_rectangle(
            x1, y1, x2, y2,
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
        
        # コールバックがあれば実行、なければデフォルトの動作
        if hasattr(self, 'region_selection_callback') and self.region_selection_callback:
            callback = self.region_selection_callback
            self.region_selection_callback = None  # コールバックをクリア
            callback()
        else:
            # デフォルトの動作：新しい領域追加ダイアログを表示
            self.show_add_region_dialog()
        
        self.log(f"領域を選択しました: ({x}, {y}, {width}, {height})")
    
    def cancel_action_selection(self):
        """アクション座標選択をキャンセル"""
        self.is_selecting_action_position = False
    
    def show_add_region_dialog(self):
        """新しい領域追加ダイアログを表示"""
        if not hasattr(self, 'selected_region'):
            messagebox.showerror("エラー", "領域が選択されていません")
            return
        
        region = self.selected_region
        
        # ダイアログウィンドウを作成
        dialog = tk.Toplevel(self.root)
        dialog.title("新しい領域を追加")
        dialog.geometry("500x400")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # 領域情報表示
        info_frame = ttk.LabelFrame(dialog, text="選択された領域", padding="10")
        info_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Label(info_frame, text=f"座標: ({region['x']}, {region['y']})").pack(anchor=tk.W, padx=5)
        ttk.Label(info_frame, text=f"サイズ: {region['width']} x {region['height']}").pack(anchor=tk.W, padx=5)
        
        # 領域名入力
        name_frame = ttk.LabelFrame(dialog, text="領域設定", padding="10")
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
        
        ttk.Button(test_frame, text="OCRテスト", command=test_ocr).pack(side=tk.LEFT, padx=(0, 10))
        
        # アクション設定（AutoClickerスタイル）
        action_frame = ttk.LabelFrame(dialog, text="アクション設定", padding="10")
        action_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # アクションリスト
        actions_list_frame = ttk.Frame(action_frame)
        actions_list_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # アクション一覧のTreeview
        columns = ("順番", "種類", "詳細", "座標")
        actions_tree = ttk.Treeview(actions_list_frame, columns=columns, show="headings", height=4)
        
        actions_tree.heading("順番", text="順番")
        actions_tree.heading("種類", text="アクション種類")
        actions_tree.heading("詳細", text="詳細")
        actions_tree.heading("座標", text="座標")
        
        actions_tree.column("順番", width=50)
        actions_tree.column("種類", width=80)
        actions_tree.column("詳細", width=150)
        actions_tree.column("座標", width=100)
        
        actions_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        actions_scrollbar = ttk.Scrollbar(actions_list_frame, orient=tk.VERTICAL, command=actions_tree.yview)
        actions_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        actions_tree.configure(yscrollcommand=actions_scrollbar.set)
        
        # アクションデータを保存するリスト
        current_actions = [{
            'type': 'click',
            'x': region['x'] + region['width'] // 2,
            'y': region['y'] + region['height'] // 2
        }]
        
        def update_actions_list():
            """アクションリストを更新"""
            for item in actions_tree.get_children():
                actions_tree.delete(item)
            
            for i, action in enumerate(current_actions, 1):
                action_type = action.get("type", "")
                details = get_action_details_text(action)
                coordinates = get_action_coordinates_text(action)
                
                actions_tree.insert("", tk.END, values=(i, action_type, details, coordinates))
        
        def get_action_details_text(action):
            """アクションの詳細テキストを取得"""
            action_type = action.get("type", "")
            
            if action_type == "click":
                return "クリック"
            elif action_type == "key":
                return f"キー: {action.get('key', '')}"
            elif action_type == "type":
                text = action.get('text', '')
                return f"テキスト: {text[:15]}" + ("..." if len(text) > 15 else "")
            elif action_type == "wait":
                return f"待機: {action.get('duration', 0)}秒"
            else:
                return action_type
        
        def get_action_coordinates_text(action):
            """アクションの座標テキストを取得"""
            action_type = action.get("type", "")
            
            if action_type == "click":
                x = action.get('x', 0)
                y = action.get('y', 0)
                return f"({x}, {y})"
            else:
                return "-"
        
        def add_action():
            """新しいアクションを追加"""
            action_dialog = show_action_dialog(dialog)
            if action_dialog:
                current_actions.append(action_dialog)
                update_actions_list()
        
        def edit_selected_action():
            """選択されたアクションを編集"""
            selected = actions_tree.selection()
            if not selected:
                messagebox.showerror("エラー", "編集するアクションを選択してください")
                return
            
            item = selected[0]
            action_index = int(actions_tree.item(item, "values")[0]) - 1
            
            if 0 <= action_index < len(current_actions):
                edited_action = show_action_dialog(dialog, current_actions[action_index])
                if edited_action:
                    current_actions[action_index] = edited_action
                    update_actions_list()
        
        def delete_selected_action():
            """選択されたアクションを削除"""
            selected = actions_tree.selection()
            if not selected:
                messagebox.showerror("エラー", "削除するアクションを選択してください")
                return
            
            item = selected[0]
            action_index = int(actions_tree.item(item, "values")[0]) - 1
            
            if 0 <= action_index < len(current_actions):
                if messagebox.askyesno("確認", "選択されたアクションを削除しますか？"):
                    del current_actions[action_index]
                    update_actions_list()
        
        def move_action_up():
            """アクションを上に移動"""
            selected = actions_tree.selection()
            if not selected:
                return
            
            item = selected[0]
            action_index = int(actions_tree.item(item, "values")[0]) - 1
            
            if action_index > 0:
                current_actions[action_index], current_actions[action_index-1] = \
                    current_actions[action_index-1], current_actions[action_index]
                update_actions_list()
        
        def move_action_down():
            """アクションを下に移動"""
            selected = actions_tree.selection()
            if not selected:
                return
            
            item = selected[0]
            action_index = int(actions_tree.item(item, "values")[0]) - 1
            
            if action_index < len(current_actions) - 1:
                current_actions[action_index], current_actions[action_index+1] = \
                    current_actions[action_index+1], current_actions[action_index]
                update_actions_list()
        
        # アクション操作ボタン
        action_buttons_frame = ttk.Frame(action_frame)
        action_buttons_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Button(action_buttons_frame, text="追加", command=add_action).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(action_buttons_frame, text="編集", command=edit_selected_action).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(action_buttons_frame, text="削除", command=delete_selected_action).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(action_buttons_frame, text="↑", command=move_action_up).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(action_buttons_frame, text="↓", command=move_action_down).pack(side=tk.LEFT)
        
        def show_action_dialog(parent=None, action_data=None):
            """アクション設定ダイアログを表示"""
            action_dialog = tk.Toplevel(parent or dialog)
            action_dialog.title("アクション設定")
            action_dialog.geometry("500x400")
            action_dialog.transient(parent or dialog)
            action_dialog.grab_set()
            
            result = {}
            
            # アクションタイプ選択
            type_frame = ttk.LabelFrame(action_dialog, text="アクションタイプ", padding="10")
            type_frame.pack(fill=tk.X, padx=10, pady=5)
            
            action_type = tk.StringVar(value=action_data.get('type', 'click') if action_data else 'click')
            
            ttk.Radiobutton(type_frame, text="マウスクリック", variable=action_type, value="click").pack(anchor=tk.W, padx=5)
            ttk.Radiobutton(type_frame, text="キー入力", variable=action_type, value="key").pack(anchor=tk.W, padx=5)
            ttk.Radiobutton(type_frame, text="テキスト入力", variable=action_type, value="type").pack(anchor=tk.W, padx=5)
            ttk.Radiobutton(type_frame, text="待機", variable=action_type, value="wait").pack(anchor=tk.W, padx=5)
            
            # 設定フレーム（動的に変更）
            settings_frame = ttk.LabelFrame(action_dialog, text="設定", padding="10")
            settings_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
            
            # 設定変数
            x_var = tk.IntVar(value=action_data.get('x', region['x'] + region['width'] // 2) if action_data else region['x'] + region['width'] // 2)
            y_var = tk.IntVar(value=action_data.get('y', region['y'] + region['height'] // 2) if action_data else region['y'] + region['height'] // 2)
            key_var = tk.StringVar(value=action_data.get('key', '') if action_data else '')
            text_var = tk.StringVar(value=action_data.get('text', '') if action_data else '')
            wait_var = tk.DoubleVar(value=action_data.get('duration', 1.0) if action_data else 1.0)
            
            def update_settings_frame():
                """設定フレームの内容を更新"""
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
                        """座標選択機能"""
                        action_dialog.withdraw()
                        
                        # 座標選択用の透明オーバーレイウィンドウを作成
                        coord_window = tk.Toplevel(action_dialog)
                        coord_window.attributes('-fullscreen', True)
                        coord_window.attributes('-alpha', 0.1)
                        coord_window.configure(bg='red')
                        coord_window.attributes('-topmost', True)
                        
                        # 情報ラベル
                        info_label = tk.Label(coord_window, 
                                            text="クリックする座標を選択してください\n（ESCキーでキャンセル）", 
                                            font=('Arial', 16, 'bold'), 
                                            fg='white', bg='red')
                        info_label.pack(pady=50)
                        
                        # 現在のマウス座標を表示するラベル
                        coord_label = tk.Label(coord_window, 
                                             text="座標: (0, 0)", 
                                             font=('Arial', 14), 
                                             fg='yellow', bg='red')
                        coord_label.pack(pady=10)
                        
                        def update_coord_display():
                            """マウス座標をリアルタイム表示"""
                            try:
                                mouse_x, mouse_y = pyautogui.position()
                                coord_label.config(text=f"座標: ({mouse_x}, {mouse_y})")
                                coord_window.after(50, update_coord_display)  # 50ms毎に更新
                            except:
                                pass
                        
                        def on_click(event):
                            """クリック時に座標を取得"""
                            try:
                                selected_x = event.x_root
                                selected_y = event.y_root
                                
                                # 座標を設定
                                x_var.set(selected_x)
                                y_var.set(selected_y)
                                
                                # ウィンドウを閉じる
                                coord_window.destroy()
                                action_dialog.deiconify()
                                
                                # 成功メッセージ
                                messagebox.showinfo("座標選択完了", 
                                                  f"座標 ({selected_x}, {selected_y}) を設定しました")
                            except Exception as e:
                                messagebox.showerror("エラー", f"座標選択に失敗しました: {e}")
                                coord_window.destroy()
                                action_dialog.deiconify()
                        
                        def on_cancel(event=None):
                            """キャンセル処理"""
                            coord_window.destroy()
                            action_dialog.deiconify()
                            messagebox.showinfo("キャンセル", "座標選択をキャンセルしました")
                        
                        def on_key(event):
                            """キーボードイベント処理"""
                            if event.keysym == 'Escape':
                                on_cancel()
                        
                        # イベントバインド
                        coord_window.bind('<Button-1>', on_click)
                        coord_window.bind('<Escape>', on_cancel)
                        coord_window.bind('<KeyPress>', on_key)
                        coord_window.focus_set()
                        
                        # マウス座標の更新を開始
                        update_coord_display()
                    
                    button_frame = ttk.Frame(coord_frame)
                    button_frame.pack(side=tk.RIGHT)
                    
                    ttk.Button(button_frame, text="画面上で選択", command=select_coordinates).pack(side=tk.LEFT, padx=(0, 5))
                    
                    def set_center_position():
                        """画面中央に設定"""
                        import tkinter as tk
                        screen_width = coord_frame.winfo_screenwidth()
                        screen_height = coord_frame.winfo_screenheight()
                        x_var.set(screen_width // 2)
                        y_var.set(screen_height // 2)
                        messagebox.showinfo("座標設定", f"画面中央 ({screen_width//2}, {screen_height//2}) に設定しました")
                    
                    ttk.Button(button_frame, text="画面中央", command=set_center_position).pack(side=tk.LEFT)
                    
                elif action_t == 'key':
                    ttk.Label(settings_frame, text="キー:").pack(anchor=tk.W, padx=5)
                    key_entry = ttk.Entry(settings_frame, textvariable=key_var, width=30)
                    key_entry.pack(fill=tk.X, padx=5, pady=2)
                    ttk.Label(settings_frame, text="例: space, enter, f1, ctrl+c", font=('TkDefaultFont', 8)).pack(anchor=tk.W, padx=5, pady=5)
                    
                elif action_t == 'type':
                    ttk.Label(settings_frame, text="入力するテキスト:").pack(anchor=tk.W, padx=5)
                    text_entry = tk.Text(settings_frame, width=40, height=4)
                    text_entry.pack(fill=tk.BOTH, expand=True, padx=5, pady=2)
                    text_entry.insert('1.0', text_var.get())
                    
                    def update_text_var(*args):
                        text_var.set(text_entry.get('1.0', tk.END).strip())
                    text_entry.bind('<KeyRelease>', update_text_var)
                    
                elif action_t == 'wait':
                    wait_frame = ttk.Frame(settings_frame)
                    wait_frame.pack(fill=tk.X, padx=5, pady=2)
                    
                    ttk.Label(wait_frame, text="待機時間(秒):").pack(side=tk.LEFT)
                    ttk.Entry(wait_frame, textvariable=wait_var, width=10).pack(side=tk.LEFT, padx=5)
            
            # タイプ変更時にフレームを更新
            action_type.trace('w', lambda *args: update_settings_frame())
            update_settings_frame()
            
            # ボタン
            btn_frame = ttk.Frame(action_dialog)
            btn_frame.pack(fill=tk.X, padx=10, pady=10)
            
            def save_action():
                action_t = action_type.get()
                
                if action_t == 'click':
                    result.update({
                        'type': 'click',
                        'x': x_var.get(),
                        'y': y_var.get()
                    })
                elif action_t == 'key':
                    result.update({
                        'type': 'key',
                        'key': key_var.get()
                    })
                elif action_t == 'type':
                    result.update({
                        'type': 'type',
                        'text': text_var.get()
                    })
                elif action_t == 'wait':
                    result.update({
                        'type': 'wait',
                        'duration': wait_var.get()
                    })
                
                action_dialog.result = result
                action_dialog.destroy()
            
            def cancel_action():
                action_dialog.result = None
                action_dialog.destroy()
            
            ttk.Button(btn_frame, text="OK", command=save_action).pack(side=tk.RIGHT, padx=5)
            ttk.Button(btn_frame, text="キャンセル", command=cancel_action).pack(side=tk.RIGHT)
            
            # ダイアログの結果を待つ
            action_dialog.result = None
            action_dialog.wait_window()
            
            return action_dialog.result
        
        # 初期リスト表示
        update_actions_list()
        
        # 比較領域設定（追加ダイアログ用）
        compare_frame_add = ttk.LabelFrame(dialog, text="比較領域設定（オプション）", padding="10")
        compare_frame_add.pack(fill=tk.X, padx=10, pady=5)

        compare_enabled_var_add = tk.BooleanVar(value=False)
        ttk.Checkbutton(compare_frame_add, text="比較を有効にする", variable=compare_enabled_var_add).pack(anchor=tk.W)

        compare_trigger_only_var_add = tk.BooleanVar(value=False)
        ttk.Checkbutton(compare_frame_add, text="比較一致のみでトリガーする", variable=compare_trigger_only_var_add).pack(anchor=tk.W, pady=(2,5))

        # 比較領域のデフォルトは主領域の右側に配置
        compare_coord_vars_add = {}
        compare_region_default = {'x': region['x'] + region['width'] + 10,
                                   'y': region['y'],
                                   'width': region['width'],
                                   'height': region['height']}

        compare_labels = [("X座標", "x"), ("Y座標", "y"), ("幅", "width"), ("高さ", "height")]
        for i, (label, key) in enumerate(compare_labels):
            row_frame = ttk.Frame(compare_frame_add)
            row_frame.pack(fill=tk.X, pady=2)
            ttk.Label(row_frame, text=f"比較領域 {label}:").pack(side=tk.LEFT, padx=(0, 10))
            compare_coord_vars_add[key] = tk.IntVar(value=compare_region_default.get(key, 0))
            ttk.Entry(row_frame, textvariable=compare_coord_vars_add[key], width=15).pack(side=tk.LEFT)

        def reselect_compare_region_add():
            dialog.withdraw()
            self.is_selecting_region = True

            def on_compare_selected_add():
                if hasattr(self, 'selected_region'):
                    compare_coord_vars_add['x'].set(self.selected_region['x'])
                    compare_coord_vars_add['y'].set(self.selected_region['y'])
                    compare_coord_vars_add['width'].set(self.selected_region['width'])
                    compare_coord_vars_add['height'].set(self.selected_region['height'])
                    dialog.deiconify()

            self.region_selection_callback = on_compare_selected_add
            self.select_region()

        coord_buttons_frame_add = ttk.Frame(compare_frame_add)
        coord_buttons_frame_add.pack(fill=tk.X, pady=(10, 0))
        ttk.Button(coord_buttons_frame_add, text="比較領域を選択", command=reselect_compare_region_add).pack(side=tk.LEFT, padx=(0, 10))

        # ボタン
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(fill=tk.X, padx=10, pady=10)
        
        def save_region():
            if not name_var.get().strip():
                messagebox.showwarning("警告", "領域名を入力してください")
                return
            
            # 検索文字が空でも、比較のみでトリガーする設定が有効なら許可する
            if not search_var.get().strip() and not (compare_enabled_var_add.get() and compare_trigger_only_var_add.get()):
                messagebox.showwarning("警告", "検索する文字を入力してください")
                return
            
            # 新しい領域を作成
            new_region = {
                'name': name_var.get().strip(),
                'x': region['x'],
                'y': region['y'],
                'width': region['width'],
                'height': region['height'],
                'target_text': search_var.get().strip(),
                'actions': current_actions.copy(),
                'enabled': True,
                'compare_enabled': compare_enabled_var_add.get(),
                'compare_trigger_only': compare_trigger_only_var_add.get(),
                'compare_region': ({
                    'x': compare_coord_vars_add['x'].get(),
                    'y': compare_coord_vars_add['y'].get(),
                    'width': compare_coord_vars_add['width'].get(),
                    'height': compare_coord_vars_add['height'].get()
                } if compare_enabled_var_add.get() else None)
            }
            
            # 現在のセットに追加
            if self.current_region_set not in self.monitoring_regions:
                self.monitoring_regions[self.current_region_set] = []
            
            self.monitoring_regions[self.current_region_set].append(new_region)
            
            # UIを更新
            self.update_regions_list()
            self.update_region_sets_list()
            self.save_regions()
            
            self.log(f"新しい領域を追加しました: {new_region['name']}")
            messagebox.showinfo("成功", f"領域 '{new_region['name']}' を追加しました")
            dialog.destroy()
        
        save_btn = ttk.Button(btn_frame, text="保存", command=save_region)
        save_btn.pack(side=tk.RIGHT, padx=5)
        cancel_btn = ttk.Button(btn_frame, text="キャンセル", command=dialog.destroy)
        cancel_btn.pack(side=tk.RIGHT)
        
        # フォーカスを名前入力欄に設定
        name_entry.focus_set()
    
    # ===== メニュー機能 =====
    def import_config(self):
        """設定をインポート"""
        messagebox.showinfo("情報", "この機能は実装中です")
    
    def export_config(self):
        """設定をエクスポート"""
        messagebox.showinfo("情報", "この機能は実装中です")
        
    def backup_regions(self):
        """領域データをバックアップ"""
        messagebox.showinfo("情報", "この機能は実装中です")
        
    def restore_regions(self):
        """領域データを復元"""
        messagebox.showinfo("情報", "この機能は実装中です")
    
    def show_help(self):
        """ヘルプを表示"""
        help_text = """
🔍 Text Recognition Macro System - 使用方法

📋 基本的な使用手順:
1. 「新しい領域を追加」をクリック (F7)
2. 画面上で監視したい領域をドラッグ選択
3. 検索文字とアクション（クリック等）を設定
4. 「監視開始」で自動実行開始 (F6)

⚡ ショートカットキー:
F6: 監視開始/停止
F7: 新しい領域追加
F8: 緊急停止
        """
        
        help_window = tk.Toplevel(self.root)
        help_window.title("使用方法")
        help_window.geometry("600x400")
        
        text_widget = tk.Text(help_window, wrap=tk.WORD, padx=20, pady=20)
        text_widget.pack(fill=tk.BOTH, expand=True)
        text_widget.insert('1.0', help_text)
        text_widget.config(state=tk.DISABLED)
    
    def show_about(self):
        """バージョン情報を表示"""
        about_text = """
Text Recognition Macro System
Version 2.0 - 改良版

AutoClickerの設計を参考にした
高機能文字認識マクロシステム
        """
        messagebox.showinfo("バージョン情報", about_text)
    
    def install_ocr_engine(self):
        """OCRエンジンのセットアップを実行"""
        messagebox.showinfo("情報", "OCRセットアップ機能は実装中です")
    
    def on_closing(self):
        """アプリケーション終了時の処理"""
        if self.running:
            self.stop_monitoring()
        
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