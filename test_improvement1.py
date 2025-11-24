#!/usr/bin/env python3
"""
改善案1テスト: 動的STRONG_TREND基準調整

2025 Q4初期（-34.9%悪化していた期間）で改善効果を測定
- Before: -$259.64 (Phase 1基本版)
- After: 本改善適用版
"""

import subprocess
import sys
import os
import json
from datetime import datetime

os.chdir('/home/satoshi/work/satosystem')

# 改善前のベースラインテスト（既存結果）
baseline_results = {
    '2025_Q4E_Baseline': {'pnl': -192.48, 'win_rate': 46.4, 'pf': 0.94},
    '2025_Q4E_Phase1_v1': {'pnl': -259.64, 'win_rate': 29.3, 'pf': 0.73}
}

# 改善案1適用版テスト
configs_to_test = [
    ('output_configs/extended_Q4EARLY_2025_baseline.ini', '改善前 Baseline'),
    ('output_configs/extended_Q4EARLY_2025_adaptive.ini', '改善案1適用版 Adaptive'),
]

print("="*70)
print("🔧 Improvement 1: Dynamic STRONG_TREND Threshold Adjustment")
print("="*70)
print("Target Period: 2025 Q4 Early (worst case)")
print(f"Start: {datetime.now().isoformat()}\n")

results = {}

for idx, (config_file, label) in enumerate(configs_to_test, 1):
    print(f"[{idx}/{len(configs_to_test)}] {label:30s} ", end='', flush=True)
    
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
                print(f"✅ PnL: ${data.get('total_pnl', 0):+7.2f} | WR: {data.get('win_rate', 0):5.1f}% | PF: {data.get('profit_factor', 0):5.2f}")
    
    except subprocess.TimeoutExpired:
        print(f"❌ Timeout")
    except Exception as e:
        print(f"❌ {str(e)[:50]}")

# 結果の比較
print(f"\n{'='*70}")
print("📊 Improvement 1 Analysis Results")
print(f"{'='*70}\n")

baseline = results.get('改善前 Baseline')
original_phase1 = baseline_results.get('2025_Q4E_Phase1_v1')
improved_phase1 = results.get('改善案1適用版 Adaptive')

if baseline and improved_phase1:
    pnl_before = original_phase1['pnl']
    pnl_after = improved_phase1['pnl']
    pnl_improvement = pnl_after - pnl_before
    pnl_improvement_pct = (pnl_improvement / abs(pnl_before) * 100) if pnl_before != 0 else 0
    
    wr_before = original_phase1['win_rate']
    wr_after = improved_phase1['win_rate']
    wr_improvement = wr_after - wr_before
    
    pf_before = original_phase1['pf']
    pf_after = improved_phase1['profit_factor']
    pf_improvement = pf_after - pf_before
    
    print("【改善案1適用前後の比較】\n")
    print(f"PnL:")
    print(f"  改善前 (Phase 1 v1):  ${pnl_before:+7.2f}")
    print(f"  改善後 (本改善版):     ${pnl_after:+7.2f}")
    print(f"  → {pnl_improvement:+7.2f} ({pnl_improvement_pct:+.1f}%)")
    
    print(f"\nWin Rate:")
    print(f"  改善前:  {wr_before:5.1f}%")
    print(f"  改善後:  {wr_after:5.1f}%")
    print(f"  → {wr_improvement:+5.1f}pp")
    
    print(f"\nProfit Factor:")
    print(f"  改善前:  {pf_before:5.2f}")
    print(f"  改善後:  {pf_after:5.2f}")
    print(f"  → {pf_improvement:+5.2f}")
    
    # 効果判定
    print(f"\n{'='*70}")
    if pnl_improvement > 0:
        print(f"✅ 改善案1は効果あり！ (PnL改善: {pnl_improvement_pct:+.1f}%)")
        print(f"   推奨: コミット対象")
    elif pnl_improvement >= -50:  # ±50未満の変動は許容
        print(f"⚠️  改善案1は効果わずか (PnL変化: {pnl_improvement_pct:.1f}%)")
        print(f"   推奨: 他の改善案と組み合わせて再評価")
    else:
        print(f"❌ 改善案1は効果なし (PnL悪化: {pnl_improvement_pct:.1f}%)")
        print(f"   推奨: このアプローチは廃止、別案を検討")

print(f"\nEnd: {datetime.now().isoformat()}")
print(f"{'='*70}")
