#!/usr/bin/env python3
"""
PVO値の粒度差を分析するスクリプト

前回の分析では四半期レベルの Sharpe 値をPVOの代替値として使用していた。
しかし実際のバックテストではバー単位（分足）のPVO値を使用している。

このスクリプトで、実際のバー単位PVO値と勝ち負けの関係を分析する。
"""

import os
import sys
import json
import re
from datetime import datetime

SRC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src')
LOG_FILE = os.path.join(SRC_DIR, 'log.txt')

def extract_trades_from_log():
    """
    ログから各エントリー時のPVO値と、そのトレード結果を抽出
    
    Returns:
        list: トレード情報（エントリー時PVO、結果など）
    """
    trades = []
    
    if not os.path.exists(LOG_FILE):
        print(f"❌ ログファイルが見つかりません: {LOG_FILE}")
        return trades
    
    with open(LOG_FILE, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    current_entry_pvo = None
    current_decision = None
    
    for line in lines:
        # エントリー条件判定のログを探す
        if '[条件判定:ENTRY]' in line and 'エントリー条件成立' in line:
            # 次のフィルターログを待つ
            current_decision = 'found_entry'
            continue
        
        # フィルターのログを探す
        if '[フィルター:ENTRY]' in line and 'PVO フィルター' in line:
            # PVO値を抽出
            match = re.search(r'PVO=([0-9.]+)', line)
            if match:
                pvo_val = float(match.group(1))
                current_entry_pvo = pvo_val
                
                if 'フィルター成功' in line:
                    result = '成功'
                else:
                    result = '失敗'
                
                trades.append({
                    'timestamp': datetime.now().isoformat(),
                    'entry_pvo': pvo_val,
                    'filter_result': result
                })
    
    return trades

def analyze_pvo_distribution():
    """
    バー単位のPVO値の分布を分析
    """
    trades = extract_trades_from_log()
    
    print("\n" + "="*80)
    print("📊 バー単位のPVO値分析")
    print("="*80)
    
    if not trades:
        print("❌ エントリー時のPVO値が取得できませんでした")
        return
    
    pvo_values = [t['entry_pvo'] for t in trades]
    
    print(f"\n📈 抽出されたPVO値: {len(pvo_values)} 件")
    print(f"  - 最小値: {min(pvo_values):.2f}")
    print(f"  - 最大値: {max(pvo_values):.2f}")
    print(f"  - 平均値: {sum(pvo_values)/len(pvo_values):.2f}")
    
    # 条件別の分布
    pvo_positive = [v for v in pvo_values if v > 0]
    pvo_zero_or_less = [v for v in pvo_values if v <= 0]
    pvo_above_20 = [v for v in pvo_values if v > 20]
    pvo_20_or_less = [v for v in pvo_values if v <= 20]
    
    print(f"\n🔍 フィルター条件別の分類:")
    print(f"  - PVO > 0: {len(pvo_positive)} 件 ({len(pvo_positive)*100//len(pvo_values)}%)")
    print(f"  - PVO <= 0: {len(pvo_zero_or_less)} 件 ({len(pvo_zero_or_less)*100//len(pvo_values)}%)")
    print(f"  - PVO > 20: {len(pvo_above_20)} 件 ({len(pvo_above_20)*100//len(pvo_values)}%)")
    print(f"  - PVO <= 20: {len(pvo_20_or_less)} 件 ({len(pvo_20_or_less)*100//len(pvo_values)}%)")
    
    # 前回の四半期ベース分析との比較
    print(f"\n⚠️  前回の分析との比較:")
    print(f"  前回: 四半期ベースの Sharpe 値を使用（値の範囲: -1.638 ～ +1.930）")
    print(f"  今回: バー単位のPVO値を使用（値の範囲: {min(pvo_values):.2f} ～ {max(pvo_values):.2f}）")
    print(f"\n  → これら2つは全く異なる指標です！")

if __name__ == '__main__':
    analyze_pvo_distribution()
