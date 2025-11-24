#!/usr/bin/env python3
"""
改善案2テスト: 環境別PVO閾値動的調整

STRONG_TREND: 低閾値(0.2) - エントリー促進
SIDEWAYS: 高閾値(1.0) - エントリー制限

最適な期間(2025 Q2 +56%)と悪化期間(2025 Q4 -34.9%)で効果を測定
"""

import subprocess
import sys
import os
import json
from datetime import datetime

os.chdir('/home/satoshi/work/satosystem')

configs = [
    ('output_configs/extended_Q2_2025_baseline.ini', '2025 Q2 Baseline'),
    ('output_configs/extended_Q2_2025_adaptive.ini', '2025 Q2 Adaptive(改善案2)'),
    ('output_configs/extended_Q4EARLY_2025_baseline.ini', '2025 Q4E Baseline'),
    ('output_configs/extended_Q4EARLY_2025_adaptive.ini', '2025 Q4E Adaptive(改善案2)'),
]

print("="*70)
print("🔧 Improvement 2: Dynamic PVO Threshold by Regime")
print("="*70)
print("Testing Q2 (+56% baseline) and Q4E (-34.9% worst case)")
print(f"Start: {datetime.now().isoformat()}\n")

results = {}

for idx, (config_file, label) in enumerate(configs, 1):
    print(f"[{idx}/{len(configs)}] {label:30s} ", end='', flush=True)
    
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
                print(f"✅ ${data.get('total_pnl', 0):+7.2f} | WR: {data.get('win_rate', 0):5.1f}%")
    
    except Exception as e:
        print(f"❌")

# 結果の比較
print(f"\n{'='*70}")
print("📊 Improvement 2 Results")
print(f"{'='*70}\n")

periods = [
    ('2025 Q2', ['2025 Q2 Baseline', '2025 Q2 Adaptive(改善案2)']),
    ('2025 Q4E', ['2025 Q4E Baseline', '2025 Q4E Adaptive(改善案2)']),
]

for period, labels in periods:
    if not all(l in results for l in labels):
        continue
    
    baseline = results[labels[0]]
    improved = results[labels[1]]
    original_phase1_pnl = -126.79 if '2025 Q2' in period else -259.64
    
    pnl_diff = improved['pnl'] - baseline['pnl']
    pnl_diff_vs_original = improved['pnl'] - original_phase1_pnl
    
    print(f"{period}:")
    print(f"  Baseline (no regime):   ${baseline['pnl']:+7.2f}")
    print(f"  Phase 1 v1 (original):  ${original_phase1_pnl:+7.2f}")
    print(f"  Improved (改善案2):      ${improved['pnl']:+7.2f}")
    print(f"  vs Baseline:            {pnl_diff:+7.2f}")
    print(f"  vs Original Phase 1:    {pnl_diff_vs_original:+7.2f}")
    print()

print(f"{'='*70}")
print("評価基準:")
print("✅: Q2でバランス悪化なく改善、Q4Eで改善")
print("⚠️: Q2の改善が損なわれていない")
print("❌: Q2の大幅な改善が失われている")

print(f"\nEnd: {datetime.now().isoformat()}")
