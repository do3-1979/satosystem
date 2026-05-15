#!/usr/bin/env python3
"""
ADXフィルター閾値スイープテスト

現在固定値のADX閾値（BTC:31 / XAUT:26）を複数の値でテストし、
四半期別・年別の損益への影響を検証する。

使用方法:
  python3 run_adx_sweep.py            # BTC + XAUT 両方を実行
  python3 run_adx_sweep.py --btc      # BTC のみ
  python3 run_adx_sweep.py --xaut     # XAUT のみ

結果:
  sweep_results/adx_sweep_YYYYMMDD_HHMMSS.json に保存
  コンソールにQ別比較表を出力
"""

import os
import sys
import json
import re
import subprocess
import argparse
from datetime import datetime

WORKSPACE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BTC_CONFIG_FILE  = os.path.join(WORKSPACE_ROOT, 'src', 'config.ini')
XAUT_CONFIG_FILE = os.path.join(WORKSPACE_ROOT, 'src', 'config_xaut.ini')
BTC_RESULTS_DIR  = os.path.join(WORKSPACE_ROOT, 'docs', 'quarterly_backtest_results', 'BTC')
XAUT_RESULTS_DIR = os.path.join(WORKSPACE_ROOT, 'docs', 'quarterly_backtest_results', 'XAUT')
SWEEP_RESULTS_DIR = os.path.join(WORKSPACE_ROOT, 'sweep_results')

os.makedirs(SWEEP_RESULTS_DIR, exist_ok=True)

# ============================================================
# スイープパターン定義
# ============================================================
# threshold=None  → enable_adx_filter=0（フィルタ完全無効）
# threshold=整数  → enable_adx_filter=1, adx_filter_threshold=値

BTC_SWEEP = [
    (None, "disabled"),   # ADXフィルタ完全無効
    (10,   "adx=10"),
    (15,   "adx=15"),
    (20,   "adx=20"),
    (25,   "adx=25"),
    (31,   "adx=31 ★BASELINE"),  # 現在のベースライン
]

XAUT_SWEEP = [
    (None, "disabled"),   # ADXフィルタ完全無効
    (12,   "adx=12"),
    (15,   "adx=15"),
    (18,   "adx=18"),
    (20,   "adx=20"),
    (22,   "adx=22"),
    (26,   "adx=26 ★BASELINE"),  # 現在のベースライン
]


# ============================================================
# config 操作
# ============================================================

def read_config(config_file):
    with open(config_file, 'r', encoding='utf-8') as f:
        return f.read()


def write_config(config_file, content):
    with open(config_file, 'w', encoding='utf-8') as f:
        f.write(content)


def set_adx_params(config_file, threshold):
    """
    config ファイルの ADX フィルター設定を変更する。
    threshold=None → enable_adx_filter=0（完全無効）
    threshold=整数 → enable_adx_filter=1 + adx_filter_threshold=値
    """
    content = read_config(config_file)

    if threshold is None:
        content = re.sub(
            r'^(enable_adx_filter\s*=\s*).*$',
            'enable_adx_filter = 0',
            content, flags=re.MULTILINE
        )
    else:
        content = re.sub(
            r'^(enable_adx_filter\s*=\s*).*$',
            'enable_adx_filter = 1',
            content, flags=re.MULTILINE
        )
        content = re.sub(
            r'^(adx_filter_threshold\s*=\s*).*$',
            f'adx_filter_threshold = {threshold}',
            content, flags=re.MULTILINE
        )

    write_config(config_file, content)


def restore_adx_params(config_file, original_threshold, original_enabled):
    """元の ADX 設定に戻す"""
    content = read_config(config_file)
    content = re.sub(
        r'^(enable_adx_filter\s*=\s*).*$',
        f'enable_adx_filter = {original_enabled}',
        content, flags=re.MULTILINE
    )
    content = re.sub(
        r'^(adx_filter_threshold\s*=\s*).*$',
        f'adx_filter_threshold = {original_threshold}',
        content, flags=re.MULTILINE
    )
    write_config(config_file, content)


def get_original_adx_params(config_file):
    """現在の ADX 設定値を読み込んで返す"""
    content = read_config(config_file)
    m_en = re.search(r'^enable_adx_filter\s*=\s*(\d+)', content, re.MULTILINE)
    m_th = re.search(r'^adx_filter_threshold\s*=\s*(\d+)', content, re.MULTILINE)
    enabled = int(m_en.group(1)) if m_en else 1
    threshold = int(m_th.group(1)) if m_th else 31
    return threshold, enabled


# ============================================================
# バックテスト実行
# ============================================================

def get_latest_result_file(results_dir):
    """最新のバックテスト結果 JSON を返す"""
    if not os.path.isdir(results_dir):
        return None
    files = [f for f in os.listdir(results_dir) if f.startswith('quarterly_results_') and f.endswith('.json')]
    if not files:
        return None
    return os.path.join(results_dir, max(files))


def run_backtest(config_name, results_dir):
    """
    run_quarterly_backtest.py をサブプロセスで実行し、結果 JSON のパスを返す。
    失敗時は None を返す。
    """
    cmd = [sys.executable, 'run_quarterly_backtest.py', '--config', config_name]
    result = subprocess.run(
        cmd,
        capture_output=True, text=True,
        timeout=600,
        cwd=WORKSPACE_ROOT
    )
    if result.returncode != 0:
        print(f"   ❌ バックテスト失敗:\n{result.stderr[-800:]}")
        return None
    return get_latest_result_file(results_dir)


# ============================================================
# 結果解析
# ============================================================

def extract_quarterly(result_file):
    """結果 JSON から Q 別データを抽出"""
    with open(result_file, encoding='utf-8') as f:
        data = json.load(f)
    quarterly = {}
    for q in data.get('quarterly', []):
        key = f"{q['year']}Q{q['quarter']}"
        quarterly[key] = {
            'pnl':    round(q['metrics']['total_pnl'], 2),
            'trades': q['metrics']['trades'],
        }
    annual = {}
    for yr, metrics in data.get('annual', {}).items():
        annual[yr] = {
            'pnl':    round(metrics.get('total_pnl', 0), 2),
            'trades': metrics.get('total_trades', 0),
        }
    total_pnl = sum(q['pnl'] for q in quarterly.values())
    total_trades = sum(q['trades'] for q in quarterly.values())
    return quarterly, annual, round(total_pnl, 2), total_trades


# ============================================================
# 表示
# ============================================================

DIVIDER = "=" * 110

def print_sweep_table(symbol, all_results, quarters, baseline_label):
    """Q別・累積損益の比較表を出力"""
    print()
    print(DIVIDER)
    print(f"  {symbol} ADX 閾値スイープ結果")
    print(DIVIDER)

    # ヘッダー
    q_width = 10
    header = f"{'設定':<24}"
    for q in quarters:
        header += f" {q:>{q_width}}"
    header += f" {'合計PnL':>10}  {'取引数':>6}"
    print(header)
    print("-" * 110)

    # ベースライン行を先に出して差分計算用に保存
    baseline_row = next((r for r in all_results if r['label'] == baseline_label), None)

    for r in all_results:
        is_base = (r['label'] == baseline_label)
        marker = "★" if is_base else " "
        row = f"{marker} {r['label']:<22}"
        for q in quarters:
            pnl = r['quarterly'].get(q, {}).get('pnl', None)
            if pnl is None:
                row += f" {'N/A':>{q_width}}"
            else:
                row += f" {pnl:>{q_width}.2f}"
        row += f" {r['total_pnl']:>10.2f}  {r['total_trades']:>6}"
        if is_base:
            row += "  ← BASELINE"
        elif baseline_row:
            diff = r['total_pnl'] - baseline_row['total_pnl']
            row += f"  ({diff:+.2f})"
        print(row)

    print("-" * 110)

    # 取引数テーブル
    print()
    print(f"  【取引数詳細】")
    th_row = f"{'設定':<24}"
    for q in quarters:
        th_row += f" {q:>{q_width}}"
    th_row += f" {'合計':>10}"
    print(th_row)
    print("-" * 80)
    for r in all_results:
        is_base = (r['label'] == baseline_label)
        marker = "★" if is_base else " "
        row = f"{marker} {r['label']:<22}"
        for q in quarters:
            trades = r['quarterly'].get(q, {}).get('trades', None)
            if trades is None:
                row += f" {'N/A':>{q_width}}"
            else:
                row += f" {trades:>{q_width}}"
        row += f" {r['total_trades']:>10}"
        print(row)
    print()


def print_final_summary(symbol, all_results, baseline_label):
    """最終サマリーを出力"""
    print(DIVIDER)
    print(f"  {symbol} 最終分析サマリー")
    print(DIVIDER)

    baseline = next((r for r in all_results if r['label'] == baseline_label), None)
    if not baseline:
        return

    sorted_results = sorted(all_results, key=lambda x: x['total_pnl'], reverse=True)

    print(f"  ベースライン ({baseline_label}): {baseline['total_pnl']:+.2f} USD / {baseline['total_trades']} trades")
    print()
    print(f"  ランキング (累積損益順):")
    for i, r in enumerate(sorted_results):
        diff = r['total_pnl'] - baseline['total_pnl']
        marker = "★" if r['label'] == baseline_label else f"  {i+1}"
        print(f"    {marker}. {r['label']:<26}  {r['total_pnl']:>9.2f} USD  ({diff:+.2f})  {r['total_trades']} trades")

    best = sorted_results[0]
    if best['label'] != baseline_label:
        diff = best['total_pnl'] - baseline['total_pnl']
        print()
        print(f"  → 最優秀: {best['label']}  ベースライン比 {diff:+.2f} USD ({diff/abs(baseline['total_pnl'])*100:+.1f}%)")
    else:
        print()
        print(f"  → 現ベースライン（{baseline_label}）が最優秀")
    print()


# ============================================================
# メイン
# ============================================================

def run_sweep(symbol, config_name, results_dir, sweep_params, baseline_label):
    """
    指定シンボルのADXスイープを実行する。
    戻り値: all_results リスト
    """
    config_file = BTC_CONFIG_FILE if symbol == 'BTC' else XAUT_CONFIG_FILE
    orig_threshold, orig_enabled = get_original_adx_params(config_file)

    print()
    print(DIVIDER)
    print(f"  {symbol} ADX スイープ開始  ({len(sweep_params)} パターン)")
    print(f"  元の設定: enable_adx_filter={orig_enabled}, adx_filter_threshold={orig_threshold}")
    print(DIVIDER)

    all_results = []

    try:
        for i, (threshold, label) in enumerate(sweep_params):
            th_str = "無効(全エントリー許可)" if threshold is None else str(threshold)
            print(f"\n[{symbol} {i+1}/{len(sweep_params)}] ADX={th_str}  ({label})")

            # config 変更
            set_adx_params(config_file, threshold)

            # バックテスト実行
            start = datetime.now()
            result_file = run_backtest(config_name, results_dir)
            elapsed = (datetime.now() - start).total_seconds()

            if not result_file:
                print(f"   ❌ スキップ")
                all_results.append({
                    'label': label, 'threshold': threshold,
                    'quarterly': {}, 'annual': {},
                    'total_pnl': 0, 'total_trades': 0,
                    'error': True,
                })
                continue

            quarterly, annual, total_pnl, total_trades = extract_quarterly(result_file)
            print(f"   ✅ {elapsed:.0f}秒  合計={total_pnl:+.2f} USD  {total_trades}trades")

            all_results.append({
                'label': label,
                'threshold': threshold,
                'quarterly': quarterly,
                'annual': annual,
                'total_pnl': total_pnl,
                'total_trades': total_trades,
                'elapsed_sec': round(elapsed, 1),
                'result_file': result_file,
            })

    finally:
        # 元の設定に必ず戻す
        restore_adx_params(config_file, orig_threshold, orig_enabled)
        print(f"\n🔄 {symbol} config を元の設定（threshold={orig_threshold}, enabled={orig_enabled}）に復元")

    return all_results


def main():
    parser = argparse.ArgumentParser(description='ADX閾値スイープテスト')
    parser.add_argument('--btc',  action='store_true', help='BTCのみ実行')
    parser.add_argument('--xaut', action='store_true', help='XAUTのみ実行')
    args = parser.parse_args()

    run_btc  = args.btc  or (not args.btc and not args.xaut)
    run_xaut = args.xaut or (not args.btc and not args.xaut)

    print(DIVIDER)
    print("  ADX フィルター閾値 スイープテスト")
    print(f"  実行: {'BTC' if run_btc else ''} {'XAUT' if run_xaut else ''}")
    print(f"  開始: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(DIVIDER)

    all_sweep_results = {}

    # ---- BTC ----
    if run_btc:
        btc_results = run_sweep(
            symbol='BTC',
            config_name='config.ini',
            results_dir=BTC_RESULTS_DIR,
            sweep_params=BTC_SWEEP,
            baseline_label='adx=31 ★BASELINE',
        )
        all_sweep_results['BTC'] = btc_results

        valid = [r for r in btc_results if not r.get('error')]
        if valid:
            quarters = sorted({q for r in valid for q in r['quarterly'].keys()})
            print_sweep_table('BTC', valid, quarters, 'adx=31 ★BASELINE')
            print_final_summary('BTC', valid, 'adx=31 ★BASELINE')

    # ---- XAUT ----
    if run_xaut:
        xaut_results = run_sweep(
            symbol='XAUT',
            config_name='config_xaut.ini',
            results_dir=XAUT_RESULTS_DIR,
            sweep_params=XAUT_SWEEP,
            baseline_label='adx=26 ★BASELINE',
        )
        all_sweep_results['XAUT'] = xaut_results

        valid = [r for r in xaut_results if not r.get('error')]
        if valid:
            quarters = sorted({q for r in valid for q in r['quarterly'].keys()})
            print_sweep_table('XAUT', valid, quarters, 'adx=26 ★BASELINE')
            print_final_summary('XAUT', valid, 'adx=26 ★BASELINE')

    # ---- JSON 保存 ----
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    out_path = os.path.join(SWEEP_RESULTS_DIR, f'adx_sweep_{ts}.json')
    save_data = {}
    for sym, results in all_sweep_results.items():
        save_data[sym] = [
            {k: v for k, v in r.items() if k != 'result_file'}
            for r in results
        ]
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump({'timestamp': ts, 'results': save_data}, f, ensure_ascii=False, indent=2)
    print(f"✅ スイープ結果を保存: {out_path}")
    print()


if __name__ == '__main__':
    main()
