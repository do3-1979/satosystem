#!/usr/bin/env python3
"""
フィルター効果比較スクリプト：3シナリオの検証
各四半期でPVO/ADXフィルターの効果を測定

シナリオ：
  1. PVO フィルターのみ (enable_pvo_filter=1, enable_adx_filter=0)
  2. ADX フィルターのみ (enable_pvo_filter=0, enable_adx_filter=1)
  3. PVO + ADX 両方 (enable_pvo_filter=1, enable_adx_filter=1)

使用方法:
  python run_filter_comparison.py
"""

import os
import sys
import json
import time
import subprocess
from configparser import ConfigParser
from datetime import datetime
import pandas as pd

WORKSPACE_ROOT = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(WORKSPACE_ROOT, 'src', 'config.ini')
LOG_DIR = os.path.join(WORKSPACE_ROOT, 'src', 'logs')  # src/logs に生成される

def read_original_config():
    """元の設定を読み込む"""
    config = ConfigParser()
    config.read(CONFIG_FILE, encoding='utf-8')
    return config

def write_config(config):
    """設定を書き込む"""
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        config.write(f)

def run_quarterly_backtest(year, quarter, enable_pvo=0, enable_adx=0):
    """
    四半期別バックテストを実行
    
    Args:
        year: 年
        quarter: 四半期 (1-4)
        enable_pvo: PVOフィルター有効フラグ
        enable_adx: ADXフィルター有効フラグ
    
    Returns:
        dict: バックテスト結果
    """
    try:
        # 元の設定を保存
        original_config = read_original_config()
        
        # 設定を修正
        config = ConfigParser()
        config.read(CONFIG_FILE, encoding='utf-8')
        
        # セクションの確保
        if not config.has_section('Backtest'):
            config.add_section('Backtest')
        if not config.has_section('EntryFilters'):
            config.add_section('EntryFilters')
        
        # 四半期の日付範囲を計算
        start_month = (quarter - 1) * 3 + 1
        if quarter == 4:
            end_month = 12
            end_day = 21
        else:
            end_month = start_month + 2
            end_day = 30 if end_month in [4, 6, 9, 11] else 31
        
        start_time = f'{year}-{start_month:02d}-01 00:00'
        end_time = f'{year}-{end_month:02d}-{end_day:02d} 23:59'
        
        config.set('Backtest', 'start_time', start_time)
        config.set('Backtest', 'end_time', end_time)
        config.set('EntryFilters', 'enable_pvo_filter', str(enable_pvo))
        config.set('EntryFilters', 'enable_adx_filter', str(enable_adx))
        
        write_config(config)
        
        # バックテスト実行
        result = subprocess.run(
            ['python', 'backtest.py'],
            cwd=os.path.join(WORKSPACE_ROOT, 'src'),
            capture_output=True,
            text=True,
            timeout=300
        )
        
        # 結果を取得
        if result.returncode != 0:
            write_config(original_config)
            return {
                'status': 'ERROR',
                'pnl': 0,
                'trades': 0,
                'win_rate': 0,
                'error': result.stderr[:100] if result.stderr else 'Unknown'
            }
        
        # ログからデータを取得
        if os.path.exists(LOG_DIR):
            # backtest_summary_*.json を探す（最新のサマリーファイル）
            summary_files = sorted([f for f in os.listdir(LOG_DIR) if f.startswith('backtest_summary_') and f.endswith('.json')], reverse=True)
            if summary_files:
                try:
                    log_path = os.path.join(LOG_DIR, summary_files[0])
                    with open(log_path, 'r', encoding='utf-8') as f:
                        log_data = json.load(f)
                    
                    pnl = log_data.get('total_pnl', 0)
                    trades = log_data.get('trades', 0)
                    win_rate = log_data.get('win_rate', 0)
                    
                    write_config(original_config)
                    return {
                        'status': 'OK',
                        'pnl': pnl,
                        'trades': trades,
                        'win_rate': win_rate
                    }
                except Exception as e:
                    pass
        
        write_config(original_config)
        return {'status': 'NO_LOG', 'pnl': 0, 'trades': 0, 'win_rate': 0}
        
    except subprocess.TimeoutExpired:
        write_config(original_config)
        return {'status': 'TIMEOUT', 'pnl': 0, 'trades': 0, 'win_rate': 0}
    except Exception as e:
        try:
            write_config(original_config)
        except:
            pass
        return {'status': 'ERROR', 'pnl': 0, 'trades': 0, 'win_rate': 0, 'error': str(e)[:50]}

def main():
    """メイン処理"""
    
    quarters = [
        (2024, 1, 'Q1 2024'),
        (2024, 2, 'Q2 2024'),
        (2024, 3, 'Q3 2024'),
        (2024, 4, 'Q4 2024'),
        (2025, 1, 'Q1 2025'),
        (2025, 2, 'Q2 2025'),
        (2025, 3, 'Q3 2025'),
        (2025, 4, 'Q4 2025'),
    ]
    
    scenarios = [
        {'name': 'Scenario 1: PVO Only', 'pvo': 1, 'adx': 0},
        {'name': 'Scenario 2: ADX Only', 'pvo': 0, 'adx': 1},
        {'name': 'Scenario 3: PVO + ADX', 'pvo': 1, 'adx': 1},
    ]
    
    all_results = {}
    
    print("\n" + "="*100)
    print("🔬 フィルター効果検証：3シナリオの比較")
    print("="*100)
    print(f"実行時刻: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # 各シナリオを実行
    for scenario in scenarios:
        print(f"\n{'='*100}")
        print(f"🧪 {scenario['name']}")
        print(f"{'='*100}")
        
        results = []
        
        for year, quarter, quarter_name in quarters:
            print(f"  ⏳ {quarter_name:<10}...", end=' ', flush=True)
            
            result = run_quarterly_backtest(year, quarter, scenario['pvo'], scenario['adx'])
            
            if result['status'] == 'OK':
                pnl = result['pnl']
                trades = result['trades']
                win_rate = result['win_rate']
                print(f"✅ PnL: {pnl:>10.2f} | Trades: {trades:>2} | WR: {win_rate:>6.2f}%")
                results.append({
                    'Quarter': quarter_name,
                    'PnL': pnl,
                    'Trades': trades,
                    'Win Rate': win_rate
                })
            else:
                print(f"❌ {result['status']}")
                results.append({
                    'Quarter': quarter_name,
                    'PnL': 0,
                    'Trades': 0,
                    'Win Rate': 0
                })
            
            time.sleep(1)
        
        df = pd.DataFrame(results)
        all_results[scenario['name']] = df
        
        # サマリー表示
        total = df['PnL'].sum()
        wins = (df['PnL'] > 0).sum()
        losses = (df['PnL'] < 0).sum()
        
        print(f"\n📊 {scenario['name']} サマリー:")
        print(f"   総損益: {total:>10.2f} USD")
        print(f"   勝敗: {wins}W-{losses}L")
    
    # 比較レポート
    print_comparison(all_results)
    
    # 結果を保存
    save_results(all_results)

def print_comparison(all_results):
    """結果の比較を表示"""
    
    print("\n" + "="*100)
    print("📊 四半期別 PnL 比較表")
    print("="*100)
    
    comparison = pd.DataFrame()
    for scenario_name, df in all_results.items():
        short_name = scenario_name.split(':')[0]
        comparison[short_name] = df.set_index('Quarter')['PnL']
    
    print(comparison.to_string())
    
    print("\n" + "="*100)
    print("🎯 シナリオ別 総損益の比較")
    print("="*100)
    
    for scenario_name, df in all_results.items():
        total = df['PnL'].sum()
        avg = df['PnL'].mean()
        wins = (df['PnL'] > 0).sum()
        
        print(f"\n{scenario_name}")
        print(f"  総損益: {total:>10.2f} USD")
        print(f"  平均: {avg:>10.2f} USD/Q")
        print(f"  勝数: {wins}Q")

def save_results(all_results):
    """結果をファイルに保存"""
    
    output_dir = os.path.join(WORKSPACE_ROOT, 'docs', 'analysis')
    os.makedirs(output_dir, exist_ok=True)
    
    # JSON形式で保存
    results_dict = {}
    for scenario_name, df in all_results.items():
        results_dict[scenario_name] = df.to_dict('records')
    
    json_path = os.path.join(output_dir, 'filter_comparison_results.json')
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(results_dict, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ 結果を保存: {json_path}")

if __name__ == '__main__':
    main()
