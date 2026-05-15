#!/usr/bin/env python3
"""
ETH/USDT パラメータスイープ検証スクリプト (PDCA #1)

目的:
  BTC/USDTで得られたパラメータ最適値を起点に、ETH/USDTで同等以上の
  パフォーマンスが得られるか検証する。

設計方針（Task 31の失敗教訓を活かした改善）:
  - 過去失敗の原因: 605件スイープ → 過学習、BTC未最適化パラメータ適用
  - 改善策:
    1. BTC最適パラメータ(2402.94 USD)を起点とするベースライン計測
    2. 絞り込んだスイープ（20〜30件）で過学習を防止
    3. 多指標評価（Sharpe / MaxDD / Profit Factor / Calmar / 勝率）
    4. インサンプル(2024Q1-2025Q2) / アウトオブサンプル(2025Q3-Q4)検証

スイープ対象パラメータ（ETH特性に合わせた絞り込み）:
  - donchian_buy_term / donchian_sell_term: ETHのトレンド周期に合わせた調整
  - pvo_threshold: ETH出来高特性を反映

使用方法:
  python3 run_eth_sweep.py               # フルスイープ実行
  python3 run_eth_sweep.py --baseline    # ベースラインのみ計測
  python3 run_eth_sweep.py --resume N   # N件目から再開

ルール:
  - ホストPCのみで実行（ラズパイ本番に影響なし）
  - config.ini は変更後に必ず復元（try-finally）
  - Bybit API から ETH OHLCVデータを直接取得
"""

import os
import sys
import re
import json
import shutil
import subprocess
import glob
import argparse
import time
from datetime import datetime
from copy import deepcopy

# -------------------------------------------------------
# パス設定
# -------------------------------------------------------
WORKSPACE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR         = os.path.join(WORKSPACE_ROOT, 'src')
CONFIG_FILE     = os.path.join(SRC_DIR, 'config.ini')
CONFIG_BACKUP   = os.path.join(WORKSPACE_ROOT, 'sweep_results', 'config_btc_backup.ini')
SWEEP_RESULTS_DIR = os.path.join(WORKSPACE_ROOT, 'sweep_results')
ETH_RESULTS_DIR   = os.path.join(SWEEP_RESULTS_DIR, 'eth_sweep_results')

os.makedirs(SWEEP_RESULTS_DIR, exist_ok=True)
os.makedirs(ETH_RESULTS_DIR, exist_ok=True)

# -------------------------------------------------------
# ETH 固定設定（BTCから変更する項目）
# -------------------------------------------------------
ETH_BASE_CONFIG = {
    'market':                   'ETH/USDT',
    'lot_limit_lower':          '0.01',          # ETH最小取引単位 (BTC: 0.0001)
    'use_cached_data_for_hot_test': '0',          # Bybit APIから直接取得
    # バックテストモード確認（変更しない、back_test=1 を維持）
}

# -------------------------------------------------------
# スイープグリッド定義
# BTCとの特性差を考慮した調整対象:
#  1. donchian_buy_term / donchian_sell_term:
#     ETHはBTCより短期トレンドが多い → 20〜40期間でスイープ
#  2. pvo_threshold:
#     ETHの出来高バースト特性がBTCと異なる → 5〜20でスイープ
# -------------------------------------------------------
SWEEP_GRID = []
for dc in [20, 25, 30, 35, 40]:
    for pvo in [5, 10, 15, 20]:
        label = f"dc{dc}_pvo{pvo}"
        SWEEP_GRID.append({
            'label':              label,
            'donchian_buy_term':  str(dc),
            'donchian_sell_term': str(dc),     # buy/sellは連動させる
            'pvo_threshold':      str(pvo),
        })

# ベースライン（現BTC最適パラメータそのまま）
BASELINE_CASE = {
    'label':              'baseline_btc_params',
    'donchian_buy_term':  '30',
    'donchian_sell_term': '30',
    'pvo_threshold':      '10',
}

# バックテスト四半期（インサンプル: 2024Q1-2025Q2、アウトオブサンプル: 2025Q3-Q4）
INSAMPLE_QUARTERS = [
    (2024, 1), (2024, 2), (2024, 3), (2024, 4),
    (2025, 1), (2025, 2),
]
OOS_QUARTERS = [
    (2025, 3), (2025, 4),  # アウトオブサンプル（過学習検証用）
]
ALL_QUARTERS = INSAMPLE_QUARTERS + OOS_QUARTERS

QUARTER_STARTS = {
    1: "01/01", 2: "04/01", 3: "07/01", 4: "10/01",
}
QUARTER_ENDS = {
    1: "03/31 23:59", 2: "06/30 23:59", 3: "09/30 23:59", 4: "12/31 23:59",
}

# -------------------------------------------------------
# config.ini 操作ユーティリティ
# -------------------------------------------------------
def read_config():
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        return f.read()

def write_config(content):
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        f.write(content)

def backup_config():
    """現在のconfig.iniをバックアップ（ETH検証前に保存）"""
    shutil.copy2(CONFIG_FILE, CONFIG_BACKUP)

def restore_config():
    """バックアップからconfig.iniを復元"""
    if os.path.exists(CONFIG_BACKUP):
        shutil.copy2(CONFIG_BACKUP, CONFIG_FILE)
        print("✅ config.ini を BTC設定に復元しました")
    else:
        print("⚠️  バックアップが見つかりません。手動確認が必要です")

def set_config_value(content, key, value):
    """config.iniのキーを更新（正規表現で確実に置換）"""
    pattern = rf'^({re.escape(key)}\s*=\s*).*$'
    new_content = re.sub(pattern, f'{key} = {value}', content, flags=re.MULTILINE)
    return new_content

def set_period(content, year, q):
    """バックテスト期間を四半期単位で設定"""
    start = f"{year}/{QUARTER_STARTS[q].replace('/', '/')} 00:00"
    end   = f"{year}/{QUARTER_ENDS[q]}"
    content = set_config_value(content, 'start_time', f"{year}/{QUARTER_STARTS[q]} 00:00")
    content = set_config_value(content, 'end_time',   f"{year}/{QUARTER_ENDS[q]}")
    return content, f"{year}/{QUARTER_STARTS[q]} 00:00", f"{year}/{QUARTER_ENDS[q]}"

def apply_eth_config(donchian_buy_term, donchian_sell_term, pvo_threshold):
    """ETH用パラメータをconfig.iniに適用"""
    content = read_config()
    # ETH固定設定
    for key, val in ETH_BASE_CONFIG.items():
        content = set_config_value(content, key, val)
    # スイープパラメータ
    content = set_config_value(content, 'donchian_buy_term',  donchian_buy_term)
    content = set_config_value(content, 'donchian_sell_term', donchian_sell_term)
    content = set_config_value(content, 'pvo_threshold',      pvo_threshold)
    write_config(content)

# -------------------------------------------------------
# バックテスト実行
# -------------------------------------------------------
def run_one_quarter(year, q):
    """1四半期のバックテストを実行して metrics を返す"""
    content = read_config()
    content, start_str, end_str = set_period(content, year, q)
    write_config(content)

    env = os.environ.copy()
    env['QUARTERLY_LOG_PREFIX'] = f"ETH_Q{q}_{year}"

    prev_dir = os.getcwd()
    try:
        os.chdir(SRC_DIR)
        result = subprocess.run(
            ['python', 'bot.py'],
            capture_output=True,
            text=True,
            timeout=600,
            env=env,
        )
    finally:
        os.chdir(prev_dir)

    if result.returncode != 0:
        return None

    # backtest_summary_*.json から結果取得
    summary_logs = glob.glob(os.path.join(SRC_DIR, 'logs', 'backtest_summary_*.json'))
    if not summary_logs:
        return None
    latest = max(summary_logs, key=os.path.getmtime)
    try:
        with open(latest, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return None

def run_all_quarters(case_params, quarters, label):
    """指定した全四半期のバックテストを実行して結果リストを返す"""
    apply_eth_config(
        case_params['donchian_buy_term'],
        case_params['donchian_sell_term'],
        case_params['pvo_threshold'],
    )
    results = []
    for (year, q) in quarters:
        metrics = run_one_quarter(year, q)
        results.append({
            'year': year, 'quarter': q,
            'metrics': metrics
        })
    return results

# -------------------------------------------------------
# 多指標スコアリング
# -------------------------------------------------------
def compute_composite_score(quarterly_results):
    """
    多指標総合スコアを計算。
    指標:
      - total_pnl       : 高いほど良い（重み40%）
      - sharpe          : 高いほど良い（重み25%）
      - max_drawdown_rate: 低いほど良い（重み20%）
      - profit_factor   : 高いほど良い（重み10%）
      - win_rate        : 高いほど良い（重み5%）
    """
    valid = [r for r in quarterly_results if r.get('metrics')]
    if not valid:
        return None, {}

    total_pnl   = sum(r['metrics'].get('total_pnl', 0)         for r in valid)
    sharpe_avg  = sum(r['metrics'].get('sharpe', 0)             for r in valid) / len(valid)
    maxdd_avg   = sum(r['metrics'].get('max_drawdown_rate', 999) for r in valid) / len(valid)
    pf_avg      = sum(r['metrics'].get('profit_factor', 0)      for r in valid) / len(valid)
    winrate_avg = sum(r['metrics'].get('win_rate', 0)           for r in valid) / len(valid)
    total_trades = sum(r['metrics'].get('trades', 0)            for r in valid)

    # Calmar比（年間リターン / 最大DD）
    quarters_covered = len(valid)
    annualized_pnl = total_pnl * (8 / quarters_covered) if quarters_covered else 0
    calmar = annualized_pnl / maxdd_avg if maxdd_avg > 0 else 0

    summary = {
        'total_pnl':       round(total_pnl, 2),
        'sharpe_avg':      round(sharpe_avg, 4),
        'maxdd_avg_pct':   round(maxdd_avg, 2),
        'pf_avg':          round(pf_avg, 4),
        'winrate_avg_pct': round(winrate_avg, 2),
        'calmar':          round(calmar, 4),
        'total_trades':    total_trades,
        'valid_quarters':  len(valid),
    }
    return summary, summary  # (score_dict, display_dict)

# -------------------------------------------------------
# 進捗表示
# -------------------------------------------------------
def fmt_seconds(sec):
    m, s = divmod(int(sec), 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h}h{m:02d}m{s:02d}s"
    elif m > 0:
        return f"{m}m{s:02d}s"
    return f"{s}s"

# -------------------------------------------------------
# 結果保存と表示
# -------------------------------------------------------
def save_sweep_results(all_results, filename_prefix="eth_sweep"):
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    out = os.path.join(ETH_RESULTS_DIR, f"{filename_prefix}_{ts}.json")
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    print(f"\n💾 結果保存: {out}")
    return out

def print_ranking(results_list, title="ETH パラメータ評価ランキング"):
    """多指標ランキングを表示"""
    valid = [r for r in results_list if r.get('summary')]
    if not valid:
        print("⚠️  有効な結果がありません")
        return

    # composite score（正規化後の重み付き合計）で並び替え
    # PnL: 40%, Sharpe: 25%, MaxDD(反転): 20%, PF: 10%, WinRate: 5%
    def score(r):
        s = r['summary']
        pnl_score   = s.get('total_pnl', -9999)
        sharpe      = s.get('sharpe_avg', 0) * 100
        maxdd_inv   = max(0, 200 - s.get('maxdd_avg_pct', 200))
        pf_score    = min(s.get('pf_avg', 0), 3.0) * 100
        wr_score    = s.get('winrate_avg_pct', 0)
        return (pnl_score * 0.40) + (sharpe * 0.25) + (maxdd_inv * 0.20) + \
               (pf_score * 0.10) + (wr_score * 0.05)

    ranked = sorted(valid, key=score, reverse=True)

    print(f"\n{'='*90}")
    print(f"  {title}")
    print(f"  インサンプル期間: 2024Q1-2025Q2 (6四半期)")
    print(f"{'='*90}")
    print(f"  {'Rank':<5} {'Label':<25} {'PnL(USD)':>10} {'Sharpe':>8} "
          f"{'MaxDD%':>8} {'PF':>6} {'WR%':>6} {'Trades':>7} {'Calmar':>8}")
    print(f"  {'-'*85}")

    for i, r in enumerate(ranked[:10]):
        s = r['summary']
        print(f"  {i+1:<5} {r['label']:<25} "
              f"{s.get('total_pnl', 0):>10.2f} "
              f"{s.get('sharpe_avg', 0):>8.4f} "
              f"{s.get('maxdd_avg_pct', 0):>8.2f} "
              f"{s.get('pf_avg', 0):>6.4f} "
              f"{s.get('winrate_avg_pct', 0):>6.2f} "
              f"{s.get('total_trades', 0):>7} "
              f"{s.get('calmar', 0):>8.4f}")

    print(f"  {'-'*85}")
    best = ranked[0]
    bq = best.get('quarters_results', [])
    print(f"\n  🏆 ベスト候補: {best['label']}")
    print(f"     DC期間: {best.get('params', {}).get('donchian_buy_term', '?')}")
    print(f"     PVO閾値: {best.get('params', {}).get('pvo_threshold', '?')}")
    print(f"     累積損益: {best['summary'].get('total_pnl', 0):.2f} USD")
    print(f"     Sharpe: {best['summary'].get('sharpe_avg', 0):.4f}")
    print(f"     MaxDD平均: {best['summary'].get('maxdd_avg_pct', 0):.2f}%")
    print(f"     Calmar: {best['summary'].get('calmar', 0):.4f}")
    print(f"{'='*90}\n")
    return ranked[0] if ranked else None

def print_oos_report(oos_result, baseline_oos=None):
    """アウトオブサンプル検証レポートを表示"""
    print(f"\n{'='*70}")
    print(f"  📊 アウトオブサンプル検証（2025Q3-Q4）")
    print(f"{'='*70}")
    if oos_result and oos_result.get('summary'):
        s = oos_result['summary']
        print(f"  ベスト候補 ({oos_result['label']}):")
        print(f"    PnL: {s.get('total_pnl', 0):.2f} USD")
        print(f"    Sharpe: {s.get('sharpe_avg', 0):.4f}")
        print(f"    MaxDD: {s.get('maxdd_avg_pct', 0):.2f}%")
        print(f"    Calmar: {s.get('calmar', 0):.4f}")
    if baseline_oos and baseline_oos.get('summary'):
        s = baseline_oos['summary']
        print(f"  ベースライン (BTCパラメータそのまま):")
        print(f"    PnL: {s.get('total_pnl', 0):.2f} USD")
        print(f"    Sharpe: {s.get('sharpe_avg', 0):.4f}")
        print(f"    MaxDD: {s.get('maxdd_avg_pct', 0):.2f}%")
    print(f"{'='*70}")

# -------------------------------------------------------
# メイン実行
# -------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description='ETH/USDT パラメータスイープ検証')
    parser.add_argument('--baseline', action='store_true',
                        help='ベースラインのみ計測（スイープなし）')
    parser.add_argument('--resume', type=int, default=0,
                        help='N件目から再開（障害復旧用）')
    args = parser.parse_args()

    print("=" * 70)
    print("  ETH/USDT パラメータスイープ検証スクリプト")
    print(f"  開始日時: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    print()
    print("📋 批判的改善点（Task 31の失敗から学習）:")
    print("  - 前回: BTC=904USD時点のパラメータ + 605件スイープ → 過学習")
    print("  - 今回: BTC=2402.94USD最適パラメータ起点 + 20件絞り込み")
    print("  - 評価: PnL + Sharpe + MaxDD + PF + Calmar 多指標スコアリング")
    print("  - 検証: インサンプル(2024Q1-2025Q2) + OOS(2025Q3-Q4)の2段階")
    print()
    print("⚙️  ETH固定設定:")
    print(f"  market = ETH/USDT")
    print(f"  lot_limit_lower = 0.01 (BTC: 0.0001 → ETH: 0.01)")
    print(f"  use_cached_data_for_hot_test = 0 (Bybit APIから直接取得)")
    print()

    # バックアップ
    backup_config()
    print(f"📦 BTC設定をバックアップ: {CONFIG_BACKUP}")
    print()

    all_sweep_results = []

    try:
        # =================================================
        # Phase 0: ベースライン計測
        # =================================================
        print("=" * 70)
        print("  Phase 0: BTCパラメータそのままでETHベースライン計測")
        print("  (2024Q1-2025Q4 全8四半期)")
        print("=" * 70)

        phase0_start = time.time()
        baseline_is_results = run_all_quarters(BASELINE_CASE, INSAMPLE_QUARTERS,
                                               BASELINE_CASE['label'])
        baseline_oos_results = run_all_quarters(BASELINE_CASE, OOS_QUARTERS,
                                                BASELINE_CASE['label'])
        phase0_elapsed = time.time() - phase0_start

        baseline_is_summary, _ = compute_composite_score(baseline_is_results)
        baseline_oos_summary, _ = compute_composite_score(baseline_oos_results)

        baseline_all = {
            'label':           BASELINE_CASE['label'],
            'params':          BASELINE_CASE,
            'insample_results': baseline_is_results,
            'oos_results':     baseline_oos_results,
            'summary':         baseline_is_summary,
            'oos_summary':     baseline_oos_summary,
        }
        all_sweep_results.append(baseline_all)

        print(f"\n📊 ETHベースライン（BTCパラメータ適用）:")
        if baseline_is_summary:
            print(f"  インサンプルPnL: {baseline_is_summary.get('total_pnl', 0):.2f} USD")
            print(f"  Sharpe: {baseline_is_summary.get('sharpe_avg', 0):.4f}")
            print(f"  MaxDD avg: {baseline_is_summary.get('maxdd_avg_pct', 0):.2f}%")
            print(f"  OOS PnL: {(baseline_oos_summary or {}).get('total_pnl', 'N/A')}")
        print(f"  ⏱  所要時間: {fmt_seconds(phase0_elapsed)}")

        if args.baseline:
            save_sweep_results({'baseline': baseline_all}, 'eth_baseline')
            print("\n✅ --baseline モード: ベースライン計測完了")
            return

        # =================================================
        # Phase 1: パラメータスイープ（インサンプル最適化）
        # =================================================
        print()
        print("=" * 70)
        print(f"  Phase 1: パラメータスイープ ({len(SWEEP_GRID)} 件 × 6四半期)")
        print(f"  インサンプル期間: 2024Q1〜2025Q2")
        print("=" * 70)

        total_cases = len(SWEEP_GRID)
        start_idx = args.resume
        sweep_start = time.time()
        case_elapsed_list = []

        for i, case in enumerate(SWEEP_GRID):
            if i < start_idx:
                print(f"  スキップ: [{i+1}/{total_cases}] {case['label']}")
                continue

            case_start = time.time()

            # 進捗表示
            done = i - start_idx
            elapsed = time.time() - sweep_start
            if done > 0 and case_elapsed_list:
                avg_per_case = sum(case_elapsed_list) / len(case_elapsed_list)
                remaining = avg_per_case * (total_cases - i)
                eta_str = fmt_seconds(remaining)
            else:
                eta_str = "計算中..."

            pct = (i + 1) / total_cases * 100
            print(f"\n  [{i+1}/{total_cases}] {pct:5.1f}%  {case['label']}")
            print(f"  経過: {fmt_seconds(elapsed)}  残り推定: {eta_str}")
            print(f"  パラメータ: dc={case['donchian_buy_term']}, pvo={case['pvo_threshold']}")

            # インサンプル実行
            is_results = run_all_quarters(case, INSAMPLE_QUARTERS, case['label'])
            is_summary, _ = compute_composite_score(is_results)

            case_elapsed = time.time() - case_start
            case_elapsed_list.append(case_elapsed)

            result_entry = {
                'label':           case['label'],
                'params':          case,
                'insample_results': is_results,
                'summary':         is_summary,
                'quarters_results': is_results,
            }
            all_sweep_results.append(result_entry)

            # 暫定状況表示
            if is_summary:
                print(f"  → PnL: {is_summary.get('total_pnl', 0):+.2f} USD  "
                      f"Sharpe: {is_summary.get('sharpe_avg', 0):.4f}  "
                      f"MaxDD: {is_summary.get('maxdd_avg_pct', 0):.1f}%  "
                      f"Calmar: {is_summary.get('calmar', 0):.4f}")
            else:
                print(f"  → 全四半期失敗 (Bybit API不通の可能性)")

            # 途中保存（5件ごと）
            if (i + 1) % 5 == 0:
                save_sweep_results(all_sweep_results, 'eth_sweep_progress')
                print(f"  💾 途中保存完了 ({i+1}/{total_cases}件)")

        total_sweep_time = time.time() - sweep_start
        print(f"\n✅ Phase 1 完了: {fmt_seconds(total_sweep_time)}")

        # =================================================
        # Phase 2: 上位3候補をアウトオブサンプルで検証
        # =================================================
        print()
        print("=" * 70)
        print("  Phase 2: 上位候補アウトオブサンプル検証 (2025Q3-Q4)")
        print("=" * 70)

        # ランキングで上位3件を選出
        valid_results = [r for r in all_sweep_results
                        if r.get('summary') and r['label'] != BASELINE_CASE['label']]

        def composite_score(r):
            s = r['summary']
            pnl_score   = s.get('total_pnl', -9999)
            sharpe      = s.get('sharpe_avg', 0) * 100
            maxdd_inv   = max(0, 200 - s.get('maxdd_avg_pct', 200))
            pf_score    = min(s.get('pf_avg', 0), 3.0) * 100
            wr_score    = s.get('winrate_avg_pct', 0)
            return (pnl_score * 0.40) + (sharpe * 0.25) + (maxdd_inv * 0.20) + \
                   (pf_score * 0.10) + (wr_score * 0.05)

        top3 = sorted(valid_results, key=composite_score, reverse=True)[:3]

        for j, candidate in enumerate(top3):
            print(f"\n  [{j+1}/3] OOS検証: {candidate['label']}")
            oos_results = run_all_quarters(candidate['params'], OOS_QUARTERS,
                                           candidate['label'])
            oos_summary, _ = compute_composite_score(oos_results)
            candidate['oos_results']  = oos_results
            candidate['oos_summary']  = oos_summary
            if oos_summary:
                print(f"  OOS PnL: {oos_summary.get('total_pnl', 0):+.2f} USD  "
                      f"Sharpe: {oos_summary.get('sharpe_avg', 0):.4f}  "
                      f"MaxDD: {oos_summary.get('maxdd_avg_pct', 0):.2f}%")

        # =================================================
        # 最終レポート
        # =================================================
        best = print_ranking(all_sweep_results, "ETH パラメータ評価ランキング（インサンプル）")
        print_oos_report(best, baseline_all)

        # BTC比較
        btc_pnl = 2402.94  # BTC 8四半期ベースライン
        btc_is_pnl = btc_pnl * (6 / 8)  # 同等のインサンプル期間換算
        print(f"\n{'='*70}")
        print(f"  📈 BTC vs ETH 最終比較")
        print(f"{'='*70}")
        print(f"  BTC/USDT (2024Q1-2025Q4 8Q累積): {btc_pnl:.2f} USD  ← 現行ベースライン")
        if best and best.get('summary'):
            eth_pnl = best['summary'].get('total_pnl', 0)
            eth_is_annualized = eth_pnl / 6 * 8
            print(f"  ETH/USDT ベスト ({best['label']}):")
            print(f"    インサンプル (6Q累積): {eth_pnl:.2f} USD")
            print(f"    換算8Q推定:          {eth_is_annualized:.2f} USD")
            if eth_is_annualized > btc_pnl:
                print(f"  🎉 判定: ETH採用検討圏内！ (+{eth_is_annualized - btc_pnl:.2f} USD)")
            else:
                print(f"  ℹ️  判定: BTC優位 ({btc_pnl - eth_is_annualized:.2f} USD 差)")
        print(f"{'='*70}")

        # 全結果を保存
        final_out = save_sweep_results(all_sweep_results, 'eth_sweep_final')
        print(f"\n🎯 PDCA #1 完了。結果: {final_out}")
        print("次のアクション:")
        if best and best.get('oos_summary'):
            oos_pnl = best['oos_summary'].get('total_pnl', 0)
            if oos_pnl > 0:
                print(f"  → OOS利益確認({oos_pnl:.2f} USD)。PDCA #2でentry_range/stop_range微調整を推奨")
            else:
                print(f"  → OOS損失({oos_pnl:.2f} USD)。ETH採用には戦略的改善が必要。")
                print(f"     選択肢: 1) ETH不採用・BTCに特化  2) Donchian期間をさらに調整")

    finally:
        # 必ずBTC設定に戻す
        restore_config()
        print(f"\n🔒 config.ini をBTC設定に戻しました（ラズパイ本番に影響なし）")


if __name__ == '__main__':
    main()
