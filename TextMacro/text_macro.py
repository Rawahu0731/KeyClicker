"""
Text Recognition Macro System
画面の指定領域の文字を読み取り、一致した場合にマクロを実行するシステム
"""

import numpy as np
import pytesseract
import pyautogui
import pynput
from pynput import mouse, keyboard
import json
import time
import threading
from PIL import Image, ImageGrab

class TextMacroSystem:
    def __init__(self, config_file="config.json"):
        self.config_file = config_file
        self.config = self.load_config()
        self.running = False
        self.monitoring_thread = None
        
        # pyautoguiの設定
        pyautogui.FAILSAFE = True
        pyautogui.PAUSE = 0.1
        
        # OCRエンジンの設定（Tesseractのパスを設定）
        # Tesseractがインストールされていない場合は、以下の行をコメントアウトしてください
        # pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
        
    def load_config(self):
        """設定ファイルを読み込む"""
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            # デフォルト設定を作成
            default_config = {
                "monitoring_regions": [
                    {
                        "name": "region1",
                        "x": 100,
                        "y": 100,
                        "width": 200,
                        "height": 50,
                        "target_text": "開始",
                        "actions": [
                            {"type": "click", "x": 500, "y": 300},
                            {"type": "key", "key": "space"},
                            {"type": "type", "text": "Hello World"}
                        ]
                    }
                ],
                "check_interval": 1.0,
                "ocr_language": "jpn+eng"
            }
            self.save_config(default_config)
            return default_config
    
    def save_config(self, config=None):
        """設定ファイルを保存"""
        if config is None:
            config = self.config
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    
    def capture_region(self, x, y, width, height):
        """指定領域をキャプチャ"""
        screenshot = ImageGrab.grab(bbox=(x, y, x + width, y + height))
        return np.array(screenshot)
    
    def extract_text_from_image(self, image, language="jpn+eng"):
        """画像から文字を抽出"""
        try:
            # OCR処理
            text = pytesseract.image_to_string(
                Image.fromarray(image), 
                lang=language,
                config='--psm 6'
            ).strip()
            return text
        except Exception as e:
            print(f"OCRエラー: {e}")
            return ""
    
    def execute_action(self, action):
        """アクションを実行"""
        action_type = action.get("type")
        
        if action_type == "click":
            # マウスクリック
            x, y = action.get("x", 0), action.get("y", 0)
            button = action.get("button", "left")
            pyautogui.click(x, y, button=button)
            print(f"クリック実行: ({x}, {y})")
            
        elif action_type == "key":
            # キー入力
            key = action.get("key")
            pyautogui.press(key)
            print(f"キー入力: {key}")
            
        elif action_type == "hotkey":
            # ホットキー入力
            keys = action.get("keys", [])
            pyautogui.hotkey(*keys)
            print(f"ホットキー: {'+'.join(keys)}")
            
        elif action_type == "type":
            # テキスト入力
            text = action.get("text", "")
            pyautogui.write(text, interval=0.05)
            print(f"テキスト入力: {text}")
            
        elif action_type == "move":
            # マウス移動
            x, y = action.get("x", 0), action.get("y", 0)
            pyautogui.moveTo(x, y)
            print(f"マウス移動: ({x}, {y})")
            
        elif action_type == "scroll":
            # スクロール
            clicks = action.get("clicks", 1)
            pyautogui.scroll(clicks)
            print(f"スクロール: {clicks}")
            
        elif action_type == "wait":
            # 待機
            duration = action.get("duration", 1)
            time.sleep(duration)
            print(f"待機: {duration}秒")
    
    def check_text_match(self, detected_text, target_text):
        """文字の一致をチェック"""
        # 完全一致
        if target_text.lower() in detected_text.lower():
            return True
        return False
    
    def monitor_text(self):
        """文字監視のメインループ"""
        print("文字監視を開始しました...")
        
        while self.running:
            try:
                for region in self.config["monitoring_regions"]:
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
                    
                    if detected_text:
                        print(f"[{name}] 検出された文字: '{detected_text}'")
                    
                    # 文字が一致したかチェック
                    if self.check_text_match(detected_text, target_text):
                        print(f"[{name}] 文字が一致しました！マクロを実行します...")
                        
                        # アクションを実行
                        for action in actions:
                            self.execute_action(action)
                            time.sleep(0.1)  # アクション間の待機
                        
                        print(f"[{name}] マクロ実行完了")
                
                # 次のチェックまで待機
                time.sleep(self.config.get("check_interval", 1.0))
                
            except Exception as e:
                print(f"監視エラー: {e}")
                time.sleep(1)
    
    def start_monitoring(self):
        """監視を開始"""
        if not self.running:
            self.running = True
            self.monitoring_thread = threading.Thread(target=self.monitor_text)
            self.monitoring_thread.daemon = True
            self.monitoring_thread.start()
            print("監視を開始しました")
        else:
            print("すでに監視中です")
    
    def stop_monitoring(self):
        """監視を停止"""
        if self.running:
            self.running = False
            if self.monitoring_thread:
                self.monitoring_thread.join()
            print("監視を停止しました")
        else:
            print("監視は実行されていません")
    
    def add_region(self, name, x, y, width, height, target_text, actions):
        """新しい監視領域を追加"""
        new_region = {
            "name": name,
            "x": x,
            "y": y,
            "width": width,
            "height": height,
            "target_text": target_text,
            "actions": actions
        }
        self.config["monitoring_regions"].append(new_region)
        self.save_config()
        print(f"新しい監視領域 '{name}' を追加しました")


def main():
    """メイン関数"""
    system = TextMacroSystem()
    
    print("=== Text Recognition Macro System ===")
    print("コマンド:")
    print("  start  - 監視開始")
    print("  stop   - 監視停止")
    print("  config - 設定表示")
    print("  test   - テスト実行")
    print("  quit   - 終了")
    print()
    
    try:
        while True:
            command = input("コマンドを入力してください: ").strip().lower()
            
            if command == "start":
                system.start_monitoring()
                
            elif command == "stop":
                system.stop_monitoring()
                
            elif command == "config":
                print("現在の設定:")
                print(json.dumps(system.config, ensure_ascii=False, indent=2))
                
            elif command == "test":
                print("テスト実行...")
                # 最初の監視領域でテスト
                if system.config["monitoring_regions"]:
                    region = system.config["monitoring_regions"][0]
                    image = system.capture_region(
                        region["x"], region["y"], 
                        region["width"], region["height"]
                    )
                    text = system.extract_text_from_image(image)
                    print(f"検出された文字: '{text}'")
                else:
                    print("監視領域が設定されていません")
                    
            elif command == "quit":
                system.stop_monitoring()
                break
                
            else:
                print("不明なコマンドです")
                
    except KeyboardInterrupt:
        print("\n終了中...")
        system.stop_monitoring()


if __name__ == "__main__":
    main()