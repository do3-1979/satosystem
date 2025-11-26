#!/usr/bin/env python3
"""
P0-1: ログ詳細分析による根本原因特定

目的:
  - 個別トレードの詳細情報をキャプチャ
  - 勝率が高いのに大損失する理由を特定
  - ポジションサイズ、エントリー/エグジット価格、損益の関連性を分析

機能:
  1. TradeDetailLogger: 個別トレードの詳細ログ記録
  2. TradeAnalyzer: バックテスト結果の事後分析
  3. 異常検知: 高勝率 + 大損失のパターン検出
"""

import json
import os
from datetime import datetime
from typing import List, Dict, Any
import statistics

class TradeDetailLogger:
    """個別トレードの詳細ログを記録"""
    
    def __init__(self, output_dir: str = 'analysis'):
        self.output_dir = output_dir
        self.trades = []
        os.makedirs(output_dir, exist_ok=True)
        
    def log_trade(self, trade_data: Dict[str, Any]):
        """トレード情報をログに記録"""
        # タイムスタンプを追加
        trade_data['logged_at'] = datetime.now().isoformat()
        self.trades.append(trade_data)
    
    def save_to_file(self, filename: str = None):
        """ログをJSONファイルに保存"""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f'trade_details_{timestamp}.json'
        
        filepath = os.path.join(self.output_dir, filename)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.trades, f, indent=2, ensure_ascii=False)
        
        return filepath

class TradeAnalyzer:
    """トレード詳細の分析"""
    
    def __init__(self, trades: List[Dict[str, Any]]):
        self.trades = trades
        self.analysis_result = {}
    
    def calculate_statistics(self) -> Dict[str, Any]:
        """基本統計を計算"""
        if not self.trades:
            return {}
        
        pnls = [t.get('pnl', 0) for t in self.trades]
        position_sizes = [t.get('position_size', 0) for t in self.trades]
        entry_prices = [t.get('entry_price', 0) for t in self.trades]
        exit_prices = [t.get('exit_price', 0) for t in self.trades]
        
        win_trades = [t for t in self.trades if t.get('pnl', 0) > 0]
        loss_trades = [t for t in self.trades if t.get('pnl', 0) < 0]
        
        stats = {
            'total_trades': len(self.trades),
            'winning_trades': len(win_trades),
            'losing_trades': len(loss_trades),
            'win_rate': len(win_trades) / len(self.trades) * 100 if self.trades else 0,
            
            # PnL統計
            'total_pnl': sum(pnls),
            'avg_pnl': statistics.mean(pnls) if pnls else 0,
            'median_pnl': statistics.median(pnls) if pnls else 0,
            'stdev_pnl': statistics.stdev(pnls) if len(pnls) > 1 else 0,
            'max_win': max([p for p in pnls if p > 0], default=0),
            'max_loss': min([p for p in pnls if p < 0], default=0),
            
            # ポジションサイズ統計
            'avg_position_size': statistics.mean(position_sizes) if position_sizes else 0,
            'max_position_size': max(position_sizes) if position_sizes else 0,
            'min_position_size': min(position_sizes) if position_sizes else 0,
        }
        
        return stats
    
    def detect_anomalies(self) -> List[Dict[str, Any]]:
        """異常パターンを検出"""
        anomalies = []
        
        # 高勝率なのに大損失するパターン
        win_rate = (len([t for t in self.trades if t.get('pnl', 0) > 0]) / 
                    len(self.trades) * 100 if self.trades else 0)
        total_pnl = sum([t.get('pnl', 0) for t in self.trades])
        
        if win_rate > 50 and total_pnl < 0:
            anomalies.append({
                'type': 'HIGH_WIN_RATE_BIG_LOSS',
                'severity': 'CRITICAL',
                'win_rate': win_rate,
                'total_pnl': total_pnl,
                'description': f'勝率{win_rate:.1f}%なのに総損失${abs(total_pnl):.2f}',
                'cause': 'ポジションサイズの不均衡が原因と推測',
            })
        
        # ポジションサイズと損失の不均衡
        for trade in self.trades:
            pnl = trade.get('pnl', 0)
            position_size = trade.get('position_size', 0)
            entry_price = trade.get('entry_price', 0)
            
            if position_size > 0 and entry_price > 0:
                # ポジション価値
                position_notional = position_size * entry_price
                
                # 損失が過度に大きい場合
                if pnl < 0 and abs(pnl) > position_notional * 0.1:  # 10%以上の損失
                    anomalies.append({
                        'type': 'EXCESSIVE_LOSS',
                        'severity': 'WARNING',
                        'trade_id': trade.get('trade_id'),
                        'pnl': pnl,
                        'position_notional': position_notional,
                        'loss_ratio': abs(pnl) / position_notional,
                    })
        
        return anomalies
    
    def analyze_pnl_distribution(self) -> Dict[str, Any]:
        """PnL分布の分析"""
        if not self.trades:
            return {}
        
        pnls = [t.get('pnl', 0) for t in self.trades]
        
        # PnLの分布を分析
        positive_pnls = [p for p in pnls if p > 0]
        negative_pnls = [p for p in pnls if p < 0]
        
        total_wins = sum(positive_pnls) if positive_pnls else 0
        total_losses = sum(negative_pnls) if negative_pnls else 0
        
        analysis = {
            'profit_factor': total_wins / abs(total_losses) if total_losses != 0 else 0,
            'avg_win': statistics.mean(positive_pnls) if positive_pnls else 0,
            'avg_loss': statistics.mean(negative_pnls) if negative_pnls else 0,
            'win_loss_ratio': abs(statistics.mean(positive_pnls) / statistics.mean(negative_pnls)) 
                             if negative_pnls and positive_pnls else 0,
            'total_wins': total_wins,
            'total_losses': total_losses,
        }
        
        return analysis
    
    def generate_report(self) -> str:
        """詳細レポートを生成"""
        stats = self.calculate_statistics()
        anomalies = self.detect_anomalies()
        pnl_dist = self.analyze_pnl_distribution()
        
        report = []
        report.append("=" * 80)
        report.append("📊 トレード詳細分析レポート")
        report.append("=" * 80)
        
        # 基本統計
        report.append("\n【基本統計】")
        report.append(f"  総トレード数: {stats.get('total_trades', 0)}")
        report.append(f"  勝ちトレード: {stats.get('winning_trades', 0)}")
        report.append(f"  負けトレード: {stats.get('losing_trades', 0)}")
        report.append(f"  勝率: {stats.get('win_rate', 0):.1f}%")
        
        # PnL統計
        report.append("\n【PnL統計】")
        report.append(f"  総損益: ${stats.get('total_pnl', 0):+.2f}")
        report.append(f"  平均PnL: ${stats.get('avg_pnl', 0):+.2f}")
        report.append(f"  中央値PnL: ${stats.get('median_pnl', 0):+.2f}")
        report.append(f"  標準偏差: ${stats.get('stdev_pnl', 0):.2f}")
        report.append(f"  最大利益: ${stats.get('max_win', 0):+.2f}")
        report.append(f"  最大損失: ${stats.get('max_loss', 0):+.2f}")
        
        # ポジションサイズ統計
        report.append("\n【ポジションサイズ統計】")
        report.append(f"  平均: {stats.get('avg_position_size', 0):.8f}")
        report.append(f"  最大: {stats.get('max_position_size', 0):.8f}")
        report.append(f"  最小: {stats.get('min_position_size', 0):.8f}")
        
        # PnL分布
        report.append("\n【PnL分布分析】")
        report.append(f"  プロフィットファクター: {pnl_dist.get('profit_factor', 0):.2f}")
        report.append(f"  平均利益: ${pnl_dist.get('avg_win', 0):+.2f}")
        report.append(f"  平均損失: ${pnl_dist.get('avg_loss', 0):+.2f}")
        report.append(f"  Win/Loss比: {pnl_dist.get('win_loss_ratio', 0):.2f}")
        report.append(f"  総利益: ${pnl_dist.get('total_wins', 0):+.2f}")
        report.append(f"  総損失: ${pnl_dist.get('total_losses', 0):+.2f}")
        
        # 異常検知
        report.append("\n【異常検知】")
        if anomalies:
            for i, anomaly in enumerate(anomalies, 1):
                report.append(f"\n  {i}. {anomaly['type']} [{anomaly['severity']}]")
                if 'description' in anomaly:
                    report.append(f"     説明: {anomaly['description']}")
                if 'cause' in anomaly:
                    report.append(f"     原因推測: {anomaly['cause']}")
        else:
            report.append("  ✅ 異常なし")
        
        # 結論
        report.append("\n" + "=" * 80)
        report.append("【結論】")
        report.append("=" * 80)
        if stats.get('win_rate', 0) > 50 and stats.get('total_pnl', 0) < 0:
            report.append("❌ 問題: 勝率は高いが総損益が負")
            report.append("\n原因の可能性:")
            report.append("  1. 負けトレードのポジションサイズが過度に大きい")
            report.append("  2. 負けトレードのストップロスが有効に機能していない")
            report.append("  3. リスク・リワード比が悪い（平均損失 > 平均利益）")
            report.append(f"\n   実測: 平均利益${pnl_dist.get('avg_win', 0):.2f} vs 平均損失${pnl_dist.get('avg_loss', 0):.2f}")
        else:
            report.append("✅ 結果は想定内")
        
        return "\n".join(report)


def example_analysis():
    """使用例"""
    # サンプルトレードデータ
    sample_trades = [
        {
            'trade_id': 1,
            'entry_price': 50000,
            'exit_price': 51000,
            'position_size': 0.1,
            'pnl': 100,
            'entry_time': '2024-01-01 10:00:00',
            'exit_time': '2024-01-01 11:00:00',
        },
        {
            'trade_id': 2,
            'entry_price': 51000,
            'exit_price': 50500,
            'position_size': 0.2,
            'pnl': -100,
            'entry_time': '2024-01-01 12:00:00',
            'exit_time': '2024-01-01 13:00:00',
        },
        {
            'trade_id': 3,
            'entry_price': 50500,
            'exit_price': 51200,
            'position_size': 0.15,
            'pnl': 105,
            'entry_time': '2024-01-01 14:00:00',
            'exit_time': '2024-01-01 15:00:00',
        },
        {
            'trade_id': 4,
            'entry_price': 51200,
            'exit_price': 49000,
            'position_size': 0.5,
            'pnl': -1100,
            'entry_time': '2024-01-01 16:00:00',
            'exit_time': '2024-01-01 17:00:00',
        },
    ]
    
    # 分析実行
    analyzer = TradeAnalyzer(sample_trades)
    report = analyzer.generate_report()
    print(report)
    
    # レポート保存
    analyzer_output = os.path.join('analysis', 'trade_detail_analysis.md')
    os.makedirs('analysis', exist_ok=True)
    with open(analyzer_output, 'w', encoding='utf-8') as f:
        f.write(report)
    print(f"\n💾 レポート保存: {analyzer_output}")

if __name__ == '__main__':
    example_analysis()
