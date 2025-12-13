#!/usr/bin/env python3
"""Strategy A (ADX) パラメータスイープ
run_quarterly_backtest.py を使って、複数の ADX 設定で結果を計測し、
Baseline（指標OFF）との比較を出力する。
"""

import os
import subprocess
import json
import glob
import shutil
from datetime import datetime
from configparser import ConfigParser

WORKSPACE_ROOT = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(WORKSPACE_ROOT, "src")
CONFIG_FILE = os.path.join(SRC_DIR, "config.ini")
RESULTS_DIR = os.path.join(WORKSPACE_ROOT, "docs/quarterly_backtest_results")
REPORT_FILE = os.path.join(RESULTS_DIR, "phase22_adx_sweep_report.json")
BACKUP_FILE = CONFIG_FILE + ".backup_phase22_adx_sweep"

COMBOS = [
    {
        "label": "FastTrend",
        "adx_term": 12,
        "adx_continue": 2,
        "adx_bull_threshold": 22,
        "adx_bear_threshold": 17
    },
    {
        "label": "FastContinue3",
        "adx_term": 12,
        "adx_continue": 3,
        "adx_bull_threshold": 22,
        "adx_bear_threshold": 17
    },
    {
        "label": "FastTerm14",
        "adx_term": 14,
        "adx_continue": 2,
        "adx_bull_threshold": 22,
        "adx_bear_threshold": 17
    },
    {
        "label": "FastThreshold24",
        "adx_term": 12,
        "adx_continue": 2,
        "adx_bull_threshold": 24,
        "adx_bear_threshold": 19
    },
    {
        "label": "FastSwayMix",
        "adx_term": 14,
        "adx_continue": 3,
        "adx_bull_threshold": 24,
        "adx_bear_threshold": 18
    }
]


def backup_config():
    if not os.path.exists(BACKUP_FILE):
        shutil.copy(CONFIG_FILE, BACKUP_FILE)
        print(f"✓ config.ini をバックアップ: {BACKUP_FILE}")
    return BACKUP_FILE


def restore_config():
    if os.path.exists(BACKUP_FILE):
        shutil.copy(BACKUP_FILE, CONFIG_FILE)
        print("✓ config.ini を復元しました")


def set_strategy_flags(enable_a=False, enable_b=False, enable_c=False):
    parser = ConfigParser()
    parser.read(CONFIG_FILE, encoding='utf-8_sig')
    if 'Strategy' not in parser:
        parser.add_section('Strategy')
    parser['Strategy']['enable_strategy_a_adx'] = '1' if enable_a else '0'
    parser['Strategy']['enable_strategy_b_bb_rsi_sma'] = '1' if enable_b else '0'
    parser['Strategy']['enable_strategy_c_combined'] = '1' if enable_c else '0'
    with open(CONFIG_FILE, 'w', encoding='utf-8_sig') as f:
        parser.write(f)


def set_adx_parameters(term, continue_num, bull_threshold, bear_threshold):
    parser = ConfigParser()
    parser.read(CONFIG_FILE, encoding='utf-8_sig')
    if 'Strategy' not in parser:
        parser.add_section('Strategy')
    parser['Strategy']['adx_term'] = str(term)
    parser['Strategy']['adx_continue_num'] = str(continue_num)
    parser['Strategy']['adx_bull_threshold'] = str(bull_threshold)
    parser['Strategy']['adx_bear_threshold'] = str(bear_threshold)
    with open(CONFIG_FILE, 'w', encoding='utf-8_sig') as f:
        parser.write(f)


def run_quarterly_backtest():
    result = subprocess.run(
        ['python', 'run_quarterly_backtest.py'],
        cwd=WORKSPACE_ROOT,
        capture_output=True,
        text=True,
        timeout=7200
    )
    for line in result.stdout.split('\n'):
        if '✅ 結果を保存しました:' in line:
            path = line.split('✅ 結果を保存しました:')[-1].strip()
            if path and os.path.exists(path):
                return path
    files = glob.glob(os.path.join(RESULTS_DIR, 'quarterly_results_*.json'))
    if files:
        return max(files, key=os.path.getctime)
    return None


def load_quarterly_json(json_path):
    quarters = {}
    total = 0
    if not json_path or not os.path.exists(json_path):
        return quarters, total
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    for entry in data:
        year = entry.get('year')
        quarter = entry.get('quarter')
        metrics = entry.get('metrics') or {}
        pnl = metrics.get('total_pnl', 0)
        total += pnl
        if year and quarter:
            key = f"{year}/Q{quarter}"
            quarters[key] = {
                'pnl': pnl,
                'win_rate': metrics.get('win_rate'),
                'sharpe': metrics.get('sharpe')
            }
    return quarters, total


def print_comparison(baseline, combo_name, combo_total, combo_quarters):
    print(f"\n--- {combo_name} ---")
    diff = combo_total - baseline['total']
    status = '↑' if diff > 0 else ('↓' if diff < 0 else '→')
    print(f"total: {combo_total:.2f} USD ({status} {diff:.2f} vs baseline)")
    for quarter in sorted(baseline['quarters']):
        base_pnl = baseline['quarters'][quarter]['pnl']
        combo_pnl = combo_quarters.get(quarter, {}).get('pnl', 0)
        print(f"{quarter}: {combo_pnl:+.2f} (Δ {combo_pnl - base_pnl:+.2f})")


def make_report(baseline, combos_data):
    report = {
        'timestamp': datetime.now().isoformat(),
        'baseline_total': baseline['total'],
        'baseline_quarters': baseline['quarters'],
        'results': []
    }
    for combo in combos_data:
        report['results'].append({
            'label': combo['label'],
            'adx_term': combo['adx_term'],
            'adx_continue_num': combo['adx_continue'],
            'adx_bull_threshold': combo['adx_bull'],
            'adx_bear_threshold': combo['adx_bear'],
            'total_pnl': combo['total'],
            'delta': combo['total'] - baseline['total'],
            'quarters': combo['quarters']
        })
    with open(REPORT_FILE, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\n✓ レポート保存: {REPORT_FILE}")


def main():
    backup_config()
    baseline_quarters = {}

    print("\nBaseline（Strategy A/B/C OFF）を実行")
    set_strategy_flags(False, False, False)
    run_path = run_quarterly_backtest()
    baseline_quarters, baseline_total = load_quarterly_json(run_path)
    baseline = {'quarters': baseline_quarters, 'total': baseline_total}
    print(f"Baseline total: {baseline_total:.2f} USD")

    combos_data = []
    for combo in COMBOS:
        print(f"\n=== {combo['label']} ===")
        set_strategy_flags(True, False, False)
        set_adx_parameters(
            combo['adx_term'],
            combo['adx_continue'],
            combo['adx_bull_threshold'],
            combo['adx_bear_threshold']
        )
        path = run_quarterly_backtest()
        quarters, total = load_quarterly_json(path)
        combos_data.append({
            'label': combo['label'],
            'adx_term': combo['adx_term'],
            'adx_continue': combo['adx_continue'],
            'adx_bull': combo['adx_bull_threshold'],
            'adx_bear': combo['adx_bear_threshold'],
            'quarters': quarters,
            'total': total
        })
        print_comparison(baseline, combo['label'], total, quarters)

    make_report(baseline, combos_data)
    restore_config()


if __name__ == '__main__':
    main()
