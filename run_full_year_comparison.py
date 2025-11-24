#!/usr/bin/env python3
"""
Phase 1 効果比較テスト: 2024 Q1～Q4, 2025 Q1～Q4
2年間全期間でBaseline（検出なし）とAdaptive（検出あり）を実行・比較
"""

import subprocess
import sys
import os
import json
from datetime import datetime

os.chdir('/home/satoshi/work/satosystem')

configs = [
    # 2024
    ('output_configs/extended_2024_Q1_baseline.ini', '2024 Q1 Baseline'),
    ('output_configs/extended_2024_Q1_adaptive.ini', '2024 Q1 Adaptive'),
    ('output_configs/extended_2024_Q2_baseline.ini', '2024 Q2 Baseline'),
    ('output_configs/extended_2024_Q2_adaptive.ini', '2024 Q2 Adaptive'),
    ('output_configs/extended_2024_Q3_baseline.ini', '2024 Q3 Baseline'),
    ('output_configs/extended_2024_Q3_adaptive.ini', '2024 Q3 Adaptive'),
    ('output_configs/extended_2024_Q4_baseline.ini', '2024 Q4 Baseline'),
    ('output_configs/extended_2024_Q4_adaptive.ini', '2024 Q4 Adaptive'),
    # 2025
    ('output_configs/test_2025_q1_baseline.ini', '2025 Q1 Baseline'),
    ('output_configs/test_2025_q1_adaptive.ini', '2025 Q1 Adaptive'),
    ('output_configs/extended_Q2_2025_baseline.ini', '2025 Q2 Baseline'),
    ('output_configs/extended_Q2_2025_adaptive.ini', '2025 Q2 Adaptive'),
    ('output_configs/extended_Q4EARLY_2025_baseline.ini', '2025 Q4E Baseline'),
    ('output_configs/extended_Q4EARLY_2025_adaptive.ini', '2025 Q4E Adaptive'),
]

print("="*70)
print("🚀 Phase 1 Effectiveness Comparison: 2024-2025 Full Year Analysis")
print("="*70)
print(f"Start: {datetime.now().isoformat()}\n")

results = {}
failed = []

for idx, (config_file, label) in enumerate(configs, 1):
    print(f"[{idx:2d}/{len(configs)}] {label:25s} ", end='', flush=True)
    
    try:
        result = subprocess.run(
            [sys.executable, 'src/backtest.py', config_file],
            capture_output=True,
            text=True,
            timeout=1800
        )
        
        if result.returncode != 0:
            print(f"❌")
            failed.append(label)
            continue
        
        # レポート取得
        report_files = sorted(
            [f for f in os.listdir('report') if f.startswith('backtest_summary_')],
            key=lambda x: os.path.getmtime(os.path.join('report', x)),
            reverse=True
        )
        
        if report_files:
            with open(f'report/{report_files[0]}', 'r') as f:
                data = json.load(f)
                results[label] = {
                    'trades': data.get('trade_count', 0),
                    'pnl': data.get('total_pnl', 0),
                    'win_rate': data.get('win_rate', 0),
                    'profit_factor': data.get('profit_factor', 0)
                }
                print(f"✅ {data.get('trade_count', 0):2d}trades | ${data.get('total_pnl', 0):+7.2f} | WR:{data.get('win_rate', 0):5.1f}%")
    
    except subprocess.TimeoutExpired:
        print(f"❌ Timeout")
        failed.append(label)
    except Exception as e:
        print(f"❌ {str(e)[:50]}")
        failed.append(label)

# 結果の比較
print(f"\n{'='*70}")
print("📊 Results Comparison")
print(f"{'='*70}\n")

periods_2024 = {
    '2024 Q1': [k for k in results.keys() if '2024 Q1' in k],
    '2024 Q2': [k for k in results.keys() if '2024 Q2' in k],
    '2024 Q3': [k for k in results.keys() if '2024 Q3' in k],
    '2024 Q4': [k for k in results.keys() if '2024 Q4' in k],
}

periods_2025 = {
    '2025 Q1': [k for k in results.keys() if '2025 Q1' in k],
    '2025 Q2': [k for k in results.keys() if '2025 Q2' in k],
    '2025 Q4E': [k for k in results.keys() if '2025 Q4E' in k],
}

print("【2024 Analysis】\n")
for period, keys in sorted(periods_2024.items()):
    if len(keys) != 2:
        continue
    
    baseline = results[keys[0]]
    adaptive = results[keys[1]]
    
    trade_diff = baseline['trades'] - adaptive['trades']
    trade_pct = (trade_diff / baseline['trades'] * 100) if baseline['trades'] > 0 else 0
    
    pnl_diff = adaptive['pnl'] - baseline['pnl']
    pnl_pct = (pnl_diff / abs(baseline['pnl']) * 100) if baseline['pnl'] != 0 else 0
    
    wr_diff = adaptive['win_rate'] - baseline['win_rate']
    pf_diff = adaptive['profit_factor'] - baseline['profit_factor']
    
    print(f"{period}:")
    print(f"  Trades:        {baseline['trades']:3d} → {adaptive['trades']:3d} ({trade_diff:+d}, {trade_pct:+.1f}%)")
    print(f"  PnL (USDT):    ${baseline['pnl']:+7.2f} → ${adaptive['pnl']:+7.2f} ({pnl_diff:+7.2f}, {pnl_pct:+.1f}%)")
    print(f"  Win Rate:      {baseline['win_rate']:5.1f}% → {adaptive['win_rate']:5.1f}% ({wr_diff:+5.1f}pp)")
    print(f"  Profit Factor: {baseline['profit_factor']:5.2f} → {adaptive['profit_factor']:5.2f} ({pf_diff:+5.2f})")
    print()

print("\n【2025 Analysis】\n")
for period, keys in sorted(periods_2025.items()):
    if len(keys) != 2:
        continue
    
    baseline = results[keys[0]]
    adaptive = results[keys[1]]
    
    trade_diff = baseline['trades'] - adaptive['trades']
    trade_pct = (trade_diff / baseline['trades'] * 100) if baseline['trades'] > 0 else 0
    
    pnl_diff = adaptive['pnl'] - baseline['pnl']
    pnl_pct = (pnl_diff / abs(baseline['pnl']) * 100) if baseline['pnl'] != 0 else 0
    
    wr_diff = adaptive['win_rate'] - baseline['win_rate']
    pf_diff = adaptive['profit_factor'] - baseline['profit_factor']
    
    print(f"{period}:")
    print(f"  Trades:        {baseline['trades']:3d} → {adaptive['trades']:3d} ({trade_diff:+d}, {trade_pct:+.1f}%)")
    print(f"  PnL (USDT):    ${baseline['pnl']:+7.2f} → ${adaptive['pnl']:+7.2f} ({pnl_diff:+7.2f}, {pnl_pct:+.1f}%)")
    print(f"  Win Rate:      {baseline['win_rate']:5.1f}% → {adaptive['win_rate']:5.1f}% ({wr_diff:+5.1f}pp)")
    print(f"  Profit Factor: {baseline['profit_factor']:5.2f} → {adaptive['profit_factor']:5.2f} ({pf_diff:+5.2f})")
    print()

if failed:
    print(f"\n⚠️  Failed tests ({len(failed)}): {', '.join(failed[:3])}")

print(f"\nEnd: {datetime.now().isoformat()}")
print(f"{'='*70}")
