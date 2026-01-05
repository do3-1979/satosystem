#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_comprehensive_backtest.py

2024/01/01 ～ 2025/09/30 の期間すべてをバックテストして、
統合トレード分析を実行します。

戦略：config.ini を一度だけ更新して、全期間バックテストを実行
"""

import os
import sys
import subprocess
from pathlib import Path
from datetime import datetime

workspace_root = str(Path(__file__).parent.parent)
src_dir = os.path.join(workspace_root, 'src')
config_file = os.path.join(src_dir, 'config.ini')


def update_config_full_period():
    """config.ini を全期間（2024/Q1～2025/Q3）に更新"""
    print(f"🔧 config.ini を更新中...")
    
    start_str = "2024/01/01 00:00"
    end_str = "2025/09/30 23:59"
    
    with open(config_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    new_lines = []
    in_period = False
    
    for line in lines:
        if '[Period]' in line:
            in_period = True
            new_lines.append(line)
        elif line.strip().startswith('[') and in_period:
            in_period = False
            new_lines.append(line)
        elif in_period and 'start_time' in line:
            new_lines.append(f"start_time = {start_str}\n")
        elif in_period and 'end_time' in line:
            new_lines.append(f"end_time = {end_str}\n")
        else:
            new_lines.append(line)
    
    with open(config_file, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)
    
    print(f"  ✓ 更新完了: {start_str} ～ {end_str}")


def run_comprehensive_backtest():
    """総合バックテスト実行"""
    print(f"\n🚀 総合バックテスト実行開始")
    print(f"{'='*80}")
    print(f"期間: 2024/01/01 ～ 2025/09/30 (9 quarters)")
    print(f"{'='*80}\n")
    
    os.chdir(src_dir)
    
    try:
        result = subprocess.run(
            ['python3', 'bot.py'],
            timeout=1800,  # 30分でタイムアウト
        )
        
        if result.returncode == 0:
            print(f"\n✅ バックテスト完了")
        else:
            print(f"\n⚠️  バックテスト終了コード: {result.returncode}")
        
    except subprocess.TimeoutExpired:
        print(f"\n⚠️  バックテストがタイムアウト（30分以上）")
    except Exception as e:
        print(f"\n❌ エラー: {e}")


def main():
    """メイン処理"""
    print("\n📊 総合バックテスト実行ツール")
    print(f"{'='*80}\n")
    
    # config.ini 更新
    update_config_full_period()
    
    # バックテスト実行
    run_comprehensive_backtest()
    
    print(f"\n💡 次のステップ:")
    print(f"   python3 tools/aggregate_backtest_logs.py")
    print(f"   python3 tools/trade_analyzer.py")


if __name__ == '__main__':
    main()
