#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
trade_extractor.py

ログファイルからトレード単位（エントリー～イグジット）を抽出し、
メタデータ付きで CSV/JSON 形式で保存します。
"""

import json
import re
import csv
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

@dataclass
class EntryPoint:
    """エントリーポイントのメタデータ"""
    timestamp: str
    side: str  # BUY/SELL
    price: float
    
    # 条件
    pvo_signal: bool
    donchian_signal: str  # BUY/SELL/NONE
    strategy_signal: Optional[str]  # strategy_A/B/C:BUY/SELL or None
    strategy_match: bool  # Donchian と Strategy が一致したか
    
    # フィルター状態
    pvo_filter_pass: bool
    pvo_filter_value: float
    pvo_filter_threshold: float
    
    adx_filter_pass: bool
    adx_filter_value: float
    adx_filter_threshold: float
    
    volume_filter_pass: bool
    volume_filter_value: float
    volume_filter_threshold: float
    
    volatility_filter_pass: bool
    volatility_filter_value: float
    volatility_filter_threshold: float
    
    # 市場情報
    market_regime: str  # RANGING/TRENDING_UP/TRENDING_DOWN/UNKNOWN
    market_regime_confidence: float  # 0-1
    

@dataclass
class ExitPoint:
    """イグジットポイントのメタデータ"""
    timestamp: str
    price: float
    reason: str  # STOP_LOSS/SIGNAL_REVERSAL/EXIT_STRATEGY/UNKNOWN
    

@dataclass
class TradeResult:
    """トレード成績"""
    pnl_usd: float
    pnl_pct: float
    max_drawdown_usd: float
    max_drawdown_pct: float
    duration_minutes: int
    bars_held: int


@dataclass
class Trade:
    """トレード全体"""
    trade_id: str
    entry: EntryPoint
    exit: ExitPoint
    result: TradeResult
    log_lines: List[str]  # このトレードに関連するログ行


class TradeExtractor:
    """ログファイルからトレード情報を抽出"""
    
    def __init__(self, log_file_path: str):
        self.log_file_path = Path(log_file_path)
        self.trades: List[Trade] = []
        self.current_entry: Optional[EntryPoint] = None
        self.entry_log_lines: List[str] = []
        
    def parse_log_line(self, line: str) -> Optional[Dict]:
        """ログ行をパースして情報を抽出"""
        try:
            # JSON ログを想定
            if line.strip().startswith('{'):
                return json.loads(line)
            
            # テキストログの場合は正規表現でパース
            # TODO: 実装
            return None
        except:
            return None
    
    def extract_entry_info(self, log_lines: List[str]) -> Optional[EntryPoint]:
        """
        ログ行からエントリー情報を抽出
        
        以下のパターンを探す:
        - [条件一覧] ...
        - [フィルタ一覧] ...
        - [最終判定] ✅ エントリー許可
        """
        # TODO: 実装
        return None
    
    def extract_exit_info(self, log_lines: List[str]) -> Optional[ExitPoint]:
        """ログ行からイグジット情報を抽出"""
        # TODO: 実装
        return None
    
    def calculate_trade_result(self, entry: EntryPoint, exit: ExitPoint) -> Optional[TradeResult]:
        """エントリー/イグジット情報からトレード成績を計算"""
        # TODO: 実装
        return None
    
    def extract_trades(self) -> List[Trade]:
        """ログファイル全体からトレードを抽出"""
        trades = []
        
        with open(self.log_file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        current_entry = None
        entry_log_lines = []
        
        for i, line in enumerate(lines):
            # [最終判定] ✅ エントリー許可 を検出
            if '[最終判定]' in line and '✅' in line and 'エントリー許可' in line:
                current_entry = self.extract_entry_info(entry_log_lines + [line])
                if current_entry:
                    entry_log_lines.append(line)
            
            # エントリー後のログを集める
            elif current_entry is not None:
                entry_log_lines.append(line)
                
                # イグジットを検出
                if '[EXIT]' in line or '[ストップロス]' in line or '[決済]' in line:
                    exit_info = self.extract_exit_info(entry_log_lines)
                    if exit_info:
                        result = self.calculate_trade_result(current_entry, exit_info)
                        if result:
                            trade = Trade(
                                trade_id=f"{current_entry.timestamp}_{current_entry.side}",
                                entry=current_entry,
                                exit=exit_info,
                                result=result,
                                log_lines=entry_log_lines.copy()
                            )
                            trades.append(trade)
                    
                    # リセット
                    current_entry = None
                    entry_log_lines = []
        
        self.trades = trades
        return trades
    
    def save_trades_csv(self, output_path: str):
        """トレード情報を CSV で保存"""
        rows = []
        for trade in self.trades:
            rows.append({
                'trade_id': trade.trade_id,
                'entry_timestamp': trade.entry.timestamp,
                'entry_side': trade.entry.side,
                'entry_price': trade.entry.price,
                'exit_timestamp': trade.exit.timestamp,
                'exit_price': trade.exit.price,
                'exit_reason': trade.exit.reason,
                'pnl_usd': trade.result.pnl_usd,
                'pnl_pct': trade.result.pnl_pct,
                'max_drawdown_usd': trade.result.max_drawdown_usd,
                'max_drawdown_pct': trade.result.max_drawdown_pct,
                'duration_minutes': trade.result.duration_minutes,
                'bars_held': trade.result.bars_held,
                'donchian_signal': trade.entry.donchian_signal,
                'strategy_signal': trade.entry.strategy_signal,
                'strategy_match': trade.entry.strategy_match,
                'market_regime': trade.entry.market_regime,
                'adx_value': trade.entry.adx_filter_value,
                'pvo_value': trade.entry.pvo_filter_value,
                'volume_value': trade.entry.volume_filter_value,
                'volatility_value': trade.entry.volatility_filter_value,
            })
        
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            fieldnames = rows[0].keys() if rows else []
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        
        print(f"✓ CSV saved: {output_path}")
    
    def save_trades_json(self, output_path: str):
        """トレード情報を JSON で保存"""
        data = {
            'total_trades': len(self.trades),
            'extraction_timestamp': datetime.now().isoformat(),
            'trades': [
                {
                    'trade_id': trade.trade_id,
                    'entry': asdict(trade.entry),
                    'exit': asdict(trade.exit),
                    'result': asdict(trade.result),
                }
                for trade in self.trades
            ]
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        print(f"✓ JSON saved: {output_path}")


def main():
    """メイン処理"""
    # ログファイルを指定
    log_file = Path(__file__).parent.parent / 'logs' / 'latest.json'
    
    if not log_file.exists():
        print(f"✗ ログファイルが見つかりません: {log_file}")
        return
    
    print(f"📖 ログファイルを読み込み中: {log_file}")
    
    extractor = TradeExtractor(str(log_file))
    trades = extractor.extract_trades()
    
    print(f"✓ {len(trades)} 個のトレードを抽出しました")
    
    # 結果を保存
    output_dir = Path(__file__).parent.parent / 'analysis'
    output_dir.mkdir(exist_ok=True)
    
    csv_path = output_dir / 'trades_with_metadata.csv'
    json_path = output_dir / 'trades_with_metadata.json'
    
    extractor.save_trades_csv(str(csv_path))
    extractor.save_trades_json(str(json_path))
    
    # 簡単な統計を表示
    if trades:
        win_trades = [t for t in trades if t.result.pnl_usd > 0]
        lose_trades = [t for t in trades if t.result.pnl_usd < 0]
        
        print(f"\n📊 トレード統計:")
        print(f"  勝ちトレード: {len(win_trades)}")
        print(f"  負けトレード: {len(lose_trades)}")
        print(f"  勝率: {len(win_trades) / len(trades) * 100:.1f}%")
        
        total_pnl = sum(t.result.pnl_usd for t in trades)
        print(f"  総利益: {total_pnl:+.2f} USD")
        
        if lose_trades:
            avg_loss = sum(abs(t.result.pnl_usd) for t in lose_trades) / len(lose_trades)
            worst_loss = min(t.result.pnl_usd for t in lose_trades)
            print(f"  平均損失: {avg_loss:.2f} USD")
            print(f"  最大損失: {worst_loss:.2f} USD")


if __name__ == '__main__':
    main()
