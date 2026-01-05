#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
aggregate_backtest_logs.py

存在するバックテストログ（logs/フォルダ）からすべてのトレードを抽出し、
複数の結果ファイルを統合します。

戦略：多くのログファイルが既に存在するため、それらをすべて処理して
統合トレード JSON を生成する
"""

import os
import sys
import json
import glob
from pathlib import Path
from datetime import datetime
import csv

# Add tools to path
sys.path.insert(0, str(Path(__file__).parent))

from trade_extractor import Trade, EntryPoint, ExitPoint, TradeResult, TradeExtractor


class LogAggregator:
    """複数ログファイルを統合処理"""
    
    def __init__(self, workspace_root: str = None):
        if workspace_root is None:
            workspace_root = str(Path(__file__).parent.parent)
        
        self.workspace_root = Path(workspace_root)
        self.logs_dir = self.workspace_root / 'logs'
        self.all_trades = []
    
    def aggregate_all_logs(self):
        """logs/ ディレクトリのすべての JSON ログを処理"""
        log_files = sorted(glob.glob(str(self.logs_dir / '*.json')))
        
        # backtest_summary_*.json と通常の日時ログを分離
        summary_logs = [f for f in log_files if 'summary' not in f and 'backtest' not in f]
        
        if not summary_logs:
            print(f"❌ 処理可能なログファイルが見つかりません")
            print(f"   検索ディレクトリ: {self.logs_dir}")
            print(f"   見つかったファイル数: {len(log_files)}")
            return []
        
        print(f"\n{'='*80}")
        print(f"📊 複数ログファイル統合処理")
        print(f"{'='*80}")
        print(f"検索ディレクトリ: {self.logs_dir}")
        print(f"処理対象ログ: {len(summary_logs)} ファイル")
        print()
        
        processed_count = 0
        failed_count = 0
        
        for idx, log_path in enumerate(summary_logs, 1):
            filename = os.path.basename(log_path)
            
            try:
                # ログファイル読み込み
                with open(log_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # 空か無効な JSON をスキップ
                if not data:
                    continue
                
                # リストの場合（個別ログ形式）
                if isinstance(data, list) and len(data) > 0:
                    # TradeExtractor を使用してトレード抽出
                    extractor = TradeExtractor(log_path)
                    trades = extractor.extract_trades()
                    
                    if trades:
                        self.all_trades.extend(trades)
                        processed_count += 1
                        print(f"  ✓ {filename}: {len(trades)} トレード抽出")
                    
            except json.JSONDecodeError:
                failed_count += 1
            except Exception as e:
                failed_count += 1
                # print(f"  ⚠️  {filename}: {str(e)[:50]}")
        
        print(f"\n{'='*80}")
        print(f"処理完了：{processed_count} ファイル処理、{failed_count} ファイル失敗")
        print(f"統合トレード総数：{len(self.all_trades)}")
        
        return self.all_trades
    
    def save_aggregated_trades(self):
        """統合トレードを JSON/CSV で保存"""
        output_dir = self.workspace_root / 'docs' / 'analysis' / 'trades'
        output_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        output_path = str(output_dir / f'trades_all_available_{timestamp}')
        
        # JSON で保存
        trades_data = {
            'metadata': {
                'total_trades': len(self.all_trades),
                'extraction_timestamp': datetime.now().isoformat(),
                'source': 'aggregated from logs directory',
            },
            'trades': [
                {
                    'trade_id': t.trade_id,
                    'entry': {
                        'timestamp': t.entry.timestamp,
                        'timestamp_epoch': t.entry.timestamp_epoch,
                        'side': t.entry.side,
                        'price': t.entry.price,
                        'pvo_signal': t.entry.pvo_signal,
                        'donchian_signal': t.entry.donchian_signal,
                        'strategy_signal': t.entry.strategy_signal,
                        'strategy_match': t.entry.strategy_match,
                        'pvo_filter_pass': t.entry.pvo_filter_pass,
                        'pvo_filter_value': t.entry.pvo_filter_value,
                        'pvo_filter_threshold': t.entry.pvo_filter_threshold,
                        'adx_filter_pass': t.entry.adx_filter_pass,
                        'adx_filter_value': t.entry.adx_filter_value,
                        'adx_filter_threshold': t.entry.adx_filter_threshold,
                        'volume_filter_pass': t.entry.volume_filter_pass,
                        'volume_filter_value': t.entry.volume_filter_value,
                        'volume_filter_threshold': t.entry.volume_filter_threshold,
                        'volatility_filter_pass': t.entry.volatility_filter_pass,
                        'volatility_filter_value': t.entry.volatility_filter_value,
                        'volatility_filter_threshold': t.entry.volatility_filter_threshold,
                        'market_regime': t.entry.market_regime,
                        'market_regime_confidence': t.entry.market_regime_confidence,
                    },
                    'exit': {
                        'timestamp': t.exit.timestamp,
                        'timestamp_epoch': t.exit.timestamp_epoch,
                        'price': t.exit.price,
                        'reason': t.exit.reason,
                    },
                    'result': {
                        'pnl_usd': t.result.pnl_usd,
                        'pnl_pct': t.result.pnl_pct,
                        'max_drawdown_usd': t.result.max_drawdown_usd,
                        'max_drawdown_pct': t.result.max_drawdown_pct,
                        'duration_minutes': t.result.duration_minutes,
                        'bars_held': t.result.bars_held,
                    },
                }
                for t in self.all_trades
            ]
        }
        
        json_path = f"{output_path}.json"
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(trades_data, f, ensure_ascii=False, indent=2)
        
        print(f"✓ JSON 保存: {json_path}")
        
        # CSV で保存
        csv_path = f"{output_path}.csv"
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            if self.all_trades:
                fieldnames = [
                    'trade_id', 'entry_timestamp', 'entry_side', 'entry_price',
                    'exit_timestamp', 'exit_price', 'exit_reason',
                    'pnl_usd', 'pnl_pct', 'max_drawdown_usd', 'max_drawdown_pct',
                    'duration_minutes', 'bars_held',
                    'donchian_signal', 'pvo_signal', 'adx_value', 'pvo_value',
                    'pvo_pass', 'adx_pass', 'market_regime'
                ]
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                
                for trade in self.all_trades:
                    writer.writerow({
                        'trade_id': trade.trade_id,
                        'entry_timestamp': trade.entry.timestamp,
                        'entry_side': trade.entry.side,
                        'entry_price': f"{trade.entry.price:.2f}",
                        'exit_timestamp': trade.exit.timestamp,
                        'exit_price': f"{trade.exit.price:.2f}",
                        'exit_reason': trade.exit.reason,
                        'pnl_usd': f"{trade.result.pnl_usd:+.2f}",
                        'pnl_pct': f"{trade.result.pnl_pct:+.2f}%",
                        'max_drawdown_usd': f"{trade.result.max_drawdown_usd:+.2f}",
                        'max_drawdown_pct': f"{trade.result.max_drawdown_pct:+.2f}%",
                        'duration_minutes': trade.result.duration_minutes,
                        'bars_held': trade.result.bars_held,
                        'donchian_signal': trade.entry.donchian_signal,
                        'pvo_signal': trade.entry.pvo_signal,
                        'adx_value': f"{trade.entry.adx_filter_value:.1f}",
                        'pvo_value': f"{trade.entry.pvo_filter_value:.1f}",
                        'pvo_pass': trade.entry.pvo_filter_pass,
                        'adx_pass': trade.entry.adx_filter_pass,
                        'market_regime': trade.entry.market_regime,
                    })
        
        print(f"✓ CSV 保存: {csv_path}")
        
        return json_path, csv_path
    
    def print_statistics(self):
        """トレード統計を表示"""
        if not self.all_trades:
            print("トレードが抽出されていません")
            return
        
        wins = [t for t in self.all_trades if t.result.pnl_usd > 0]
        losses = [t for t in self.all_trades if t.result.pnl_usd < 0]
        
        total_pnl = sum(t.result.pnl_usd for t in self.all_trades)
        avg_pnl = total_pnl / len(self.all_trades) if self.all_trades else 0
        avg_win = sum(t.result.pnl_usd for t in wins) / len(wins) if wins else 0
        avg_loss = sum(t.result.pnl_usd for t in losses) / len(losses) if losses else 0
        
        win_rate = len(wins) / len(self.all_trades) * 100 if self.all_trades else 0
        
        pf = 0
        if losses:
            win_sum = sum(t.result.pnl_usd for t in wins)
            loss_sum = abs(sum(t.result.pnl_usd for t in losses))
            if loss_sum > 0:
                pf = win_sum / loss_sum
        
        print(f"\n📊 統合トレード統計")
        print(f"{'='*60}")
        print(f"  総トレード数: {len(self.all_trades)}")
        print(f"  勝ちトレード: {len(wins)} ({win_rate:.1f}%)")
        print(f"  負けトレード: {len(losses)}")
        print(f"  総PnL: {total_pnl:+.2f} USD")
        print(f"  平均PnL: {avg_pnl:+.2f} USD")
        print(f"  平均勝利: {avg_win:+.2f} USD")
        print(f"  平均損失: {avg_loss:+.2f} USD")
        if pf > 0:
            print(f"  Profit Factor: {pf:.2f}")


def main():
    """メイン処理"""
    aggregator = LogAggregator()
    
    # すべてのログを統合
    trades = aggregator.aggregate_all_logs()
    
    if trades:
        # 統計表示
        aggregator.print_statistics()
        
        # 結果保存
        json_path, csv_path = aggregator.save_aggregated_trades()
        
        print(f"\n✅ 統合完了: {len(trades)} トレード")
        print(f"   JSON: {json_path}")
        print(f"   CSV: {csv_path}")
    else:
        print(f"\n⚠️  抽出可能なトレードがありません")


if __name__ == '__main__':
    main()
