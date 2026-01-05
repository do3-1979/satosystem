#!/usr/bin/env python3
"""
市場レジーム検出の有効性分析ツール

trade_log_*.jsonを読み込み、レジーム別の勝率・PnL・トレード数を集計。
フィルタリング有効時の仮想結果も算出する。
"""

import json
import sys
from pathlib import Path
from collections import defaultdict
from typing import Dict, List

def analyze_regime_effectiveness(trade_log_path: str) -> Dict:
    """
    トレードログから市場レジーム別の統計を分析
    
    Args:
        trade_log_path: trade_log_*.jsonファイルのパス
    
    Returns:
        レジーム別統計の辞書
    """
    with open(trade_log_path, 'r') as f:
        data = json.load(f)
    
    trades = data.get('trades', [])
    
    # レジーム別の集計
    regime_stats = defaultdict(lambda: {
        'total': 0,
        'wins': 0,
        'losses': 0,
        'total_pnl': 0.0,
        'win_pnl': 0.0,
        'loss_pnl': 0.0,
        'trades': []
    })
    
    # 全体統計
    overall_stats = {
        'total': 0,
        'wins': 0,
        'losses': 0,
        'total_pnl': 0.0
    }
    
    for trade in trades:
        if not trade.get('exit') or not trade.get('result'):
            continue  # 未完了トレードはスキップ
        
        regime = trade['entry']['market']['regime']
        confidence = trade['entry']['market']['confidence']
        reason = trade['entry']['market'].get('reason', '')
        
        pnl = trade['result']['pnl_usd']
        is_win = pnl > 0
        
        # レジーム別集計
        regime_stats[regime]['total'] += 1
        regime_stats[regime]['total_pnl'] += pnl
        regime_stats[regime]['trades'].append({
            'trade_id': trade['trade_id'],
            'side': trade['entry']['side'],
            'pnl': pnl,
            'confidence': confidence,
            'reason': reason
        })
        
        if is_win:
            regime_stats[regime]['wins'] += 1
            regime_stats[regime]['win_pnl'] += pnl
        else:
            regime_stats[regime]['losses'] += 1
            regime_stats[regime]['loss_pnl'] += pnl
        
        # 全体統計
        overall_stats['total'] += 1
        overall_stats['total_pnl'] += pnl
        if is_win:
            overall_stats['wins'] += 1
        else:
            overall_stats['losses'] += 1
    
    # 勝率とProfit Factor計算
    results = {}
    for regime, stats in regime_stats.items():
        win_rate = (stats['wins'] / stats['total'] * 100) if stats['total'] > 0 else 0
        profit_factor = (stats['win_pnl'] / abs(stats['loss_pnl'])) if stats['loss_pnl'] != 0 else float('inf')
        
        results[regime] = {
            'total_trades': stats['total'],
            'wins': stats['wins'],
            'losses': stats['losses'],
            'win_rate': win_rate,
            'total_pnl': stats['total_pnl'],
            'win_pnl': stats['win_pnl'],
            'loss_pnl': stats['loss_pnl'],
            'profit_factor': profit_factor,
            'trades': stats['trades']
        }
    
    # 全体統計計算
    overall_win_rate = (overall_stats['wins'] / overall_stats['total'] * 100) if overall_stats['total'] > 0 else 0
    
    return {
        'overall': {
            'total_trades': overall_stats['total'],
            'wins': overall_stats['wins'],
            'losses': overall_stats['losses'],
            'win_rate': overall_win_rate,
            'total_pnl': overall_stats['total_pnl']
        },
        'by_regime': results
    }

def calculate_hypothetical_filtered_results(analysis: Dict, filter_regimes: List[str]) -> Dict:
    """
    特定レジームのみでトレードした場合の仮想結果を計算
    
    Args:
        analysis: analyze_regime_effectiveness()の結果
        filter_regimes: フィルタリングで許可するレジームのリスト
    
    Returns:
        仮想結果の統計
    """
    total_trades = 0
    wins = 0
    losses = 0
    total_pnl = 0.0
    
    for regime in filter_regimes:
        if regime in analysis['by_regime']:
            stats = analysis['by_regime'][regime]
            total_trades += stats['total_trades']
            wins += stats['wins']
            losses += stats['losses']
            total_pnl += stats['total_pnl']
    
    win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
    
    return {
        'filtered_regimes': filter_regimes,
        'total_trades': total_trades,
        'wins': wins,
        'losses': losses,
        'win_rate': win_rate,
        'total_pnl': total_pnl,
        'trades_filtered_out': analysis['overall']['total_trades'] - total_trades,
        'pnl_improvement': total_pnl - analysis['overall']['total_pnl']
    }

def print_analysis_report(analysis: Dict):
    """
    分析結果をコンソールに出力
    
    Args:
        analysis: analyze_regime_effectiveness()の結果
    """
    print("=" * 80)
    print("市場レジーム有効性分析レポート")
    print("=" * 80)
    
    # 全体統計
    overall = analysis['overall']
    print(f"\n【全体統計】")
    print(f"  総トレード数: {overall['total_trades']}")
    print(f"  勝ち: {overall['wins']} | 負け: {overall['losses']}")
    print(f"  勝率: {overall['win_rate']:.2f}%")
    print(f"  総PnL: {overall['total_pnl']:.2f} USD")
    
    # レジーム別統計
    print(f"\n【レジーム別統計】")
    for regime, stats in sorted(analysis['by_regime'].items()):
        print(f"\n  {regime}:")
        print(f"    トレード数: {stats['total_trades']}")
        print(f"    勝ち: {stats['wins']} | 負け: {stats['losses']}")
        print(f"    勝率: {stats['win_rate']:.2f}%")
        print(f"    総PnL: {stats['total_pnl']:.2f} USD")
        print(f"    勝ちPnL: {stats['win_pnl']:.2f} USD | 負けPnL: {stats['loss_pnl']:.2f} USD")
        print(f"    Profit Factor: {stats['profit_factor']:.2f}")
    
    # フィルタリング仮想結果
    print(f"\n【仮想フィルタリング結果】")
    
    # パターン1: TRENDING_UP/TRENDING_DOWNのみ許可
    trending_only = calculate_hypothetical_filtered_results(
        analysis, 
        ['TRENDING_UP', 'TRENDING_DOWN']
    )
    print(f"\n  パターン1: TRENDINGのみ許可")
    print(f"    トレード数: {trending_only['total_trades']} (除外: {trending_only['trades_filtered_out']})")
    print(f"    勝率: {trending_only['win_rate']:.2f}%")
    print(f"    総PnL: {trending_only['total_pnl']:.2f} USD")
    print(f"    改善PnL: {trending_only['pnl_improvement']:+.2f} USD")
    
    # パターン2: RANGINGを除外
    no_ranging = calculate_hypothetical_filtered_results(
        analysis,
        ['TRENDING_UP', 'TRENDING_DOWN', 'TRANSITION']
    )
    print(f"\n  パターン2: RANGING除外")
    print(f"    トレード数: {no_ranging['total_trades']} (除外: {no_ranging['trades_filtered_out']})")
    print(f"    勝率: {no_ranging['win_rate']:.2f}%")
    print(f"    総PnL: {no_ranging['total_pnl']:.2f} USD")
    print(f"    改善PnL: {no_ranging['pnl_improvement']:+.2f} USD")
    
    # パターン3: TRANSITIONを除外
    no_transition = calculate_hypothetical_filtered_results(
        analysis,
        ['TRENDING_UP', 'TRENDING_DOWN', 'RANGING']
    )
    print(f"\n  パターン3: TRANSITION除外")
    print(f"    トレード数: {no_transition['total_trades']} (除外: {no_transition['trades_filtered_out']})")
    print(f"    勝率: {no_transition['win_rate']:.2f}%")
    print(f"    総PnL: {no_transition['total_pnl']:.2f} USD")
    print(f"    改善PnL: {no_transition['pnl_improvement']:+.2f} USD")
    
    print("\n" + "=" * 80)

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 analyze_regime_effectiveness.py <trade_log_path>")
        print("Example: python3 analyze_regime_effectiveness.py logs/trade_log_20260105121258.json")
        sys.exit(1)
    
    trade_log_path = sys.argv[1]
    
    if not Path(trade_log_path).exists():
        print(f"Error: File not found: {trade_log_path}")
        sys.exit(1)
    
    analysis = analyze_regime_effectiveness(trade_log_path)
    print_analysis_report(analysis)
    
    # JSON出力
    output_path = trade_log_path.replace('.json', '_regime_analysis.json')
    with open(output_path, 'w') as f:
        json.dump(analysis, f, indent=2, ensure_ascii=False)
    print(f"\n詳細分析結果を保存: {output_path}")

if __name__ == '__main__':
    main()
