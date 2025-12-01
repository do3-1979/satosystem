#!/usr/bin/env python3
"""
P0-1: ログ詳細分析 - 修正後のバックテスト結果分析

目的: Win Rate = 0% なのに PnL = +21,105.61 USD という矛盾を解明

分析対象:
- trend_trades_*.json: 個別トレードの詳細
- backtest_summary_*.json: 集計結果
"""

import json
from pathlib import Path
from collections import defaultdict
import statistics

class TradeAnalyzer:
    def __init__(self, trades_file, summary_file):
        self.trades_file = trades_file
        self.summary_file = summary_file
        self.trades = []
        self.summary = {}
        self.load_data()
    
    def load_data(self):
        """データを読み込む"""
        # トレード詳細
        if self.trades_file.exists():
            with open(self.trades_file, 'r') as f:
                data = json.load(f)
                self.trades = data if isinstance(data, list) else data.get('trades', [])
        
        # サマリー
        if self.summary_file.exists():
            with open(self.summary_file, 'r') as f:
                self.summary = json.load(f)
    
    def analyze(self):
        """詳細分析を実施"""
        
        print("\n" + "="*80)
        print("P0-1: ログ詳細分析 - バックテスト結果分析")
        print("="*80 + "\n")
        
        # ===== サマリー結果 =====
        print("📊 バックテスト集計結果:")
        print("-" * 80)
        print(f"  Total PnL: {self.summary.get('total_pnl', 'N/A'):.2f} USD")
        print(f"  Win Rate: {self.summary.get('win_rate', 'N/A'):.2f}%")
        print(f"  Profit Factor: {self.summary.get('profit_factor', 'N/A'):.2f}")
        print(f"  Max Drawdown: {self.summary.get('max_drawdown', 'N/A'):.2f} USD")
        print(f"  Trades Count: {self.summary.get('num_trades', 'N/A')}")
        print(f"  Wins: {self.summary.get('num_wins', 'N/A')}")
        print(f"  Losses: {self.summary.get('num_losses', 'N/A')}")
        print()
        
        # ===== トレード詳細分析 =====
        if self.trades:
            self._analyze_trades()
        else:
            print("❌ トレード詳細データが見つかりません")
        
        # ===== 矛盾点の分析 =====
        self._analyze_contradictions()
    
    def _analyze_trades(self):
        """トレード詳細を分析"""
        
        print("📈 個別トレード分析:")
        print("-" * 80)
        
        # ステータス別に分類
        winning_trades = []
        losing_trades = []
        closed_trades = []
        
        for i, trade in enumerate(self.trades):
            pnl = trade.get('realized_pnl', 0)
            classification = trade.get('classification', 'UNKNOWN')
            
            if pnl > 0:
                winning_trades.append(trade)
            elif pnl < 0:
                losing_trades.append(trade)
            
            if trade.get('exit_price') and trade.get('entry_price'):
                closed_trades.append(trade)
        
        print(f"  総トレード数: {len(self.trades)}")
        print(f"  勝ちトレード: {len(winning_trades)}")
        print(f"  負けトレード: {len(losing_trades)}")
        print(f"  終了したトレード: {len(closed_trades)}")
        print()
        
        # 勝率計算（異なる定義）
        if len(closed_trades) > 0:
            actual_win_rate = (len(winning_trades) / len(closed_trades)) * 100
            print(f"  📊 実計算勝率（閉じたトレード）: {actual_win_rate:.2f}%")
        
        if len(self.trades) > 0:
            overall_win_rate = (len(winning_trades) / len(self.trades)) * 100
            print(f"  📊 全体勝率（全トレード）: {overall_win_rate:.2f}%")
        print()
        
        # 利益・損失の統計
        if winning_trades:
            wins_pnl = [t.get('realized_pnl', 0) for t in winning_trades]
            print(f"  勝ちトレード PnL:")
            print(f"    平均: {statistics.mean(wins_pnl):.2f} USD")
            print(f"    中央値: {statistics.median(wins_pnl):.2f} USD")
            print(f"    合計: {sum(wins_pnl):.2f} USD")
            print()
        
        if losing_trades:
            losses_pnl = [t.get('realized_pnl', 0) for t in losing_trades]
            print(f"  負けトレード PnL:")
            print(f"    平均: {statistics.mean(losses_pnl):.2f} USD")
            print(f"    中央値: {statistics.median(losses_pnl):.2f} USD")
            print(f"    合計: {sum(losses_pnl):.2f} USD")
            print()
        
        # 分類別分析
        classification_stats = defaultdict(lambda: {"count": 0, "pnl": 0})
        for trade in self.trades:
            classification = trade.get('classification', 'UNKNOWN')
            pnl = trade.get('realized_pnl', 0)
            classification_stats[classification]['count'] += 1
            classification_stats[classification]['pnl'] += pnl
        
        print(f"  トレード分類別:")
        for classification, stats in sorted(classification_stats.items()):
            avg_pnl = stats['pnl'] / stats['count'] if stats['count'] > 0 else 0
            print(f"    {classification}: {stats['count']} 件 (平均 PnL: {avg_pnl:.2f} USD, 合計: {stats['pnl']:.2f} USD)")
        print()
    
    def _analyze_contradictions(self):
        """矛盾点を分析"""
        
        print("🔍 矛盾点の分析:")
        print("-" * 80)
        
        summary_win_rate = self.summary.get('win_rate', 0)
        summary_pnl = self.summary.get('total_pnl', 0)
        summary_num_wins = self.summary.get('num_wins', 0)
        summary_num_trades = self.summary.get('num_trades', 0)
        
        # 矛盾1: Win Rate = 0% なのに利益がある
        if summary_win_rate == 0 and summary_pnl > 0:
            print(f"  🔴 矛盾1: Win Rate = 0% なのに PnL = {summary_pnl:.2f} USD (利益)")
            print(f"    → これはロジックエラー")
            print()
        
        # 矛盾2: Win Rate 計算ロジックの検証
        if summary_num_trades > 0 and summary_num_wins >= 0:
            calculated_wr = (summary_num_wins / summary_num_trades) * 100
            print(f"  計算検証:")
            print(f"    wins = {summary_num_wins}, trades = {summary_num_trades}")
            print(f"    期待される Win Rate = {calculated_wr:.2f}%")
            print(f"    サマリーの Win Rate = {summary_win_rate:.2f}%")
            if abs(calculated_wr - summary_win_rate) > 0.01:
                print(f"    🔴 不一致！{calculated_wr:.2f}% ≠ {summary_win_rate:.2f}%")
            print()
        
        # 矛盾3: トレード数の検証
        closed_trades = [t for t in self.trades if t.get('exit_price') and t.get('entry_price')]
        positive_trades = [t for t in self.trades if t.get('realized_pnl', 0) > 0]
        
        print(f"  トレード数の検証:")
        print(f"    トレード詳細の総数: {len(self.trades)}")
        print(f"    サマリーのトレード数: {summary_num_trades}")
        print(f"    詳細の勝ちトレード: {len(positive_trades)}")
        print(f"    サマリーの勝ちトレード: {summary_num_wins}")
        if len(self.trades) != summary_num_trades:
            print(f"    🔴 不一致！")
        print()

def main():
    report_dir = Path('report')
    
    # 最新のファイルを取得
    trades_files = sorted(report_dir.glob('trend_trades_*.json'), reverse=True)
    summary_files = sorted(report_dir.glob('backtest_summary_*.json'), reverse=True)
    
    if not trades_files or not summary_files:
        print("❌ バックテスト結果ファイルが見つかりません")
        return
    
    trades_file = trades_files[0]
    summary_file = summary_files[0]
    
    print(f"分析ファイル:")
    print(f"  トレード詳細: {trades_file}")
    print(f"  サマリー: {summary_file}")
    print()
    
    analyzer = TradeAnalyzer(trades_file, summary_file)
    analyzer.analyze()

if __name__ == '__main__':
    main()
