#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
trade_extractor.py

ログファイル（JSON形式）からトレード単位（エントリー～イグジット）を抽出し、
メタデータ付きで CSV/JSON 形式で保存します。

フェーズ1実装：損失トレード分析のためのメタデータベース構築
"""

import json
import csv
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
import sys
from statistics import mean

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

@dataclass
class EntryPoint:
    """エントリーポイントのメタデータ"""
    timestamp: str  # ISO format
    timestamp_epoch: float
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
    market_regime: str  # RANGING/TRENDING_UP/TRENDING_DOWN
    market_regime_confidence: float  # 0-1
    

@dataclass
class ExitPoint:
    """イグジットポイントのメタデータ"""
    timestamp: str  # ISO format
    timestamp_epoch: float
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


class TradeExtractor:
    """ログファイルからトレード情報を抽出"""
    
    def __init__(self, log_file_path: str):
        self.log_file_path = Path(log_file_path)
        self.log_data: List[Dict] = []
        self.trades: List[Trade] = []
        
        # ログを読み込み
        with open(self.log_file_path, 'r', encoding='utf-8') as f:
            self.log_data = json.load(f)
    
    def extract_trades(self) -> List[Trade]:
        """ログから ENTRY～EXIT のトレードを抽出"""
        trades = []
        current_entry_idx = None
        
        for i, entry in enumerate(self.log_data):
            decision = entry.get('decision', 'NONE')
            
            # エントリーシグナルを検出
            if decision == 'ENTRY':
                current_entry_idx = i
            
            # エグジットシグナルを検出
            elif decision == 'EXIT' and current_entry_idx is not None:
                entry_log = self.log_data[current_entry_idx]
                exit_log = entry
                
                # トレード情報を構築
                trade = self._construct_trade(entry_log, exit_log, current_entry_idx, i)
                if trade:
                    trades.append(trade)
                
                current_entry_idx = None
        
        self.trades = trades
        return trades
    
    def _construct_trade(self, entry_log: Dict, exit_log: Dict, entry_idx: int, exit_idx: int) -> Optional[Trade]:
        """エントリーログとイグジットログからトレード情報を構築"""
        try:
            # エントリー情報抽出
            entry_time_dt = entry_log.get('close_time_dt', '')
            entry_time_epoch = entry_log.get('close_time', 0)
            entry_price = entry_log.get('close_price', 0)
            entry_side = entry_log.get('side', 'NONE')
            
            # イグジット情報抽出
            exit_time_dt = exit_log.get('close_time_dt', '')
            exit_time_epoch = exit_log.get('close_time', 0)
            exit_price = exit_log.get('close_price', 0)
            
            # シグナル情報抽出
            donchian_data = entry_log.get('donchian', {})
            donchian_signal = donchian_data.get('side', 'NONE')
            pvo_data = entry_log.get('pvo', {})
            pvo_signal = pvo_data.get('signal', False)
            
            # 市場情報（簡略版）
            adx_value = entry_log.get('adx', 0)
            pvo_value = pvo_data.get('info', {}).get('value', 0)
            volatility_value = entry_log.get('volatility', 0)
            volume_value = entry_log.get('Volume', 0)
            
            # 計算：PnL, ドローダウン, 保有期間
            position_price = entry_log.get('position_price', entry_price)
            
            # PnL USD を計算（entry_price から exit_price への変動）
            # BUYの場合: (exit_price - entry_price) * position_quantity
            # SELLの場合: (entry_price - exit_price) * position_quantity
            # 単純化: 1単位のポジションと仮定
            if entry_side == 'BUY':
                pnl_usd = exit_price - entry_price
            elif entry_side == 'SELL':
                pnl_usd = entry_price - exit_price
            else:
                pnl_usd = exit_log.get('profit_and_loss', 0)
            
            if position_price > 0:
                pnl_pct = ((exit_price - position_price) / position_price) * 100
            else:
                pnl_pct = 0
            
            # エントリー～イグジット間の最大ドローダウンを計算
            max_dd = self._calculate_max_drawdown(entry_idx, exit_idx)
            
            duration_minutes = int((exit_time_epoch - entry_time_epoch) / 60)
            bars_held = exit_idx - entry_idx
            
            # EntryPoint構築
            entry_point = EntryPoint(
                timestamp=entry_time_dt,
                timestamp_epoch=entry_time_epoch,
                side=entry_side,
                price=entry_price,
                pvo_signal=pvo_signal,
                donchian_signal=donchian_signal if donchian_signal != 'None' else 'NONE',
                strategy_signal=None,  # ログに記録されていない場合
                strategy_match=False,
                pvo_filter_pass=pvo_signal,
                pvo_filter_value=pvo_value,
                pvo_filter_threshold=10,  # デフォルト
                adx_filter_pass=adx_value >= 31,
                adx_filter_value=adx_value,
                adx_filter_threshold=31,
                volume_filter_pass=volume_value > 0,
                volume_filter_value=volume_value,
                volume_filter_threshold=1500000,  # デフォルト
                volatility_filter_pass=volatility_value < 100,  # 仮
                volatility_filter_value=volatility_value,
                volatility_filter_threshold=100,
                market_regime='UNKNOWN',
                market_regime_confidence=0.5
            )
            
            # ExitPoint構築
            exit_point = ExitPoint(
                timestamp=exit_time_dt,
                timestamp_epoch=exit_time_epoch,
                price=exit_price,
                reason='STOP_LOSS' if exit_log.get('stop_price', 0) > 0 else 'EXIT_STRATEGY'
            )
            
            # TradeResult構築
            trade_result = TradeResult(
                pnl_usd=pnl_usd,
                pnl_pct=pnl_pct,
                max_drawdown_usd=max_dd,
                max_drawdown_pct=(max_dd / position_price * 100) if position_price > 0 else 0,
                duration_minutes=duration_minutes,
                bars_held=bars_held
            )
            
            # Trade構築
            trade_id = f"{entry_time_dt}_{entry_side}_{int(entry_price)}"
            trade = Trade(
                trade_id=trade_id,
                entry=entry_point,
                exit=exit_point,
                result=trade_result
            )
            
            return trade
            
        except Exception as e:
            print(f"⚠️  トレード構築エラー (entry_idx={entry_idx}): {e}")
            return None
    
    def _calculate_max_drawdown(self, start_idx: int, end_idx: int) -> float:
        """エントリー～エグジット間の最大ドローダウンを計算"""
        try:
            pnl_values = []
            for i in range(start_idx, end_idx + 1):
                pnl = self.log_data[i].get('profit_and_loss', 0)
                pnl_values.append(pnl)
            
            if not pnl_values:
                return 0
            
            # ドローダウン = ピークから現在値までの下落幅
            max_dd = 0
            peak = pnl_values[0]
            
            for pnl in pnl_values:
                if pnl > peak:
                    peak = pnl
                dd = peak - pnl
                if dd > max_dd:
                    max_dd = dd
            
            return -max_dd  # 負の値で返す
            
        except:
            return 0
    
    def save_trades_csv(self, output_path: str):
        """トレード情報を CSV で保存"""
        if not self.trades:
            print(f"✗ トレードが抽出されていません")
            return
        
        rows = []
        for trade in self.trades:
            rows.append({
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
                'volatility_value': f"{trade.entry.volatility_filter_value:.1f}",
                'market_regime': trade.entry.market_regime,
            })
        
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            fieldnames = rows[0].keys() if rows else []
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        
        print(f"✓ CSV saved: {output_path}")
    
    def save_trades_json(self, output_path: str):
        """トレード情報を JSON で保存"""
        if not self.trades:
            print(f"✗ トレードが抽出されていません")
            return
        
        data = {
            'metadata': {
                'total_trades': len(self.trades),
                'extraction_timestamp': datetime.now().isoformat(),
                'log_file': str(self.log_file_path),
            },
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
    
    def print_statistics(self):
        """トレード統計を表示"""
        if not self.trades:
            print(f"✗ トレードが抽出されていません")
            return
        
        win_trades = [t for t in self.trades if t.result.pnl_usd > 0]
        lose_trades = [t for t in self.trades if t.result.pnl_usd < 0]
        
        print(f"\n📊 トレード統計:")
        print(f"  総トレード数: {len(self.trades)}")
        print(f"  勝ちトレード: {len(win_trades)}")
        print(f"  負けトレード: {len(lose_trades)}")
        print(f"  勝率: {len(win_trades) / len(self.trades) * 100:.1f}%")
        
        total_pnl = sum(t.result.pnl_usd for t in self.trades)
        print(f"  総利益: {total_pnl:+.2f} USD")
        
        if win_trades:
            avg_win = mean(t.result.pnl_usd for t in win_trades)
            max_win = max(t.result.pnl_usd for t in win_trades)
            print(f"  平均利益: {avg_win:+.2f} USD")
            print(f"  最大利益: {max_win:+.2f} USD")
        
        if lose_trades:
            avg_loss = mean(t.result.pnl_usd for t in lose_trades)
            worst_loss = min(t.result.pnl_usd for t in lose_trades)
            print(f"  平均損失: {avg_loss:+.2f} USD")
            print(f"  最大損失: {worst_loss:+.2f} USD")
        
        if len(self.trades) > 0:
            profit_factor = sum(t.result.pnl_usd for t in win_trades) / abs(sum(t.result.pnl_usd for t in lose_trades)) if lose_trades and sum(t.result.pnl_usd for t in lose_trades) != 0 else 0
            print(f"  Profit Factor: {profit_factor:.2f}")


def main():
    """メイン処理"""
    # 最新のログファイルを取得
    log_dir = Path(__file__).parent.parent / 'logs'
    log_files = sorted([f for f in log_dir.glob('*.json') if f.name[0].isdigit()], reverse=True)
    
    if not log_files:
        print(f"✗ ログファイルが見つかりません")
        return
    
    log_file = log_files[0]
    print(f"📖 ログファイルを読み込み中: {log_file.name}")
    
    try:
        extractor = TradeExtractor(str(log_file))
        trades = extractor.extract_trades()
        
        print(f"✓ {len(trades)} 個のトレードを抽出しました")
        
        # 結果を保存
        output_dir = Path(__file__).parent.parent / 'docs' / 'analysis' / 'trades'
        output_dir.mkdir(exist_ok=True, parents=True)
        
        csv_path = output_dir / f"trades_{log_file.stem}.csv"
        json_path = output_dir / f"trades_{log_file.stem}.json"
        
        extractor.save_trades_csv(str(csv_path))
        extractor.save_trades_json(str(json_path))
        
        # 統計表示
        extractor.print_statistics()
        
    except Exception as e:
        print(f"✗ エラーが発生しました: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
