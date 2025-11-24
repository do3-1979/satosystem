#!/usr/bin/env python3
"""
Phase 1 効果比較テスト: Q1, Q2, Q4初期
- 各期間でBaseline（マーケットレジーム検出なし）とAdaptive（検出あり）を実行
- 結果を自動比較
"""

import subprocess
import sys
import os
import json
from datetime import datetime

os.chdir('/home/satoshi/work/satosystem')

configs = [
    ('output_configs/test_2025_q1_baseline.ini', 'Q1 Baseline (No Regime)'),
    ('output_configs/test_2025_q1_adaptive.ini', 'Q1 Adaptive (Phase 1)'),
    ('output_configs/extended_Q2_2025_baseline.ini', 'Q2 Baseline (No Regime)'),
    ('output_configs/extended_Q2_2025_adaptive.ini', 'Q2 Adaptive (Phase 1)'),
    ('output_configs/extended_Q4EARLY_2025_baseline.ini', 'Q4Early Baseline (No Regime)'),
    ('output_configs/extended_Q4EARLY_2025_adaptive.ini', 'Q4Early Adaptive (Phase 1)'),
]

print("="*70)
print("🚀 Phase 1 Multi-Period Effectiveness Comparison")
print("="*70)
print(f"Start: {datetime.now().isoformat()}\n")

results = {}
failed = []

for idx, (config_file, label) in enumerate(configs, 1):
    print(f"\n[{idx}/{len(configs)}] {label}")
    print(f"{'='*70}")
    
    try:
        result = subprocess.run(
            [sys.executable, 'src/backtest.py', config_file],
            capture_output=True,
            text=True,
            timeout=1800  # 30分
        )
        
        if result.returncode != 0:
            print(f"❌ Error: {result.stderr[:200]}")
            failed.append(label)
            continue
        
        # レポートから結果を抽出
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
                print(f"✅ {data.get('trade_count', 0)} trades, PnL: ${data.get('total_pnl', 0):.2f}, WR: {data.get('win_rate', 0):.1f}%")
    
    except subprocess.TimeoutExpired:
        print(f"❌ Timeout")
        failed.append(label)
    except Exception as e:
        print(f"❌ {str(e)[:100]}")
        failed.append(label)

# 結果の比較表を作成
print(f"\n\n{'='*70}")
print("📊 Results Comparison")
print(f"{'='*70}\n")

periods = {
    'Q1': [k for k in results.keys() if 'Q1' in k],
    'Q2': [k for k in results.keys() if 'Q2' in k],
    'Q4Early': [k for k in results.keys() if 'Q4Early' in k]
}

for period, keys in periods.items():
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
    
    print(f"【{period}】")
    print(f"  Trades:        {baseline['trades']:3d} → {adaptive['trades']:3d} ({trade_diff:+d}, {trade_pct:+.1f}%)")
    print(f"  PnL (USDT):    ${baseline['pnl']:+7.2f} → ${adaptive['pnl']:+7.2f} ({pnl_diff:+7.2f}, {pnl_pct:+.1f}%)")
    print(f"  Win Rate:      {baseline['win_rate']:5.1f}% → {adaptive['win_rate']:5.1f}% ({wr_diff:+5.1f}pp)")
    print(f"  Profit Factor: {baseline['profit_factor']:5.2f} → {adaptive['profit_factor']:5.2f} ({pf_diff:+5.2f})")
    print()

if failed:
    print(f"\n⚠️  Failed: {', '.join(failed)}")

print(f"\nEnd: {datetime.now().isoformat()}")
print(f"{'='*70}")
