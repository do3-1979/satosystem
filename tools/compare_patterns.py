"""
Task42 パリティ検証スクリプト
パターン1 (use_cached_hot_test) vs パターン2 (back_test=1) の損益比較

使用期間: 2025/12/01〜2025/12/31（キャッシュ完全保持）
"""
import os
import sys
import configparser
import subprocess
import re
import time
import shutil
from datetime import datetime

WORKSPACE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(WORKSPACE_ROOT, "src")
CONFIG_PATH = os.path.join(SRC_DIR, "config.ini")
BACKUP_PATH = CONFIG_PATH + ".parity_backup"

def read_config():
    """config.ini をそのまま文字列で読む"""
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return f.read()

def write_config(content):
    """config.ini を書き戻す"""
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        f.write(content)

def set_pattern(original: str, pattern: int) -> str:
    """config.ini テキストをパターンに応じて書き換える"""
    text = original

    # Period を固定（Q4 2025: キャッシュ完全保持、トレード発生確認済み）
    text = re.sub(r'start_time\s*=.*', 'start_time = 2025/10/01 00:00', text)
    text = re.sub(r'end_time\s*=.*', 'end_time = 2025/12/31 23:59', text)

    if pattern == 1:
        # キャッシュベースホットテスト
        text = re.sub(r'back_test\s*=\s*\d', 'back_test = 0', text)
        text = re.sub(r'hot_test_dummy_mode\s*=\s*\d', 'hot_test_dummy_mode = 1', text)
        text = re.sub(r'use_cached_data_for_hot_test\s*=\s*\d', 'use_cached_data_for_hot_test = 1', text)
    else:
        # 従来バックテスト
        text = re.sub(r'back_test\s*=\s*\d', 'back_test = 1', text)
        text = re.sub(r'hot_test_dummy_mode\s*=\s*\d', 'hot_test_dummy_mode = 1', text)
        text = re.sub(r'use_cached_data_for_hot_test\s*=\s*\d', 'use_cached_data_for_hot_test = 0', text)
    return text

def parse_result(output: str) -> dict:
    """bot.py の出力から主要指標を抽出"""
    result = {}

    # 最終損益
    m = re.search(r'最終損益[：:\s]+([-\d.]+)', output)
    if m:
        result['pnl'] = float(m.group(1))

    # プロフィットファクター
    m = re.search(r'プロフィットファクター[：:\s]+([-\d.]+)', output)
    if m:
        result['pf'] = float(m.group(1))

    # 最大ドローダウン率
    m = re.search(r'最大ドローダウン率[：:\s]+([-\d.]+)', output)
    if m:
        result['dd_rate'] = float(m.group(1))

    # Sharpe
    m = re.search(r'Sharpe[：:\s]+([-\d.]+)', output)
    if m:
        result['sharpe'] = float(m.group(1))

    # WinRate / Trades
    m = re.search(r'WinRate[：:\s]+([-\d.]+)%\s+Trades[：:\s]+(\d+)', output)
    if m:
        result['win_rate'] = float(m.group(1))
        result['trades'] = int(m.group(2))

    # トレード統計
    m = re.search(r'トレード統計[：:\s]+総数=(\d+).*?完了=(\d+).*?勝=(\d+).*?負=(\d+).*?勝率=([-\d.]+)%', output)
    if m:
        result['total_trades'] = int(m.group(1))
        result['completed']    = int(m.group(2))
        result['wins']         = int(m.group(3))
        result['losses']       = int(m.group(4))
        result['win_rate2']    = float(m.group(5))

    return result

def run_bot() -> tuple:
    """bot.py を実行し (output, elapsed_sec) を返す"""
    start = time.time()
    result = subprocess.run(
        [sys.executable, "bot.py"],
        capture_output=True,
        text=True,
        cwd=SRC_DIR,
        timeout=300
    )
    elapsed = time.time() - start
    output = result.stdout + result.stderr
    return output, elapsed

def main():
    print("=" * 60)
    print("🔬 Task42 パリティ検証")
    print(f"📅 対象期間: 2025/10/01 〜 2025/12/31（Q4 2025、トレード発生確認済み）")
    print("=" * 60)

    # バックアップ
    original = read_config()
    shutil.copy(CONFIG_PATH, BACKUP_PATH)

    results = {}
    outputs = {}

    for pattern in [1, 2]:
        label = "パターン1 (back_test=0, use_cached=1)" if pattern == 1 else "パターン2 (back_test=1)"
        print(f"\n▶ {label} 実行中...")
        try:
            write_config(set_pattern(original, pattern))
            output, elapsed = run_bot()
            outputs[pattern] = output
            results[pattern] = parse_result(output)
            results[pattern]['elapsed'] = elapsed
            print(f"  ✅ 完了 ({elapsed:.1f}秒)")
        except subprocess.TimeoutExpired:
            print(f"  ❌ タイムアウト（300秒超過）")
            results[pattern] = {'error': 'timeout'}
        except Exception as e:
            print(f"  ❌ エラー: {e}")
            results[pattern] = {'error': str(e)}
        finally:
            # 毎回バックアップから復元
            write_config(original)

    # --- 比較レポート ---
    print("\n" + "=" * 60)
    print("📊 比較結果")
    print("=" * 60)

    p1 = results.get(1, {})
    p2 = results.get(2, {})

    headers = [
        ('pnl',       '最終損益 (USD)'),
        ('pf',        'プロフィットファクター'),
        ('dd_rate',   '最大DD率 (%)'),
        ('sharpe',    'Sharpe比'),
        ('win_rate',  '勝率 (%)'),
        ('trades',    'トレード数'),
        ('elapsed',   '実行時間 (秒)'),
    ]

    print(f"{'指標':<25} {'パターン1':>15} {'パターン2':>15} {'差異':>12}")
    print("-" * 70)
    for key, label in headers:
        v1 = p1.get(key, 'N/A')
        v2 = p2.get(key, 'N/A')
        if isinstance(v1, float) and isinstance(v2, float):
            diff = v1 - v2
            diff_str = f"{diff:+.2f}"
        else:
            diff_str = "-"
        print(f"{label:<25} {str(v1):>15} {str(v2):>15} {diff_str:>12}")

    # 実行時間の設計期待値チェック
    print()
    if 'elapsed' in p1 and 'elapsed' in p2:
        ratio = p2['elapsed'] / max(p1['elapsed'], 0.1)
        print(f"⏱️  速度比 (P2/P1): {ratio:.1f}x  （期待値: P2がP1より速い、または同等）")
        if p1['elapsed'] > p2['elapsed']:
            print(f"   → パターン1がパターン2より遅い ({p1['elapsed']:.1f}s vs {p2['elapsed']:.1f}s)")
            print(f"   → 理由: パターン1は1分足も使用するため処理が多い（設計通り）")
        else:
            print(f"   → パターン1がパターン2より速い・同等 ({p1['elapsed']:.1f}s vs {p2['elapsed']:.1f}s)")

    # 損益の乖離チェック
    print()
    if 'pnl' in p1 and 'pnl' in p2:
        pnl_diff = abs(p1['pnl'] - p2['pnl'])
        pnl_base = max(abs(p2['pnl']), 1.0)
        pnl_pct = pnl_diff / pnl_base * 100
        print(f"💰 損益乖離: {pnl_diff:.2f} USD ({pnl_pct:.1f}%)")
        if pnl_diff <= 5.0:
            print("   ✅ 損益一致（許容範囲内: ±5 USD）")
        elif pnl_pct <= 5.0:
            print("   ✅ 損益ほぼ一致（±5%以内）")
        else:
            print("   ⚠️  損益に有意な乖離あり → 要調査")

    if 'trades' in p1 and 'trades' in p2:
        trade_diff = abs(p1['trades'] - p2['trades'])
        if trade_diff == 0:
            print(f"   ✅ トレード数一致: {p1['trades']} 件")
        else:
            print(f"   ⚠️  トレード数不一致: P1={p1['trades']} vs P2={p2['trades']} (差={trade_diff})")

    print("\n" + "=" * 60)

    # ログ保存
    log_path = os.path.join(WORKSPACE_ROOT, "logs", f"parity_check_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    with open(log_path, "w", encoding="utf-8") as f:
        f.write("=== パターン1 出力 ===\n")
        f.write(outputs.get(1, '(なし)'))
        f.write("\n=== パターン2 出力 ===\n")
        f.write(outputs.get(2, '(なし)'))
    print(f"📁 ログ保存: {log_path}")

if __name__ == "__main__":
    main()
