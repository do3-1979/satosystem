#!/usr/bin/env python3
"""
フィルター効果推定スクリプト - 実データベース使用版

実際の四半期インジケータデータを使用して、3つのフィルター
シナリオの効果を推定します。

シナリオ：
  1. PVO フィルターのみ (PVO > 0)
  2. ADX フィルターのみ (ADX > 70)
  3. PVO + ADX 両フィルター
"""

import json
import os
from datetime import datetime
import pandas as pd

WORKSPACE_ROOT = os.path.dirname(os.path.abspath(__file__))

def load_quarterly_data():
    """
    QUARTERLY_INDICATOR_ANALYSIS.md から四半期データを読み込む
    
    Returns:
        list: 四半期ごとのPnLと指標データ
    """
    quarters_data = [
        {'Q': 'Q1 2024', 'PnL': 921.85, 'PVO': 1.930, 'ADX': 100.00},
        {'Q': 'Q2 2024', 'PnL': -25.80, 'PVO': -0.166, 'ADX': 42.31},
        {'Q': 'Q3 2024', 'PnL': -56.21, 'PVO': -0.294, 'ADX': 51.61},
        {'Q': 'Q4 2024', 'PnL': 185.74, 'PVO': 0.727, 'ADX': 78.26},
        {'Q': 'Q1 2025', 'PnL': -172.30, 'PVO': -1.638, 'ADX': 11.54},
        {'Q': 'Q2 2025', 'PnL': -123.88, 'PVO': -1.014, 'ADX': 16.00},
        {'Q': 'Q3 2025', 'PnL': -79.36, 'PVO': -0.234, 'ADX': 75.00},
        {'Q': 'Q4 2025', 'PnL': 254.32, 'PVO': 0.946, 'ADX': 100.00},
    ]
    return quarters_data

def apply_filters(quarters_data):
    """
    3つのシナリオでフィルターを適用
    
    Returns:
        dict: 各シナリオの結果
    """
    results = {
        'Scenario 1: PVO Only': [],
        'Scenario 2: ADX Only': [],
        'Scenario 3: PVO + ADX': []
    }
    
    for q in quarters_data:
        quarter = q['Q']
        pnl = q['PnL']
        pvo = q['PVO']
        adx = q['ADX']
        
        # 条件判定
        pvo_ok = pvo > 0
        adx_ok = adx > 70
        both_ok = pvo_ok and adx_ok
        
        # Scenario 1: PVO フィルターのみ
        s1_pnl = pnl if pvo_ok else 0.0
        results['Scenario 1: PVO Only'].append({
            'Q': quarter,
            'PVO': f'{pvo:+.3f}',
            'ADX': f'{adx:6.2f}',
            'PVO>0': '✅' if pvo_ok else '❌',
            'PnL': s1_pnl
        })
        
        # Scenario 2: ADX フィルターのみ
        s2_pnl = pnl if adx_ok else 0.0
        results['Scenario 2: ADX Only'].append({
            'Q': quarter,
            'PVO': f'{pvo:+.3f}',
            'ADX': f'{adx:6.2f}',
            'ADX>70': '✅' if adx_ok else '❌',
            'PnL': s2_pnl
        })
        
        # Scenario 3: 両フィルター
        s3_pnl = pnl if both_ok else 0.0
        results['Scenario 3: PVO + ADX'].append({
            'Q': quarter,
            'PVO': f'{pvo:+.3f}',
            'ADX': f'{adx:6.2f}',
            'Both OK': '✅' if both_ok else '❌',
            'PnL': s3_pnl
        })
    
    return results

def main():
    """メイン処理"""
    
    print("\n" + "="*140)
    print("🔬 フィルター効果推定：3シナリオの比較（実データベース使用）")
    print("="*140)
    print(f"実行時刻: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"データソース: QUARTERLY_INDICATOR_ANALYSIS.md\n")
    
    # データを読み込み
    quarters_data = load_quarterly_data()
    base_total = sum(q['PnL'] for q in quarters_data)
    
    # フィルターを適用
    results = apply_filters(quarters_data)
    
    # 結果を表示
    comparison_rows = []
    
    for scenario_name, results_list in results.items():
        df = pd.DataFrame(results_list)
        
        print(f"\n{'='*140}")
        print(f"📊 {scenario_name}")
        print(f"{'='*140}")
        
        # テーブル表示
        display_cols = list(df.columns)
        print(df[display_cols].to_string(index=False))
        
        # サマリー統計
        total_pnl = df['PnL'].sum()
        filtered_count = (df['PnL'] > 0).sum() + (df['PnL'] < 0).sum()
        loss_reduction = base_total - total_pnl
        improvement = (loss_reduction / abs(base_total) * 100) if base_total != 0 else 0
        
        print(f"\n📈 {scenario_name} のサマリー:")
        print(f"   総損益: {total_pnl:>10.2f} USD")
        print(f"   ロス削減: {loss_reduction:>10.2f} USD")
        print(f"   改善率: {improvement:>+10.2f}%")
        print(f"   エントリー回数: {filtered_count} 回")
        
        # 勝敗
        wins = (df['PnL'] > 0).sum()
        losses = (df['PnL'] < 0).sum()
        print(f"   勝敗: {wins}W - {losses}L")
        
        comparison_rows.append({
            'Scenario': scenario_name.split(':')[0],
            'Total PnL': total_pnl,
            'Loss Reduction': loss_reduction,
            'Improvement %': improvement,
            'Entries': filtered_count,
            'Wins': wins,
            'Losses': losses
        })
    
    # 比較レポート
    print("\n" + "="*140)
    print("🎯 シナリオ別比較")
    print("="*140)
    
    comparison_df = pd.DataFrame(comparison_rows)
    print(comparison_df[['Scenario', 'Total PnL', 'Loss Reduction', 'Improvement %', 'Wins', 'Losses']].to_string(index=False))
    
    # ベース情報
    print(f"\n📊 ベースライン（フィルターなし）:")
    print(f"   総損益: {base_total:.2f} USD")
    
    # 最適フィルターの特定
    print("\n" + "="*140)
    print("🏆 推奨フィルター")
    print("="*140)
    
    best_scenario = max(comparison_rows, key=lambda x: x['Total PnL'])
    print(f"\n✅ 最適フィルター: {best_scenario['Scenario']}")
    print(f"   損益: {best_scenario['Total PnL']:.2f} USD")
    print(f"   改善率: {best_scenario['Improvement %']:+.2f}%")
    print(f"   ロス削減: {best_scenario['Loss Reduction']:.2f} USD")
    
    # 結果をファイルに保存
    output_dir = os.path.join(WORKSPACE_ROOT, 'docs', 'analysis')
    os.makedirs(output_dir, exist_ok=True)
    
    csv_path = os.path.join(output_dir, 'filter_scenario_comparison_estimated.csv')
    comparison_df.to_csv(csv_path, index=False, encoding='utf-8-sig')
    print(f"\n✅ 結果を保存: {csv_path}")
    
    print("\n" + "="*140)

if __name__ == '__main__':
    main()
