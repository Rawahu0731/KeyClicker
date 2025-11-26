import ctypes
import time
import threading
from ctypes import wintypes

# Windows API関数の定義
user32 = ctypes.WinDLL('user32', use_last_error=True)

# キーコード
VK_RETURN = 0x0D

# キーイベントフラグ
KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002

# keybd_event関数
keybd_event = user32.keybd_event
keybd_event.argtypes = [wintypes.BYTE, wintypes.BYTE, wintypes.DWORD, ctypes.POINTER(wintypes.ULONG)]
keybd_event.restype = None

# 停止フラグ
stop_flag = False
# 合計押下回数（全サイクル通算）
total_presses = 0
# 現在サイクル内の押下回数
cycle_presses = 0
# 最大押下回数（1サイクルあたり）
MAX_PRESSES = 10000
# クールダウン時間（秒）
COOLDOWN_SECONDS = 45
# カウント用ロック
press_lock = threading.Lock()

def press_enter_fast():
    """1秒間に約200回のペースでEnterキーを連打（サイクル内で MAX_PRESSES 回で終了）"""
    global stop_flag, total_presses, cycle_presses

    # 1秒間に200回 = 0.005秒間隔
    target_interval = 0.005

    while not stop_flag:
        start = time.perf_counter()

        # キーダウン
        keybd_event(VK_RETURN, 0, KEYEVENTF_EXTENDEDKEY, None)
        # キーアップ
        keybd_event(VK_RETURN, 0, KEYEVENTF_EXTENDEDKEY | KEYEVENTF_KEYUP, None)

        # カウントをインクリメント（サイクルと合計）
        with press_lock:
            total_presses += 1
            cycle_presses += 1
            # サイクル上限に到達したらこのスレッドは終了
            if cycle_presses >= MAX_PRESSES:
                break

        # 次の押下まで待機
        elapsed = time.perf_counter() - start
        sleep_time = target_interval - elapsed
        if sleep_time > 0:
            time.sleep(sleep_time)

def monitor_stats():
    """統計情報を表示（合計押下回数と現在速度/平均を表示）"""
    global total_presses, stop_flag
    start_time = time.time()
    last_count = 0

    while not stop_flag:
        time.sleep(1)
        current_count = total_presses
        elapsed = time.time() - start_time
        pps = (current_count - last_count)  # 1秒あたりの押下回数
        total_pps = current_count / elapsed if elapsed > 0 else 0

        print(f"\r合計押下回数: {current_count:,} | 現在速度: {pps:,} press/sec | 平均: {total_pps:,.1f} press/sec", end="", flush=True)
        last_count = current_count

def main():
    global stop_flag, total_presses, cycle_presses

    print("=" * 70)
    print("Enter連打ツール (1秒間に約200回)")
    print("=" * 70)
    print("\n[設定] 1サイクル: {} 回押下、その後 {} 秒クールダウンを繰り返します".format(MAX_PRESSES, COOLDOWN_SECONDS))
    print("開始後、3秒間の猶予があります。その間にターゲットウィンドウをアクティブにしてください")
    print("停止するには、Ctrl+Cを押してください")
    print("\n準備ができたらEnterキーを押してください...")
    input()

    print("\n3秒後に開始します...")
    for i in range(3, 0, -1):
        print(f"{i}...")
        time.sleep(1)

    print(f"\n[開始] Enter連打を実行中... (Ctrl+Cで停止)。サイクル: {MAX_PRESSES:,} 回 -> {COOLDOWN_SECONDS} 秒 クールダウン\n")

    # シングルスレッドで実行（速度制限のため）
    num_threads = 1

    # 統計モニタースレッド
    stats_thread = threading.Thread(target=monitor_stats, daemon=True)
    stats_thread.start()

    try:
        while not stop_flag:
            # サイクル用カウンタをリセット
            with press_lock:
                cycle_presses = 0

            threads = []
            for _ in range(num_threads):
                t = threading.Thread(target=press_enter_fast, daemon=False)
                t.start()
                threads.append(t)

            # サイクル内スレッドが完了するまで待機
            while any(t.is_alive() for t in threads):
                time.sleep(0.1)
                if stop_flag:
                    break

            if stop_flag:
                break

            print(f"\n[サイクル完了] {MAX_PRESSES:,} 回押しました。クールダウン {COOLDOWN_SECONDS} 秒...\n")

            # クールダウン（Ctrl+C を許容）
            remaining = COOLDOWN_SECONDS
            try:
                while remaining > 0 and not stop_flag:
                    time.sleep(1)
                    remaining -= 1
            except KeyboardInterrupt:
                stop_flag = True
                break

    except KeyboardInterrupt:
        print("\n\n[停止] ユーザによる割り込みを受けました。終了します...")
        stop_flag = True
    finally:
        # 少し待ってスレッドを落ち着かせる
        time.sleep(0.5)
        print(f"\n最終結果: 合計 {total_presses:,} 回のEnter押下を実行しました")

if __name__ == "__main__":
    main()