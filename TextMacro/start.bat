@echo off
echo Text Recognition Macro System を起動中...
cd /d "%~dp0"

REM Pythonの存在確認
python --version >nul 2>&1
if errorlevel 1 (
    echo エラー: Pythonがインストールされていません
    echo https://www.python.org/ からPythonをインストールしてください
    pause
    exit /b 1
)

REM 必要なライブラリのインストール確認
echo 必要なライブラリをチェック中...
pip show pyautogui >nul 2>&1
if errorlevel 1 (
    echo 必要なライブラリをインストール中...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo エラー: ライブラリのインストールに失敗しました
        pause
        exit /b 1
    )
)

REM OCRエンジンのチェック（オプション）
echo OCRエンジンをチェック中...
python -c "import pytesseract; print('Tesseract OK')" 2>nul
if errorlevel 1 (
    python -c "import easyocr; print('EasyOCR OK')" 2>nul
    if errorlevel 1 (
        echo.
        echo 警告: OCRエンジンが見つかりません
        echo setup_ocr.py を実行してOCRエンジンをセットアップすることをお勧めします
        echo.
        set /p choice="OCRセットアップを実行しますか？ (y/n): "
        if /i "%choice%"=="y" (
            python setup_ocr.py
            pause
            exit /b 0
        )
    )
)

REM アプリケーション起動
echo アプリケーションを起動中...
python text_macro_gui.py

if errorlevel 1 (
    echo エラーが発生しました
    pause
)