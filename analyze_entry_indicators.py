#!/usr/bin/env python3
"""
各エントリー時の指標抽出・勝敗分析スクリプト

ログから以下の情報を抽出：
  1. エントリー時刻（decision = 'ENTRY'）
  2. そのエントリーに対応するエグジット（decision = 'EXIT'）
  3. エントリー時の指標: Volatility, PVO, ADX, Volume
  4. トレード成績（勝ち/負け）
  5. 比較分析
"""

import os
import json
import numpy as np
import pandas as pd
from pathlib import Path

SRC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src')
LOGS_DIR = os.path.join(SRC_DIR, 'logs')

def get_latest_backtest_log():
    """最新のバックテストログを取得"""
    if not os.path.exists(LOGS_DIR):
        return None
    
    log_files = [f for f in os.listdir(LOGS_DIR) if f.endswith('.json') and not f.startswith('backtest_summary')]
    if not log_files:
        return None
    
    latest_log = max(log_files, key=lambda x: os.path.getctime(os.path.join(LOGS_DIR, x)))
    log_path = os.path.join(LOGS_DIR, latest_log)
    
    with open(log_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def extract_entry_trades(log_data):
    """
    エントリー時の指標とトレード成績を抽出
    
    Returns:
        list: トレード情報
        [
            {
                'entry_idx': int,
                'entry_time': str,
                'side': str,
                'entry_volatility': float,
                'entry_pvo': float,
                'entry_adx': float,
                'entry_volume': float,
                'exit_idx': int,
                'exit_time': str,
                'trade_pnl': float,
                'pnl_pct': float,
            },
            ...
        ]
    """
    trades = []
    
    # エントリーとエグジットのインデックスを取得
    entries = [(i, e) for i, e in enumerate(log_data) if e.get('decision') == 'ENTRY']
    exits = [(i, e) for i, e in enumerate(log_data) if e.get('decision') == 'EXIT']
    
    if not entries or not exits:
        return trades
    
    # エントリーと対応するエグジットをペアリング
    for entry_num, (entry_idx, entry) in enumerate(entries):
        if entry_num >= len(exits):
            break
        
        exit_idx, exit_data = exits[entry_num]
        
        # エントリーのPnL（前のバー）
        entry_pnl_before = log_data[entry_idx - 1]['total_profit_and_loss'] if entry_idx > 0 else 0
        
        # エグジットのPnL
        exit_pnl = exit_data.get('total_profit_and_loss', 0)
        
        # トレード成績
        trade_pnl = exit_pnl - entry_pnl_before
        
        trades.append({
            'entry_idx': entry_idx,
            'entry_time': entry.get('close_time_dt', ''),
            'side': entry.get('side', 'UNKNOWN'),
            'entry_volatility': entry.get('volatility', 0),
            'entry_pvo': entry.get('pvo_val', 0),
            'entry_adx': entry.get('adx', 0),
            'entry_volume': entry.get('Volume', 0),
            'exit_idx': exit_idx,
            'exit_time': exit_data.get('close_time_dt', ''),
            'trade_pnl': trade_pnl,
        })
    
    return trades

def analyze_trades(trades):
    """
    トレードを勝敗で分析
    """
    if not trades:
        print("❌ トレードデータが取得できませんでした")
        return
    
    # 勝敗で分類
    winning_trades = [t for t in trades if t['trade_pnl'] > 0]
    losing_trades = [t for t in trades if t['trade_pnl'] < 0]
    
    print("\n" + "="*100)
    print("📊 エントリー時の指標分析（勝敗比較）")
    print("="*100)
    
    print(f"\n📈 トレード統計:")
    print(f"  - 総トレード数: {len(trades)}")
    print(f"  - 勝ちトレード: {len(winning_trades)} 件")
    print(f"  - 負けトレード: {len(losing_trades)} 件")
    print(f"  - 総損益: {sum(t['trade_pnl'] for t in trades):.2f} USD")
    
    # 各指標の比較
    metrics = ['entry_volatility', 'entry_pvo', 'entry_adx', 'entry_volume']
    metric_names = ['Volatility', 'PVO', 'ADX', 'Volume']
    
    print("\n" + "-"*100)
    print("🔍 指標別比較（平均値）")
    print("-"*100)
    
    for metric, metric_name in zip(metrics, metric_names):
        if winning_trades and losing_trades:
            win_avg = np.mean([t[metric] for t in winning_trades])
            lose_avg = np.mean([t[metric] for t in losing_trades])
            diff_pct = ((win_avg - lose_avg) / abs(lose_avg) * 100) if lose_avg != 0 else 0
            
            print(f"\n{metric_name}:")
            print(f"  ✅ 勝ちトレード: {win_avg:10.2f}")
            print(f"  ❌ 負けトレード: {lose_avg:10.2f}")
            print(f"  📊 差分: {win_avg - lose_avg:+10.2f} ({diff_pct:+.1f}%)")
            
            # 相関判定
            if win_avg > lose_avg:
                print(f"  → 勝ちトレードで値が高い（フィルター有効の可能性）")
            else:
                print(f"  → 負けトレードで値が高い（フィルター逆効果の可能性）")
    
    # 詳細データをCSV形式で出力
    print("\n" + "-"*100)
    print("📋 詳細データ（全トレード一覧）")
    print("-"*100)
    
    df = pd.DataFrame(trades)
    print(f"\n{'結果':<5} {'時刻':<20} {'V.vol':<8} {'PVO':<8} {'ADX':<8} {'Vol':<10} {'PnL':<10}")
    print("-" * 100)
    
    for _, trade in df.iterrows():
        result = "✅" if trade['trade_pnl'] > 0 else "❌"
        print(f"{result:<5} {trade['entry_time']:<20} {trade['entry_volatility']:>7.2f} {trade['entry_pvo']:>7.2f} {trade['entry_adx']:>7.2f} {trade['entry_volume']:>9.0f} {trade['trade_pnl']:>9.2f}")
    
    # CSVファイルに保存
    output_file = os.path.join(os.path.dirname(__file__), 'entry_indicators_analysis.csv')
    df.to_csv(output_file, index=False, encoding='utf-8')
    print(f"\n💾 詳細データを CSV に保存: {output_file}")

def main():
    log_data = get_latest_backtest_log()
    
    if not log_data:
        print("❌ バックテストログが見つかりません")
        return
    
    trades = extract_entry_trades(log_data)
    analyze_trades(trades)

if __name__ == '__main__':
    main()
