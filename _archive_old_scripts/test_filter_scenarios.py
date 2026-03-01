#!/usr/bin/env python3
"""
フィルター検証スクリプト：PVO と ADX の効果を3シナリオで比較

実行シナリオ:
  1. PVO フィルターのみ (PVO > 0)
  2. ADX フィルターのみ (ADX > 70)
  3. PVO AND ADX フィルター両方

全8四半期（Q1 2024 - Q4 2025）でバックテストを実行し、結果を比較
"""

import json
import subprocess
import sys
from pathlib import Path
from datetime import datetime
import pandas as pd
import numpy as np

def run_backtest_for_quarters(filter_config):
    """
    指定されたフィルター設定で全8四半期のバックテストを実行
    """
    quarters = [
        ('2024-01-01', '2024-03-31', 'Q1 2024'),
        ('2024-04-01', '2024-06-30', 'Q2 2024'),
        ('2024-07-01', '2024-09-30', 'Q3 2024'),
        ('2024-10-01', '2024-12-31', 'Q4 2024'),
        ('2025-01-01', '2025-03-31', 'Q1 2025'),
        ('2025-04-01', '2025-06-30', 'Q2 2025'),
        ('2025-07-01', '2025-09-30', 'Q3 2025'),
        ('2025-10-01', '2025-12-21', 'Q4 2025'),
    ]
    
    results = []
    scenario_name = filter_config.get('name', 'Unknown')
    
    print(f"\n{'='*100}")
    print(f"🧪 {scenario_name}")
    print(f"{'='*100}")
    print(f"フィルター設定: {filter_config}")
    print(f"\nバックテスト実行中...\n")
    
    for start_date, end_date, quarter_name in quarters:
        print(f"  ⏳ {quarter_name} ({start_date} → {end_date})...", end=' ', flush=True)
        
        try:
            # config.ini を一時的に修正
            config_path = Path('src/config.ini')
            original_content = config_path.read_text(encoding='utf-8')
            
            # フィルター設定を挿入
            modified_content = original_content
            for key, value in filter_config.get('settings', {}).items():
                # 既存の設定値を置換
                import re
                pattern = f'^{key}\s*=\s*.*$'
                replacement = f'{key} = {value}'
                modified_content = re.sub(pattern, replacement, modified_content, flags=re.MULTILINE)
            
            # 期間を設定
            modified_content = re.sub(
                r'^start_time\s*=\s*.*$',
                f'start_time = {start_date} 00:00',
                modified_content, flags=re.MULTILINE
            )
            modified_content = re.sub(
                r'^end_time\s*=\s*.*$',
                f'end_time = {end_date} 23:59',
                modified_content, flags=re.MULTILINE
            )
            
            config_path.write_text(modified_content, encoding='utf-8')
            
            # バックテスト実行
            result = subprocess.run(
                ['python', 'src/backtest.py'],
                cwd='/home/satoshi/work/satosystem',
                capture_output=True,
                text=True,
                timeout=300
            )
            
            # 設定を復元
            config_path.write_text(original_content, encoding='utf-8')
            
            # 結果を解析
            if result.returncode == 0:
                # ログから指標を抽出
                pnl_match = re.search(r'Total\s+PnL:\s*([-\d.]+)', result.stdout)
                win_rate_match = re.search(r'Win\s+Rate:\s*([\d.]+)%', result.stdout)
                trades_match = re.search(r'Total\s+Trades:\s*(\d+)', result.stdout)
                
                pnl = float(pnl_match.group(1)) if pnl_match else 0.0
                win_rate = float(win_rate_match.group(1)) if win_rate_match else 0.0
                trades = int(trades_match.group(1)) if trades_match else 0
                
                results.append({
                    'Quarter': quarter_name,
                    'PnL': pnl,
                    'Trades': trades,
                    'Win Rate': win_rate,
                    'Status': '✅'
                })
                
                print(f"✅ PnL: {pnl:>10.2f} | Trades: {trades:>2} | WinRate: {win_rate:>6.2f}%")
            else:
                print(f"❌ ERROR")
                results.append({
                    'Quarter': quarter_name,
                    'PnL': 0.0,
                    'Trades': 0,
                    'Win Rate': 0.0,
                    'Status': '❌ ERROR'
                })
                
        except Exception as e:
            print(f"❌ EXCEPTION: {str(e)[:50]}")
            results.append({
                'Quarter': quarter_name,
                'PnL': 0.0,
                'Trades': 0,
                'Win Rate': 0.0,
                'Status': f'❌ {str(e)[:20]}'
            })
    
    return results

def main():
    """
    メイン実行関数：3シナリオのテストを順番に実行
    """
    
    # 3つのフィルター設定シナリオ
    scenarios = [
        {
            'name': 'シナリオ 1: PVO フィルターのみ (PVO > 0)',
            'settings': {
                'enable_pvo_filter': '1',
                'enable_adx_filter': '0',
            }
        },
        {
            'name': 'シナリオ 2: ADX フィルターのみ (ADX > 70)',
            'settings': {
                'enable_pvo_filter': '0',
                'enable_adx_filter': '1',
            }
        },
        {
            'name': 'シナリオ 3: PVO AND ADX フィルター両方',
            'settings': {
                'enable_pvo_filter': '1',
                'enable_adx_filter': '1',
            }
        },
    ]
    
    all_results = {}
    
    print("\n" + "="*100)
    print("🔬 フィルター効果検証：3シナリオの比較テスト")
    print("="*100)
    print(f"実行時刻: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"対象期間: Q1 2024 - Q4 2025 (8四半期)")
    print()
    
    # 各シナリオを実行
    for scenario in scenarios:
        results = run_backtest_for_quarters(scenario)
        all_results[scenario['name']] = pd.DataFrame(results)
    
    # 結果比較レポートを生成
    print_comparison_report(all_results)
    
    # JSON形式で詳細結果を保存
    save_results_to_file(all_results)

def print_comparison_report(all_results):
    """
    3シナリオの結果を比較レポートで表示
    """
    print("\n\n" + "="*150)
    print("📊 フィルター効果比較レポート")
    print("="*150)
    
    # 各シナリオのサマリー統計を表示
    for scenario_name, df in all_results.items():
        if df.empty:
            continue
            
        print(f"\n{scenario_name}")
        print("-" * 150)
        
        # テーブル表示
        print(df[['Quarter', 'PnL', 'Trades', 'Win Rate']].to_string(index=False))
        
        # 統計値
        print(f"\n統計:")
        print(f"  総損益: {df['PnL'].sum():>10.2f} USD")
        print(f"  平均PnL: {df['PnL'].mean():>10.2f} USD")
        print(f"  総トレード数: {df['Trades'].sum():>3} 回")
        print(f"  平均勝率: {df['Win Rate'].mean():>6.2f}%")
        print(f"  最大損失: {df['PnL'].min():>10.2f} USD")
        print(f"  最大利益: {df['PnL'].max():>10.2f} USD")
    
    # 横並び比較
    print("\n\n" + "="*150)
    print("🔄 四半期別 PnL 比較")
    print("="*150)
    
    comparison_df = pd.DataFrame()
    for scenario_name, df in all_results.items():
        scenario_short = scenario_name.split(':')[0]  # "シナリオ N" のみ抽出
        comparison_df[scenario_short] = df.set_index('Quarter')['PnL']
    
    print(comparison_df.to_string())
    
    # 改善率の計算
    print("\n\n" + "="*150)
    print("📈 改善率の計算（シナリオ3 vs シナリオ1,2 の比較）")
    print("="*150)
    
    if len(all_results) >= 3:
        scenarios_list = list(all_results.items())
        baseline1 = scenarios_list[0][1]  # シナリオ1
        baseline2 = scenarios_list[1][1]  # シナリオ2
        combined = scenarios_list[2][1]   # シナリオ3
        
        print(f"\n{'Quarter':<12} {'Scenario1':<12} {'Scenario2':<12} {'Scenario3':<12} {'vs Scenario1':<15} {'vs Scenario2':<15}")
        print("-" * 150)
        
        for q in baseline1['Quarter']:
            s1_pnl = baseline1[baseline1['Quarter'] == q]['PnL'].values[0]
            s2_pnl = baseline2[baseline2['Quarter'] == q]['PnL'].values[0]
            s3_pnl = combined[combined['Quarter'] == q]['PnL'].values[0]
            
            improvement1 = ((s3_pnl - s1_pnl) / abs(s1_pnl) * 100) if s1_pnl != 0 else 0
            improvement2 = ((s3_pnl - s2_pnl) / abs(s2_pnl) * 100) if s2_pnl != 0 else 0
            
            print(f"{q:<12} {s1_pnl:>11.2f} {s2_pnl:>11.2f} {s3_pnl:>11.2f} {improvement1:>14.1f}% {improvement2:>14.1f}%")
        
        # 総計での改善率
        s1_total = baseline1['PnL'].sum()
        s2_total = baseline2['PnL'].sum()
        s3_total = combined['PnL'].sum()
        
        improvement1_total = ((s3_total - s1_total) / abs(s1_total) * 100) if s1_total != 0 else 0
        improvement2_total = ((s3_total - s2_total) / abs(s2_total) * 100) if s2_total != 0 else 0
        
        print("-" * 150)
        print(f"{'合計':<12} {s1_total:>11.2f} {s2_total:>11.2f} {s3_total:>11.2f} {improvement1_total:>14.1f}% {improvement2_total:>14.1f}%")

def save_results_to_file(all_results):
    """
    結果をJSONファイルに保存
    """
    output_path = Path('docs/analysis/filter_scenario_comparison.json')
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # DataFrameをdict形式に変換
    results_dict = {
        name: df.to_dict('records')
        for name, df in all_results.items()
    }
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results_dict, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ 詳細結果を保存: {output_path}")

if __name__ == '__main__':
    main()
