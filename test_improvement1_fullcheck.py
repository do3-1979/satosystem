#!/usr/bin/env python3
"""
改善案1検証: 全期間でのテスト

2025 Q4初期でのPnL改善+262.51が、
他の期間では悪化していないか確認する
"""

import subprocess
import sys
import os
import json
from datetime import datetime

os.chdir('/home/satoshi/work/satosystem')

# 改善案1適用で全期間テスト
configs = [
    ('output_configs/extended_2024_Q1_baseline.ini', '2024 Q1 Baseline'),
    ('output_configs/extended_2024_Q1_adaptive.ini', '2024 Q1 Adaptive(改善案1)'),
    ('output_configs/test_2025_q1_baseline.ini', '2025 Q1 Baseline'),
    ('output_configs/test_2025_q1_adaptive.ini', '2025 Q1 Adaptive(改善案1)'),
    ('output_configs/extended_Q2_2025_baseline.ini', '2025 Q2 Baseline'),
    ('output_configs/extended_Q2_2025_adaptive.ini', '2025 Q2 Adaptive(改善案1)'),
]

print("="*70)
print("✅ Improvement 1: Full Year Validation")
print("="*70)
print(f"Start: {datetime.now().isoformat()}\n")

results = {}

for idx, (config_file, label) in enumerate(configs, 1):
    print(f"[{idx:2d}/{len(configs)}] {label:30s} ", end='', flush=True)
    
    try:
        result = subprocess.run(
            [sys.executable, 'src/backtest.py', config_file],
            capture_output=True,
            text=True,
            timeout=1200
        )
        
        if result.returncode != 0:
            print(f"❌")
            continue
        
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
                print(f"✅ ${data.get('total_pnl', 0):+7.2f}")
    
    except Exception as e:
        print(f"❌")

# 結果の比較
print(f"\n{'='*70}")
print("📊 Improvement 1: Full Year Impact Analysis")
print(f"{'='*70}\n")

periods = [
    ('2024 Q1', ['2024 Q1 Baseline', '2024 Q1 Adaptive(改善案1)']),
    ('2025 Q1', ['2025 Q1 Baseline', '2025 Q1 Adaptive(改善案1)']),
    ('2025 Q2', ['2025 Q2 Baseline', '2025 Q2 Adaptive(改善案1)']),
]

for period_name, labels in periods:
    if not all(l in results for l in labels):
        continue
    
    baseline = results[labels[0]]
    adaptive = results[labels[1]]
    
    pnl_diff = adaptive['pnl'] - baseline['pnl']
    pnl_pct = (pnl_diff / abs(baseline['pnl']) * 100) if baseline['pnl'] != 0 else 0
    
    print(f"{period_name}:")
    print(f"  Baseline: ${baseline['pnl']:+7.2f}")
    print(f"  Improved: ${adaptive['pnl']:+7.2f}")
    print(f"  Change:   {pnl_diff:+7.2f} ({pnl_pct:+.1f}%)")
    print()

print(f"\n{'='*70}")
print("✅ 改善案1の全期間への影響")
print(f"{'='*70}\n")
print("改善案1（WEAK_TREND制限）はQ4初期で+262.51改善を実現")
print("→ 他期間への悪化がなければコミット対象")

print(f"\nEnd: {datetime.now().isoformat()}")
