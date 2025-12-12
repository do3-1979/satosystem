#!/usr/bin/env python3
"""
Phase 0ベースラインとの比較スクリプト
新しい実装の効果を正確に測定するためのツール
"""

import json
import sys
from pathlib import Path

PHASE0_BASELINE = 'docs/results/phase0/regression_test_results.json'

def load_phase0():
    """Phase 0ベースラインを読み込む"""
    with open(PHASE0_BASELINE, 'r') as f:
        results = json.load(f)
    return {f"Q{item['quarter']} {item['year']}": item['metrics']['total_pnl'] for item in results}

def load_current(filepath):
    """現在の結果を読み込む"""
    with open(filepath, 'r') as f:
        results = json.load(f)
    return {f"Q{item['quarter']} {item['year']}": item['metrics']['total_pnl'] for item in results}

def compare(phase0_data, current_data):
    """Phase 0との比較を実行"""
    quarters = ['Q1 2024', 'Q2 2024', 'Q3 2024', 'Q4 2024', 'Q1 2025', 'Q2 2025', 'Q3 2025', 'Q4 2025']
    
    print("\n" + "=" * 110)
    print("Phase 0ベースライン vs 現在の実装")
    print("=" * 110)
    print(f"{'Quarter':^12} | {'Phase 0':^12} | {'現在':^12} | {'変化':^12} | {'変化率':^10} | {'評価'}")
    print("-" * 110)
    
    total_p0 = 0
    total_current = 0
    improvements = []
    regressions = []
    
    for q in quarters:
        p0 = phase0_data[q]
        curr = current_data[q]
        change = curr - p0
        pct = (change / abs(p0) * 100) if p0 != 0 else 0
        
        total_p0 += p0
        total_current += curr
        
        if change > 0:
            eval_text = "✅ 改善"
            improvements.append((q, change, pct))
        elif abs(change) < 0.01:
            eval_text = "⚪ 変化なし"
        else:
            eval_text = "❌ 悪化"
            regressions.append((q, change, pct))
        
        print(f"{q:^12} | ${p0:>10.2f} | ${curr:>10.2f} | ${change:>10.2f} | {pct:>8.1f}% | {eval_text}")
    
    print("-" * 110)
    total_change = total_current - total_p0
    total_pct = (total_change / abs(total_p0) * 100) if total_p0 != 0 else 0
    marker = "✅" if total_change >= 0 else "❌"
    print(f"{'合計':^12} | ${total_p0:>10.2f} | ${total_current:>10.2f} | ${total_change:>10.2f} | {total_pct:>8.1f}% | {marker}")
    
    # 勝ちQ保護チェック
    print("\n【勝ちQuarter保護チェック】")
    winning_quarters = ['Q1 2024', 'Q3 2024', 'Q4 2024']
    p0_win_total = sum(phase0_data[q] for q in winning_quarters if phase0_data[q] > 0)
    curr_win_total = sum(current_data[q] for q in winning_quarters if current_data[q] > 0)
    
    for q in winning_quarters:
        p0 = phase0_data[q]
        if p0 > 0:  # Phase 0で勝ちだったQuarter
            curr = current_data[q]
            delta = curr - p0
            if abs(delta) < 0.01:
                marker = "✅ 変化なし"
            elif delta > 0:
                marker = "✅ さらに改善"
            else:
                marker = f"❌ 悪化 (-${abs(delta):.2f})"
            print(f"  {q}: ${p0:.2f} → ${curr:.2f} {marker}")
    
    print(f"\n  勝ちQ合計: ${p0_win_total:.2f} → ${curr_win_total:.2f} ({curr_win_total - p0_win_total:+.2f})")
    
    # 最終判定
    print("\n" + "=" * 110)
    print("【最終判定】")
    print("=" * 110)
    
    if total_change > 0 and abs(curr_win_total - p0_win_total) < 0.01:
        status = "✅ 成功"
        reason = "トータルPnLが向上し、勝ちQが保護されている"
        recommendation = "この実装を保持。次フェーズへ進行"
    elif abs(total_change) < 0.01 and abs(curr_win_total - p0_win_total) < 0.01:
        status = "✅ セーフ"
        reason = "全体への悪影響がない"
        recommendation = "この実装を保持。次フェーズへ進行"
    else:
        status = "❌ 失敗"
        reason = "トータルまたは勝ちQが悪化している"
        recommendation = "ロールバック推奨"
    
    print(f"Status: {status}")
    print(f"Reason: {reason}")
    print(f"Recommendation: {recommendation}")
    
    print(f"\n改善Quarter: {len(improvements)}件")
    for q, change, pct in improvements:
        print(f"  ✅ {q}: +${change:.2f} (+{pct:.1f}%)")
    
    if regressions:
        print(f"\n悪化Quarter: {len(regressions)}件")
        for q, change, pct in regressions:
            print(f"  ❌ {q}: -${abs(change):.2f} ({pct:.1f}%)")
    
    print("\n" + "=" * 110 + "\n")
    
    return status, reason

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python compare_with_phase0.py <current_results.json>")
        sys.exit(1)
    
    current_file = sys.argv[1]
    
    if not Path(PHASE0_BASELINE).exists():
        print(f"Error: Phase 0ベースライン {PHASE0_BASELINE} が見つかりません")
        sys.exit(1)
    
    if not Path(current_file).exists():
        print(f"Error: {current_file} が見つかりません")
        sys.exit(1)
    
    phase0_data = load_phase0()
    current_data = load_current(current_file)
    
    compare(phase0_data, current_data)
