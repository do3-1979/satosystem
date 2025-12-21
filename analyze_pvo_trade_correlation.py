#!/usr/bin/env python3
"""
バー単位のPVO値と、トレード成績の関係を分析

最新のバックテストログ（JSON）から：
1. 各トレードのエントリー時PVO値を抽出
2. トレード結果（勝ち/負け）を判定
3. PVO値の分布を比較
"""

import os
import json
import sys
from datetime import datetime

SRC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src')
LOGS_DIR = os.path.join(SRC_DIR, 'logs')

def get_latest_backtest_log():
    """最新のバックテストログを取得"""
    if not os.path.exists(LOGS_DIR):
        print(f"❌ ログディレクトリが見つかりません: {LOGS_DIR}")
        return None
    
    log_files = [f for f in os.listdir(LOGS_DIR) if f.endswith('.json') and not f.startswith('backtest_summary')]
    
    if not log_files:
        print(f"❌ バックテストログが見つかりません")
        return None
    
    # タイムスタンプでソート
    latest_log = max(log_files, key=lambda x: os.path.getctime(os.path.join(LOGS_DIR, x)))
    
    log_path = os.path.join(LOGS_DIR, latest_log)
    print(f"📖 最新ログを読み込み: {latest_log}")
    
    try:
        with open(log_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data
    except Exception as e:
        print(f"❌ ログ読み込みエラー: {e}")
        return None

def extract_trades_with_pvo(log_data):
    """
    ログデータからトレード情報を抽出
    
    Returns:
        list: トレード情報 [{'entry_pvo': float, 'pnl': float, 'side': str}, ...]
    """
    trades = []
    
    if not isinstance(log_data, list):
        print(f"❌ ログ形式が不正です（期待: list型）")
        return trades
    
    for entry in log_data:
        # 各エントリーは以下の情報を含む:
        # - pvo_value_at_entry: エントリー時のPVO値
        # - pnl: トレード結果（USD）
        # - side: BUY or SELL
        
        if 'pvo_value_at_entry' in entry and 'pnl' in entry:
            trades.append({
                'entry_pvo': entry.get('pvo_value_at_entry', 0),
                'pnl': entry.get('pnl', 0),
                'side': entry.get('side', 'UNKNOWN'),
                'timestamp': entry.get('timestamp', ''),
            })
    
    return trades

def analyze_pvo_vs_trades(trades):
    """
    トレード結果とエントリー時PVO値の関係を分析
    """
    if not trades:
        print(f"\n❌ トレード情報が取得できませんでした")
        return
    
    # 勝ち負けで分類
    winning_trades = [t for t in trades if t['pnl'] > 0]
    losing_trades = [t for t in trades if t['pnl'] < 0]
    
    print(f"\n" + "="*80)
    print(f"📊 トレード成績とPVO値の関係分析")
    print(f"="*80)
    
    print(f"\n📈 全トレード統計:")
    print(f"  - 総トレード数: {len(trades)}")
    print(f"  - 勝ちトレード: {len(winning_trades)} 件")
    print(f"  - 負けトレード: {len(losing_trades)} 件")
    
    if winning_trades:
        winning_pvos = [t['entry_pvo'] for t in winning_trades]
        print(f"\n✅ 勝ちトレード時のPVO値:")
        print(f"  - 件数: {len(winning_pvos)}")
        print(f"  - 平均: {sum(winning_pvos)/len(winning_pvos):.2f}")
        print(f"  - 最小: {min(winning_pvos):.2f}")
        print(f"  - 最大: {max(winning_pvos):.2f}")
        print(f"  - 値リスト: {sorted(winning_pvos)}")
    
    if losing_trades:
        losing_pvos = [t['entry_pnl'] for t in losing_trades]
        print(f"\n❌ 負けトレード時のPVO値:")
        print(f"  - 件数: {len(losing_pvos)}")
        print(f"  - 平均: {sum(losing_pvos)/len(losing_pvos):.2f}")
        print(f"  - 最小: {min(losing_pvos):.2f}")
        print(f"  - 最大: {max(losing_pvos):.2f}")
        print(f"  - 値リスト: {sorted(losing_pvos)}")
    
    # 前回の分析との比較
    print(f"\n⚠️  前回の分析との比較:")
    print(f"  前回: 四半期ベースで Sharpe 値を使用")
    print(f"    - PVO > 0 でフィルター → 1361.91 USD（推定）")
    print(f"    - 負けトレード 0 件で除外")
    print(f"\n  実際: バー単位のPVO値を使用")
    print(f"    - PVO > 20 でフィルター → 904.35 USD（実運用）")
    print(f"    - フィルター効果なし")
    
    # 仮説
    print(f"\n💡 仮説:")
    print(f"  1. 前回のPVO（四半期Sharpe値）と現在のPVO（バー単位）が異なる指標")
    print(f"  2. バー単位のPVO値には、トレード勝敗と相関がない可能性")
    print(f"  3. 四半期レベルのシグナルとバー単位のシグナルの粒度差")

if __name__ == '__main__':
    log_data = get_latest_backtest_log()
    if log_data:
        trades = extract_trades_with_pvo(log_data)
        analyze_pvo_vs_trades(trades)
    else:
        print("\n" + "="*80)
        print("⚠️  バックテストログから直接データを抽出する必要があります")
        print("="*80)
        print("\n代替案:")
        print("  1. backtest.py のログ出力フォーマットを確認")
        print("  2. 各トレードのエントリー時PVO値を記録するよう修正")
        print("  3. トレード勝敗情報を JSON ログに追加")
