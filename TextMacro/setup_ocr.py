"""
OCRエンジンセットアップスクリプト
Tesseract OCRまたはEasyOCRを自動的にセットアップします
"""
import os
import sys
import subprocess
import urllib.request
import zipfile
import platform

def check_python_version():
    """Pythonバージョンをチェック"""
    if sys.version_info < (3, 7):
        print("エラー: Python 3.7以上が必要です")
        return False
    print(f"Python {sys.version} を検出")
    return True

def install_requirements():
    """基本的な依存関係をインストール"""
    try:
        print("基本的な依存関係をインストール中...")
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt'])
        print("✓ 基本的な依存関係のインストール完了")
        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ 依存関係のインストールに失敗: {e}")
        return False

def check_tesseract():
    """Tesseractがインストールされているかチェック"""
    try:
        result = subprocess.run(['tesseract', '--version'], 
                              capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            print("✓ Tesseract が見つかりました")
            print(result.stdout.split('\n')[0])
            return True
    except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.SubprocessError):
        pass
    
    # Windowsの一般的なパスをチェック
    if platform.system() == "Windows":
        possible_paths = [
            r'C:\Program Files\Tesseract-OCR\tesseract.exe',
            r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                print(f"✓ Tesseract が見つかりました: {path}")
                return True
    
    print("✗ Tesseract が見つかりません")
    return False

def install_easyocr():
    """EasyOCRをインストール"""
    try:
        print("EasyOCRをインストール中...")
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'easyocr'])
        print("✓ EasyOCRのインストール完了")
        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ EasyOCRのインストールに失敗: {e}")
        return False

def show_tesseract_install_guide():
    """Tesseractのインストールガイドを表示"""
    print("\n" + "="*60)
    print("Tesseract OCR インストールガイド")
    print("="*60)
    
    if platform.system() == "Windows":
        print("""
Windows用 Tesseract インストール手順:

1. 以下のURLからTesseractをダウンロード:
   https://github.com/UB-Mannheim/tesseract/wiki

2. 「tesseract-ocr-w64-setup-v5.x.x.xxxxxxxx.exe」をダウンロード

3. インストーラーを実行し、以下のオプションを選択:
   - 「Additional script data」
   - 「Japanese」（日本語認識用）

4. インストール完了後、システムを再起動

5. コマンドプロンプトで以下を実行して確認:
   tesseract --version

注意: デフォルトのインストールパスは以下のいずれかです:
- C:\\Program Files\\Tesseract-OCR\\
- C:\\Program Files (x86)\\Tesseract-OCR\\
""")
    
    elif platform.system() == "Darwin":  # macOS
        print("""
macOS用 Tesseract インストール手順:

1. Homebrewを使用（推奨）:
   brew install tesseract
   brew install tesseract-lang  # 日本語サポート用

2. または MacPortsを使用:
   sudo port install tesseract-4
   sudo port install tesseract-jpn

3. インストール確認:
   tesseract --version
""")
    
    else:  # Linux
        print("""
Linux用 Tesseract インストール手順:

Ubuntu/Debian:
   sudo apt update
   sudo apt install tesseract-ocr tesseract-ocr-jpn

CentOS/RHEL/Fedora:
   sudo yum install tesseract tesseract-langpack-jpn
   # または
   sudo dnf install tesseract tesseract-langpack-jpn

インストール確認:
   tesseract --version
""")

def main():
    print("Text Recognition Macro System - OCRセットアップ")
    print("="*50)
    
    # Pythonバージョンチェック
    if not check_python_version():
        return
    
    # 基本依存関係をインストール
    if not install_requirements():
        print("基本依存関係のインストールに失敗しました")
        return
    
    # Tesseractチェック
    if check_tesseract():
        print("\n✓ セットアップ完了！Tesseractが利用可能です")
        print("text_macro_gui.py を実行してアプリケーションを開始できます")
        return
    
    print("\nOCRエンジンのセットアップオプション:")
    print("1. Tesseract OCR (推奨) - 高精度、日本語対応")
    print("2. EasyOCR (代替) - 簡単インストール")
    print("3. セットアップガイドのみ表示")
    
    choice = input("\n選択してください (1-3): ").strip()
    
    if choice == "1":
        show_tesseract_install_guide()
        print("\nTesseractのインストール後、このスクリプトを再実行してください")
    
    elif choice == "2":
        if install_easyocr():
            print("\n✓ セットアップ完了！EasyOCRが利用可能です")
            print("text_macro_gui.py を実行してアプリケーションを開始できます")
        else:
            print("\nEasyOCRのインストールに失敗しました")
    
    elif choice == "3":
        show_tesseract_install_guide()
    
    else:
        print("無効な選択です")

if __name__ == "__main__":
    main()
    input("\nEnterキーを押して終了...")