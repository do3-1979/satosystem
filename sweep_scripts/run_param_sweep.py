#!/usr/bin/env python3
"""
パラメータスイープテストスクリプト

指定したパラメータ組み合わせで全8四半期バックテストを実行し、
各評価指標の改善効果を比較する。

対象パラメータ:
  - psar_lookback_term: PSAR初期化期間（OHLCVウィンドウに影響）
  - tsmom_filter_lookback: TSMOMフィルター計算期間

使用方法:
  python3 run_param_sweep.py

結果:
  sweep_results/ ディレクトリにJSON形式で保存
  コンソールに比較表を出力
"""
import os
import sys
import json
import re
import subprocess
from datetime import datetime
from copy import deepcopy

# ワークスペースのルートディレクトリ
WORKSPACE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_FILE = os.path.join(WORKSPACE_ROOT, 'src', 'config.ini')
RESULTS_DIR = os.path.join(WORKSPACE_ROOT, 'docs', 'quarterly_backtest_results')
SWEEP_RESULTS_DIR = os.path.join(WORKSPACE_ROOT, 'sweep_results')

os.makedirs(SWEEP_RESULTS_DIR, exist_ok=True)

# ============================================================
# スイープパラメータ定義
# ============================================================

# 2次元グリッドサーチ: psar_lookback_term × tsmom_filter_lookback
PARAM_GRID = [
    # (psar_lookback_term, tsmom_filter_lookback, label)
    (200, 200, "psar200_tsmom200"),
    (300, 150, "psar300_tsmom150"),
    (300, 200, "psar300_tsmom200"),   # ← 現在のベースライン
    (300, 250, "psar300_tsmom250"),
    (300, 300, "psar300_tsmom300"),
    (400, 200, "psar400_tsmom200"),
    (400, 250, "psar400_tsmom250"),
]


def read_config():
    """config.ini を読み込んで文字列として返す"""
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        return f.read()


def write_config(content):
    """config.ini に書き込む"""
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        f.write(content)


def update_sweep_params(psar_lookback, tsmom_lookback):
    """スイープ対象パラメータを config.ini に反映"""
    content = read_config()
    
    # psar_lookback_term を更新
    content = re.sub(
        r'^(psar_lookback_term\s*=\s*).*$',
        f'psar_lookback_term = {psar_lookback}',
        content, flags=re.MULTILINE
    )
    # tsmom_filter_lookback を更新
    content = re.sub(
        r'^(tsmom_filter_lookback\s*=\s*).*$',
        f'tsmom_filter_lookback = {tsmom_lookback}',
        content, flags=re.MULTILINE
    )
    # tsmom_filter_enabled = 1 を確認・強制設定
    content = re.sub(
        r'^(tsmom_filter_enabled\s*=\s*).*$',
        'tsmom_filter_enabled = 1',
        content, flags=re.MULTILINE
    )
    
    write_config(content)


def restore_baseline_params():
    """実行後にベースラインパラメータを復元（psar=300, tsmom=200）"""
    update_sweep_params(300, 200)


def get_latest_result_file():
    """最新のバックテスト結果JSONを取得"""
    files = [f for f in os.listdir(RESULTS_DIR) if f.startswith('quarterly_results_')]
    if not files:
        return None
    latest = max(files)
    return os.path.join(RESULTS_DIR, latest)


def run_quarterly_backtest_subprocess():
    """run_quarterly_backtest.py をサブプロセスで実行し、結果JSONパスを返す"""
    result = subprocess.run(
        [sys.executable, 'run_quarterly_backtest.py'],
        capture_output=True, text=True,
        timeout=900,
        cwd=WORKSPACE_ROOT
    )
    if result.returncode != 0:
        print(f"   ❌ バックテスト失敗:\n{result.stderr[-500:]}")
        return None
    
    # 最新ファイルを返す
    return get_latest_result_file()


def compute_composite_score(ann_2024, ann_2025):
    """
    複合スコアを計算（各指標を正規化して加重平均）
    
    重み付け:
    - 総損益: 30%
    - Sortino: 25% （下方リスク調整済みリターン）
    - Recovery Factor: 20% （回復力）
    - 最大DD率（逆数）: 15% （ドローダウン抑制）
    - Expectancy: 10% （1取引当たり期待値）
    """
    if not ann_2024 or not ann_2025:
        return 0.0
    
    # 2024 + 2025 合計
    total_pnl = ann_2024.get('total_pnl', 0) + ann_2025.get('total_pnl', 0)
    sortino = (ann_2024.get('sortino_avg', 0) + ann_2025.get('sortino_avg', 0)) / 2
    recovery = (ann_2024.get('recovery_factor', 0) + ann_2025.get('recovery_factor', 0)) / 2
    max_dd = max(ann_2024.get('max_drawdown_rate', 100), ann_2025.get('max_drawdown_rate', 100))
    expectancy = (ann_2024.get('expectancy_avg', 0) + ann_2025.get('expectancy_avg', 0)) / 2
    
    # 正規化スコア（スケーリング）
    pnl_score = total_pnl / 2157.10  # ベースライン比
    sortino_score = max(0, sortino) / 0.5  # 0.5 以上で 1.0
    recovery_score = min(recovery, 10.0) / 10.0  # 10以上で 1.0
    dd_score = max(0, 1.0 - max_dd / 100.0)  # DDが低いほど高スコア
    exp_score = max(0, expectancy) / 100.0  # 100 USD/取引で 1.0
    
    composite = (
        0.30 * pnl_score +
        0.25 * sortino_score +
        0.20 * recovery_score +
        0.15 * dd_score +
        0.10 * exp_score
    )
    return round(composite, 4)


def print_sweep_summary(all_results):
    """スイープ結果の比較表を出力"""
    print("\n" + "=" * 130)
    print("📊 パラメータスイープ結果比較")
    print("=" * 130)
    
    baseline_label = "psar300_tsmom200"
    
    # ヘッダー
    print(f"\n{'設定':<22} {'累積損益':>10} {'Sortino':>8} {'Recov.':>8} {'MaxDD%':>8} {'Expectancy':>12} {'Composite':>10} {'備考'}")
    print("-" * 130)
    
    sorted_results = sorted(all_results, key=lambda x: x.get('composite_score', 0), reverse=True)
    
    for r in sorted_results:
        label = r['label']
        note = " ← BASELINE" if label == baseline_label else ""
        rank_marker = "🏆" if r == sorted_results[0] else "  "
        
        ann_all = r.get('annual_combined', {})
        
        print(f"{rank_marker} {label:<20} {ann_all.get('total_pnl', 0):>10.2f} {ann_all.get('sortino_avg', 0):>8.3f} "
              f"{ann_all.get('recovery_factor', 0):>8.3f} {ann_all.get('max_drawdown_rate', 0):>7.2f}% "
              f"{ann_all.get('expectancy_avg', 0):>12.2f} {r.get('composite_score', 0):>10.4f}{note}")
    
    print("-" * 130)
    
    # 年別詳細
    print(f"\n{'設定':<22} | {'2024: PnL':>11} {'Sortino':>8} {'RecovF':>8} | {'2025: PnL':>11} {'Sortino':>8} {'RecovF':>8} | Composite")
    print("-" * 130)
    for r in sorted_results:
        label = r['label']
        a24 = r.get('annual', {}).get('2024', {})
        a25 = r.get('annual', {}).get('2025', {})
        marker = "🏆 " if r == sorted_results[0] else "   "
        print(f"{marker}{label:<20} | "
              f"{a24.get('total_pnl', 0):>11.2f} {a24.get('sortino_avg', 0):>8.3f} {a24.get('recovery_factor', 0):>8.3f} | "
              f"{a25.get('total_pnl', 0):>11.2f} {a25.get('sortino_avg', 0):>8.3f} {a25.get('recovery_factor', 0):>8.3f} | "
              f"{r.get('composite_score', 0):.4f}")
    
    print()
    
    # 最良の設定
    best = sorted_results[0]
    print(f"🏆 最優秀設定: {best['label']}")
    print(f"   psar_lookback_term = {best['psar_lookback']}")
    print(f"   tsmom_filter_lookback = {best['tsmom_lookback']}")
    print(f"   Composite Score: {best['composite_score']:.4f}")
    print(f"   累積損益: {best.get('annual_combined', {}).get('total_pnl', 0):.2f} USD")
    
    return sorted_results[0]


def combine_annual(ann_2024, ann_2025):
    """2024 + 2025 の年間合計/平均メトリクスを計算"""
    if not ann_2024 and not ann_2025:
        return {}
    a24 = ann_2024 or {}
    a25 = ann_2025 or {}
    
    total_pnl = a24.get('total_pnl', 0) + a25.get('total_pnl', 0)
    total_trades = a24.get('total_trades', 0) + a25.get('total_trades', 0)
    
    w24 = a24.get('total_trades', 0)
    w25 = a25.get('total_trades', 0)
    total_w = w24 + w25
    
    def wavg(key):
        v24 = a24.get(key, 0)
        v25 = a25.get(key, 0)
        return (v24 * w24 + v25 * w25) / total_w if total_w > 0 else 0.0
    
    max_dd = max(a24.get('max_drawdown_rate', 0), a25.get('max_drawdown_rate', 0))
    max_dd_usd = max(a24.get('max_drawdown', 0), a25.get('max_drawdown', 0))
    
    return {
        'total_pnl': round(total_pnl, 3),
        'total_trades': total_trades,
        'win_rate': round(wavg('win_rate'), 2),
        'sharpe_avg': round(wavg('sharpe_avg'), 3),
        'sortino_avg': round(wavg('sortino_avg'), 3),
        'payoff_ratio_avg': round(wavg('payoff_ratio_avg'), 3),
        'expectancy_avg': round(wavg('expectancy_avg'), 3),
        'recovery_factor': round(total_pnl / max_dd_usd if max_dd_usd > 0 else 0, 3),
        'max_drawdown_rate': round(max_dd, 3),
        'max_consec_losses': max(a24.get('max_consec_losses', 0), a25.get('max_consec_losses', 0)),
    }


def main():
    print("=" * 80)
    print("🔬 パラメータスイープテスト開始")
    print("=" * 80)
    print(f"  パラメータ組み合わせ数: {len(PARAM_GRID)}")
    print(f"  推定実行時間: 約 {len(PARAM_GRID) * 10} 分")
    print()
    
    # 現在の config.ini を保存
    original_config = read_config()
    
    all_results = []
    
    try:
        for i, (psar_lb, tsmom_lb, label) in enumerate(PARAM_GRID):
            print(f"\n[{i+1}/{len(PARAM_GRID)}] 🧪 {label}  (psar={psar_lb}, tsmom={tsmom_lb})")
            print("-" * 60)
            
            # パラメータを config.ini に反映
            update_sweep_params(psar_lb, tsmom_lb)
            
            # バックテスト実行
            start_ts = datetime.now()
            result_file = run_quarterly_backtest_subprocess()
            elapsed = (datetime.now() - start_ts).total_seconds()
            
            if not result_file or not os.path.exists(result_file):
                print(f"   ❌ バックテスト失敗: 結果ファイルが見つかりません")
                all_results.append({
                    'label': label,
                    'psar_lookback': psar_lb,
                    'tsmom_lookback': tsmom_lb,
                    'error': 'backtest failed',
                    'composite_score': -1,
                })
                continue
            
            with open(result_file) as f:
                data = json.load(f)
            
            quarterly = data.get('quarterly', [])
            annual = data.get('annual', {})
            
            ann_2024 = annual.get('2024', {})
            ann_2025 = annual.get('2025', {})
            ann_combined = combine_annual(ann_2024, ann_2025)
            composite = compute_composite_score(ann_2024, ann_2025)
            
            result_entry = {
                'label': label,
                'psar_lookback': psar_lb,
                'tsmom_lookback': tsmom_lb,
                'elapsed_sec': round(elapsed, 1),
                'quarterly': quarterly,
                'annual': annual,
                'annual_combined': ann_combined,
                'composite_score': composite,
                'result_file': result_file,
            }
            all_results.append(result_entry)
            
            print(f"   ✅ 完了 ({elapsed:.0f}秒)  累積損益: {ann_combined.get('total_pnl', 0):.2f} USD  "
                  f"Sortino: {ann_combined.get('sortino_avg', 0):.3f}  Composite: {composite:.4f}")
    
    finally:
        # 元の config.ini を復元（ベースラインを保持）
        restore_baseline_params()
        print(f"\n🔄 config.ini をベースライン（psar=300, tsmom=200）に復元")
    
    if not all_results:
        print("❌ 有効な結果がありません")
        return
    
    # 比較表を表示
    best = print_sweep_summary(all_results)
    
    # 結果を JSON 保存
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    sweep_out = os.path.join(SWEEP_RESULTS_DIR, f'sweep_results_{ts}.json')
    with open(sweep_out, 'w', encoding='utf-8') as f:
        # quarterly は大きいので省略オプション
        save_data = [
            {k: v for k, v in r.items() if k != 'quarterly'}
            for r in all_results
        ]
        json.dump({'timestamp': ts, 'param_grid': PARAM_GRID, 'results': save_data}, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ スイープ結果を保存: {sweep_out}")
    
    # ベースライン比較
    baseline = next((r for r in all_results if r['label'] == 'psar300_tsmom200'), None)
    if baseline and best['label'] != 'psar300_tsmom200':
        improvement = best.get('annual_combined', {}).get('total_pnl', 0) - baseline.get('annual_combined', {}).get('total_pnl', 0)
        print(f"\n📈 改善提案:")
        print(f"   ベースライン ({baseline['label']}): {baseline.get('annual_combined', {}).get('total_pnl', 0):.2f} USD")
        print(f"   最優秀設定  ({best['label']}): {best.get('annual_combined', {}).get('total_pnl', 0):.2f} USD")
        print(f"   差分: {improvement:+.2f} USD  Composite改善: {best['composite_score'] - baseline['composite_score']:+.4f}")
        print(f"\n   採用する場合の config.ini 変更:")
        print(f"     psar_lookback_term = {best['psar_lookback']}")
        print(f"     tsmom_filter_lookback = {best['tsmom_lookback']}")
    else:
        print(f"\n✅ 現在のベースライン（psar=300, tsmom=200）が最優秀です")
    
    return all_results, best


if __name__ == '__main__':
    main()
