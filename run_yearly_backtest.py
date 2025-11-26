#!/usr/bin/env python3
"""
2024年通年 + 2025年1/1～11/24 バックテスト実行スクリプト
"""

import os
import sys
import subprocess
import json
from datetime import datetime
from pathlib import Path

def run_backtest(config_file):
    """backtest.py を実行"""
    print(f"\n{'=' * 80}")
    print(f"🔄 実行中: {os.path.basename(config_file)}")
    print(f"{'=' * 80}")
    
    try:
        result = subprocess.run(
            [sys.executable, 'src/backtest.py', config_file],
            cwd=os.path.dirname(os.path.abspath(__file__)),
            capture_output=True,
            text=True,
            timeout=300
        )
        
        if result.returncode == 0:
            print(f"✅ 実行成功")
            return True
        else:
            print(f"❌ 実行失敗")
            if result.stderr:
                print(f"Error: {result.stderr[-200:]}")
            return False
    except Exception as e:
        print(f"❌ エラー: {str(e)}")
        return False

def extract_summary(report_dir):
    """最新のバックテスト結果を抽出"""
    summary_files = sorted(
        Path(report_dir).glob('backtest_summary_*.json'),
        reverse=True
    )
    
    if not summary_files:
        return None
    
    try:
        with open(summary_files[0], 'r') as f:
            return json.load(f)
    except:
        return None

def main():
    repo_root = os.path.dirname(os.path.abspath(__file__))
    output_configs_dir = os.path.join(repo_root, 'output_configs')
    report_dir = os.path.join(repo_root, 'report')
    
    # 2024年と2025年の config ファイルを取得
    configs_2024 = sorted([
        os.path.join(output_configs_dir, f)
        for f in os.listdir(output_configs_dir)
        if '2024' in f and 'baseline' in f
    ])
    
    configs_2025 = sorted([
        os.path.join(output_configs_dir, f)
        for f in os.listdir(output_configs_dir)
        if '2025' in f and 'baseline' in f
    ])
    
    print("=" * 80)
    print("📊 年間バックテスト実行")
    print("=" * 80)
    print(f"\n2024年 config ファイル: {len(configs_2024)}")
    for cfg in configs_2024:
        print(f"  - {os.path.basename(cfg)}")
    
    print(f"\n2025年 config ファイル: {len(configs_2025)}")
    for cfg in configs_2025:
        print(f"  - {os.path.basename(cfg)}")
    
    # 2024年実行
    print("\n" + "=" * 80)
    print("📅 2024年通年 バックテスト開始")
    print("=" * 80)
    
    results_2024 = []
    for config_file in configs_2024:
        if run_backtest(config_file):
            summary = extract_summary(report_dir)
            if summary:
                results_2024.append({
                    'config': os.path.basename(config_file),
                    'pnl': summary.get('total_pnl', 0),
                    'win_rate': summary.get('win_rate', 0),
                    'max_dd': summary.get('max_dd', 0),
                    'sharpe': summary.get('sharpe_ratio', 0),
                })
    
    # 2025年実行
    print("\n" + "=" * 80)
    print("📅 2025年1/1～11/24 バックテスト開始")
    print("=" * 80)
    
    results_2025 = []
    for config_file in configs_2025:
        if run_backtest(config_file):
            summary = extract_summary(report_dir)
            if summary:
                results_2025.append({
                    'config': os.path.basename(config_file),
                    'pnl': summary.get('total_pnl', 0),
                    'win_rate': summary.get('win_rate', 0),
                    'max_dd': summary.get('max_dd', 0),
                    'sharpe': summary.get('sharpe_ratio', 0),
                })
    
    # 結果表示
    print("\n" + "=" * 80)
    print("📊 バックテスト結果サマリー")
    print("=" * 80)
    
    print("\n2024年通年:")
    if results_2024:
        for result in results_2024:
            print(f"  {result['config']}")
            print(f"    PnL: {result['pnl']:>10.2f} | WinRate: {result['win_rate']:>6.2f}% | MaxDD: {result['max_dd']:>8.2f} | Sharpe: {result['sharpe']:>6.3f}")
        
        avg_pnl_2024 = sum(r['pnl'] for r in results_2024) / len(results_2024)
        avg_wr_2024 = sum(r['win_rate'] for r in results_2024) / len(results_2024)
        print(f"\n  📈 2024年平均: PnL={avg_pnl_2024:>10.2f} | WinRate={avg_wr_2024:>6.2f}%")
    else:
        print("  ❌ 結果なし")
    
    print("\n2025年1/1～11/24:")
    if results_2025:
        for result in results_2025:
            print(f"  {result['config']}")
            print(f"    PnL: {result['pnl']:>10.2f} | WinRate: {result['win_rate']:>6.2f}% | MaxDD: {result['max_dd']:>8.2f} | Sharpe: {result['sharpe']:>6.3f}")
        
        avg_pnl_2025 = sum(r['pnl'] for r in results_2025) / len(results_2025)
        avg_wr_2025 = sum(r['win_rate'] for r in results_2025) / len(results_2025)
        print(f"\n  📈 2025年平均: PnL={avg_pnl_2025:>10.2f} | WinRate={avg_wr_2025:>6.2f}%")
    else:
        print("  ❌ 結果なし")
    
    # 年間比較
    if results_2024 and results_2025:
        print("\n" + "=" * 80)
        print("🔍 2024年 vs 2025年 比較")
        print("=" * 80)
        
        avg_pnl_2024 = sum(r['pnl'] for r in results_2024) / len(results_2024)
        avg_pnl_2025 = sum(r['pnl'] for r in results_2025) / len(results_2025)
        
        print(f"\n平均 PnL:")
        print(f"  2024年: {avg_pnl_2024:>10.2f}")
        print(f"  2025年: {avg_pnl_2025:>10.2f}")
        print(f"  差分:   {avg_pnl_2025 - avg_pnl_2024:>+10.2f} ({((avg_pnl_2025 - avg_pnl_2024) / avg_pnl_2024 * 100) if avg_pnl_2024 != 0 else 0:>+6.2f}%)")
    
    print("\n✅ バックテスト完了")

if __name__ == '__main__':
    main()
