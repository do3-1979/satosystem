#!/usr/bin/env python3
"""
Phase 2 段階的フィルタリング効果比較テスト: 2024 Q1～Q4, 2025 Q1～Q3
8期間全期間でBaseline（段階的ポジションサイジング無効）とPhase2（有効）を実行・比較
"""

import subprocess
import sys
import os
import json
from datetime import datetime

os.chdir('/home/satoshi/work/satosystem')

configs = [
    # 2024
    ('output_configs/phase2_2024_Q1_baseline.ini', '2024 Q1 Baseline'),
    ('output_configs/phase2_2024_Q1_phase2.ini', '2024 Q1 Phase2'),
    ('output_configs/phase2_2024_Q2_baseline.ini', '2024 Q2 Baseline'),
    ('output_configs/phase2_2024_Q2_phase2.ini', '2024 Q2 Phase2'),
    ('output_configs/phase2_2024_Q3_baseline.ini', '2024 Q3 Baseline'),
    ('output_configs/phase2_2024_Q3_phase2.ini', '2024 Q3 Phase2'),
    ('output_configs/phase2_2024_Q4_baseline.ini', '2024 Q4 Baseline'),
    ('output_configs/phase2_2024_Q4_phase2.ini', '2024 Q4 Phase2'),
    # 2025
    ('output_configs/phase2_2025_Q1_baseline.ini', '2025 Q1 Baseline'),
    ('output_configs/phase2_2025_Q1_phase2.ini', '2025 Q1 Phase2'),
    ('output_configs/phase2_2025_Q2_baseline.ini', '2025 Q2 Baseline'),
    ('output_configs/phase2_2025_Q2_phase2.ini', '2025 Q2 Phase2'),
    ('output_configs/phase2_2025_Q3_baseline.ini', '2025 Q3 Baseline'),
    ('output_configs/phase2_2025_Q3_phase2.ini', '2025 Q3 Phase2'),
]

print("="*70)
print("🚀 Phase 2 Graduated Filtering Effectiveness Comparison: 2024-2025")
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
            print(f"❌ (Return code: {result.returncode})")
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
        else:
            print(f"⚠️  No report file found")
            failed.append(label)
    
    except subprocess.TimeoutExpired:
        print(f"❌ Timeout")
        failed.append(label)
    except Exception as e:
        print(f"❌ {str(e)[:50]}")
        failed.append(label)

# 結果の比較
print(f"\n{'='*70}")
print("📊 Results Comparison: Phase 2 Graduated Filtering Effect")
print(f"{'='*70}\n")

periods = {
    '2024 Q1': [k for k in results.keys() if '2024 Q1' in k],
    '2024 Q2': [k for k in results.keys() if '2024 Q2' in k],
    '2024 Q3': [k for k in results.keys() if '2024 Q3' in k],
    '2024 Q4': [k for k in results.keys() if '2024 Q4' in k],
    '2025 Q1': [k for k in results.keys() if '2025 Q1' in k],
    '2025 Q2': [k for k in results.keys() if '2025 Q2' in k],
    '2025 Q3': [k for k in results.keys() if '2025 Q3' in k],
}

comparison_results = []

for period_name, keys in periods.items():
    if len(keys) != 2:
        continue
    
    baseline = next((k for k in keys if 'Baseline' in k), None)
    phase2 = next((k for k in keys if 'Phase2' in k), None)
    
    if baseline and phase2 and baseline in results and phase2 in results:
        b = results[baseline]
        p = results[phase2]
        
        pnl_diff = p['pnl'] - b['pnl']
        pnl_diff_pct = (pnl_diff / abs(b['pnl']) * 100) if b['pnl'] != 0 else 0
        wr_diff = p['win_rate'] - b['win_rate']
        pf_diff = p['profit_factor'] - b['profit_factor']
        
        comparison_results.append({
            'period': period_name,
            'baseline_pnl': b['pnl'],
            'phase2_pnl': p['pnl'],
            'pnl_diff': pnl_diff,
            'pnl_diff_pct': pnl_diff_pct,
            'baseline_wr': b['win_rate'],
            'phase2_wr': p['win_rate'],
            'wr_diff': wr_diff,
            'baseline_pf': b['profit_factor'],
            'phase2_pf': p['profit_factor'],
            'pf_diff': pf_diff,
            'baseline_trades': b['trades'],
            'phase2_trades': p['trades'],
        })
        
        print(f"【{period_name}】")
        print(f"  Baseline: PnL=${b['pnl']:+7.2f} | WR={b['win_rate']:5.1f}% | PF={b['profit_factor']:5.2f} | Trades={b['trades']}")
        print(f"  Phase2:   PnL=${p['pnl']:+7.2f} | WR={p['win_rate']:5.1f}% | PF={p['profit_factor']:5.2f} | Trades={p['trades']}")
        print(f"  DIFF:     PnL=${pnl_diff:+7.2f} ({pnl_diff_pct:+6.2f}%) | WR={wr_diff:+5.1f}% | PF={pf_diff:+5.2f}")
        print()

# サマリー
print(f"{'='*70}")
print("📈 Summary")
print(f"{'='*70}\n")

if comparison_results:
    total_baseline_pnl = sum(r['baseline_pnl'] for r in comparison_results)
    total_phase2_pnl = sum(r['phase2_pnl'] for r in comparison_results)
    avg_pnl_diff = total_phase2_pnl - total_baseline_pnl
    avg_wr_diff = sum(r['wr_diff'] for r in comparison_results) / len(comparison_results)
    
    print(f"Total Baseline PnL: ${total_baseline_pnl:+7.2f}")
    print(f"Total Phase2 PnL:   ${total_phase2_pnl:+7.2f}")
    print(f"Overall PnL Improvement: ${avg_pnl_diff:+7.2f}")
    print(f"Average WR Improvement: {avg_wr_diff:+5.2f}%")
    print()

if failed:
    print(f"\n⚠️  Failed tests ({len(failed)}):")
    for label in failed:
        print(f"  - {label}")

print(f"\nEnd: {datetime.now().isoformat()}")
