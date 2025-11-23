#!/usr/bin/env python3
"""
高速サマリモードで実行した4つのQ1バックテスト結果を集計・分析するスクリプト
適応型 vs ベースライン、2024 vs 2025 での有用性を評価
"""

import json
import os
from datetime import datetime
import sys

def extract_backtest_metrics(report_dir):
    """バックテストレポートディレクトリからメトリクスを抽出"""
    try:
        # backtest_summary_*.json を探す
        files = [f for f in os.listdir(report_dir) if f.startswith('backtest_summary_') and f.endswith('.json')]
        if not files:
            print(f"警告: {report_dir} にバックテストサマリが見つかりません")
            return None
        
        summary_file = os.path.join(report_dir, files[0])
        with open(summary_file, 'r', encoding='utf-8') as f:
            metrics = json.load(f)
        
        return metrics
    except Exception as e:
        print(f"エラー: {report_dir} からメトリクス抽出失敗: {e}")
        return None

def analyze_results():
    """4つのバックテスト結果を分析"""
    
    test_configs = [
        ("adaptive_2024_q1", "適応型 2024 Q1", "report"),
        ("baseline_2024_q1", "ベースライン 2024 Q1", "report"),
        ("adaptive_2025_q1", "適応型 2025 Q1", "report"),
        ("baseline_2025_q1", "ベースライン 2025 Q1", "report"),
    ]
    
    results = {}
    
    for config_name, display_name, report_base in test_configs:
        report_dir = os.path.join(report_base)
        # 最新のバックテストレポートを探す
        if os.path.exists(report_dir):
            metrics = extract_backtest_metrics(report_dir)
            results[config_name] = {
                'name': display_name,
                'metrics': metrics
            }
        else:
            print(f"警告: {report_dir} が見つかりません")
    
    # 結果を表示
    print("\n" + "="*80)
    print("【高速サマリモード Q1バックテスト結果集計】")
    print("="*80)
    
    # ヘッダ
    print(f"\n{'テスト名':<25} {'Total PnL':<15} {'Max DD':<15} {'Win Rate':<15}")
    print("-"*70)
    
    for config_name, result_data in results.items():
        display_name = result_data['name']
        metrics = result_data['metrics']
        
        if metrics is None:
            print(f"{display_name:<25} {'N/A':<15} {'N/A':<15} {'N/A':<15}")
            continue
        
        # メトリクスから重要な値を抽出
        total_pnl = metrics.get('total_pnl', 'N/A')
        max_dd = metrics.get('max_drawdown', 'N/A')
        win_rate = metrics.get('win_rate', 'N/A')
        
        # フォーマット
        pnl_str = f"${total_pnl:.2f}" if isinstance(total_pnl, (int, float)) else str(total_pnl)
        dd_str = f"{max_dd:.2f}%" if isinstance(max_dd, (int, float)) else str(max_dd)
        wr_str = f"{win_rate:.1f}%" if isinstance(win_rate, (int, float)) else str(win_rate)
        
        print(f"{display_name:<25} {pnl_str:<15} {dd_str:<15} {wr_str:<15}")
    
    # 比較分析
    print("\n" + "="*80)
    print("【比較分析】")
    print("="*80)
    
    # 2024: 適応型 vs ベースライン
    if 'adaptive_2024_q1' in results and 'baseline_2024_q1' in results:
        adaptive_2024 = results['adaptive_2024_q1']['metrics']
        baseline_2024 = results['baseline_2024_q1']['metrics']
        
        if adaptive_2024 and baseline_2024:
            adaptive_pnl = adaptive_2024.get('total_pnl', 0)
            baseline_pnl = baseline_2024.get('total_pnl', 0)
            diff = adaptive_pnl - baseline_pnl
            
            print(f"\n【2024 Q1: 適応型 vs ベースライン】")
            print(f"  適応型 PnL:    ${adaptive_pnl:.2f}")
            print(f"  ベースラインPnL: ${baseline_pnl:.2f}")
            print(f"  差分（適応型有利）: ${diff:+.2f}")
            if baseline_pnl != 0:
                pct_improvement = (diff / abs(baseline_pnl)) * 100
                print(f"  改善率: {pct_improvement:+.1f}%")
    
    # 2025: 適応型 vs ベースライン
    if 'adaptive_2025_q1' in results and 'baseline_2025_q1' in results:
        adaptive_2025 = results['adaptive_2025_q1']['metrics']
        baseline_2025 = results['baseline_2025_q1']['metrics']
        
        if adaptive_2025 and baseline_2025:
            adaptive_pnl = adaptive_2025.get('total_pnl', 0)
            baseline_pnl = baseline_2025.get('total_pnl', 0)
            diff = adaptive_pnl - baseline_pnl
            
            print(f"\n【2025 Q1: 適応型 vs ベースライン】")
            print(f"  適応型 PnL:    ${adaptive_pnl:.2f}")
            print(f"  ベースラインPnL: ${baseline_pnl:.2f}")
            print(f"  差分（適応型有利）: ${diff:+.2f}")
            if baseline_pnl != 0:
                pct_improvement = (diff / abs(baseline_pnl)) * 100
                print(f"  改善率: {pct_improvement:+.1f}%")
    
    # 2024 vs 2025: 全体市場環境の影響
    if 'adaptive_2024_q1' in results and 'adaptive_2025_q1' in results:
        adaptive_2024 = results['adaptive_2024_q1']['metrics']
        adaptive_2025 = results['adaptive_2025_q1']['metrics']
        
        if adaptive_2024 and adaptive_2025:
            pnl_2024 = adaptive_2024.get('total_pnl', 0)
            pnl_2025 = adaptive_2025.get('total_pnl', 0)
            
            print(f"\n【適応型: 2024 Q1 vs 2025 Q1（市場環境の影響）】")
            print(f"  2024 Q1 PnL: ${pnl_2024:.2f}")
            print(f"  2025 Q1 PnL: ${pnl_2025:.2f}")
            print(f"  YoY変化: ${pnl_2025 - pnl_2024:+.2f}")
    
    # 詳細メトリクス出力
    print("\n" + "="*80)
    print("【詳細メトリクス】")
    print("="*80)
    
    for config_name, result_data in results.items():
        display_name = result_data['name']
        metrics = result_data['metrics']
        
        if metrics:
            print(f"\n{display_name}")
            print(f"  Total PnL: ${metrics.get('total_pnl', 'N/A')}")
            print(f"  Total Trades: {metrics.get('total_trades', 'N/A')}")
            print(f"  Winning Trades: {metrics.get('winning_trades', 'N/A')}")
            print(f"  Losing Trades: {metrics.get('losing_trades', 'N/A')}")
            print(f"  Win Rate: {metrics.get('win_rate', 'N/A')}")
            print(f"  Max Drawdown: {metrics.get('max_drawdown', 'N/A')}")
            print(f"  Avg Win: ${metrics.get('avg_win', 'N/A')}")
            print(f"  Avg Loss: ${metrics.get('avg_loss', 'N/A')}")
            print(f"  Profit Factor: {metrics.get('profit_factor', 'N/A')}")
            
            # レジーム統計
            regime_stats = metrics.get('regime_stats', {})
            if regime_stats:
                print(f"\n  【レジーム統計】")
                for regime_name, stat_data in regime_stats.items():
                    if isinstance(stat_data, dict):
                        print(f"    {regime_name}:")
                        for stat_key, stat_val in stat_data.items():
                            print(f"      {stat_key}: {stat_val}")
    
    print("\n" + "="*80)
    print(f"分析完了時刻: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80 + "\n")

if __name__ == "__main__":
    analyze_results()
