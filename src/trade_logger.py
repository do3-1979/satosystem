"""
TradeLogger クラス:

エントリー時とエグジット時のトレード情報を JSON 形式で logs フォルダに記録します。
後の分析時にこのログを読み込むことで、トレード単位の詳細な分析が可能になります。

記録される情報:
- エントリー時: 時刻、方向（BUY/SELL）、価格、各フィルター状態、PVO/ADX値など
- エグジット時: 上記 + 決済価格、利益、累積利益、保有期間など
"""

import json
import os
from datetime import datetime
import time as _t


class TradeLogger:
    """トレードログを JSON で記録するクラス"""
    
    def __init__(self, log_dir: str = "logs"):
        """
        TradeLogger の初期化
        
        Args:
            log_dir: ログディレクトリのパス
        """
        # 環境変数でQ別ログプリフィックスをチェック（quarterly backtest用）
        quarterly_prefix = os.environ.get('QUARTERLY_LOG_PREFIX', '')
        
        self.log_dir = log_dir
        self.quarterly_prefix = quarterly_prefix  # Q1_2024 のような形式
        self.trades = []  # メモリ内の トレード記録
        self.current_trade = None  # 現在進行中のトレード
        self.trade_counter = 0  # トレードID生成用
        
        # logs フォルダが存在しなければ作成
        if not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)
    
    def log_entry(self, entry_data: dict):
        """
        エントリーをログに記録
        
        Args:
            entry_data: エントリー情報
                - timestamp: ISO形式の時刻
                - close_time_dt: 人間が読める形式の時刻
                - side: 'BUY' または 'SELL'
                - price: エントリー価格
                - pvo_signal: PVO信号 (True/False)
                - pvo_value: PVO値
                - adx_value: ADX値
                - volatility: ボラティリティ値
                - volume: 出来高
                - pvo_filter_pass: PVOフィルター合否
                - adx_filter_pass: ADXフィルター合否
                - volume_filter_pass: Volumeフィルター合否
                - volatility_filter_pass: Volatilityフィルター合否
                - market_regime: 市場体制 (TRENDING/RANGING/UNKNOWN)
                - market_confidence: 市場信頼度 (0-1)
                - donchian_signal: Donchian信号
                - strategy_signal: Strategy信号
        """
        self.trade_counter += 1
        
        self.current_trade = {
            "trade_id": f"{entry_data.get('close_time_dt', datetime.now().isoformat())}_{entry_data.get('side', 'UNKNOWN')}_{entry_data.get('price', 0):.0f}",
            "entry": {
                "timestamp": entry_data.get('timestamp'),
                "close_time_dt": entry_data.get('close_time_dt'),
                "side": entry_data.get('side'),
                "price": entry_data.get('price'),
                "signals": {
                    "pvo_signal": entry_data.get('pvo_signal'),
                    "donchian_signal": entry_data.get('donchian_signal'),
                    "strategy_signal": entry_data.get('strategy_signal')
                },
                "filters": {
                    "pvo": {
                        "pass": entry_data.get('pvo_filter_pass'),
                        "value": entry_data.get('pvo_value'),
                        "threshold": entry_data.get('pvo_threshold', 10)
                    },
                    "adx": {
                        "pass": entry_data.get('adx_filter_pass'),
                        "value": entry_data.get('adx_value'),
                        "threshold": entry_data.get('adx_threshold', 25)
                    },
                    "volume": {
                        "pass": entry_data.get('volume_filter_pass'),
                        "value": entry_data.get('volume'),
                        "threshold": entry_data.get('volume_threshold', 1500000)
                    },
                    "volatility": {
                        "pass": entry_data.get('volatility_filter_pass'),
                        "value": entry_data.get('volatility'),
                        "threshold": entry_data.get('volatility_threshold', 100)
                    }
                },
                "market": {
                    "regime": entry_data.get('market_regime', 'UNKNOWN'),
                    "confidence": entry_data.get('market_regime_confidence', 0.0),
                    "reason": entry_data.get('market_regime_reason', ''),
                    "filter_enabled": entry_data.get('market_regime_filter_enabled', 0)
                },
                "vcp": {
                    "signal": entry_data.get('vcp_signal', 0),
                    "confidence": entry_data.get('vcp_confidence', 0.0),
                    "reason": entry_data.get('vcp_reason', '')
                },
                "mean_reversion": {
                    "signal": entry_data.get('mean_reversion_signal', False),
                    "bb_position": entry_data.get('bb_position', 0.0),
                    "rsi_value": entry_data.get('rsi_value', None),
                    "reason": entry_data.get('mr_reason', '')
                }
            },
            "exit": None,
            "result": None
        }
    
    def log_exit(self, exit_data: dict):
        """
        エグジットをログに記録。エントリーが存在する場合のみ実行
        
        Args:
            exit_data: エグジット情報
                - timestamp: ISO形式の時刻
                - close_time_dt: 人間が読める形式の時刻
                - price: エグジット価格
                - pnl_usd: 損益（USD）
                - pnl_pct: 損益（%）
                - max_drawdown_usd: 最大ドローダウン（USD）
                - max_drawdown_pct: 最大ドローダウン（%）
                - bars_held: 保有バー数
                - duration_minutes: 保有分数
                - reason: エグジット理由 (STOP_LOSS/SIGNAL_REVERSAL/EXIT_STRATEGY)
                - cumulative_pnl: 累積損益
        """
        if self.current_trade is None:
            return  # エントリーログがなければ記録しない
        
        self.current_trade["exit"] = {
            "timestamp": exit_data.get('timestamp'),
            "close_time_dt": exit_data.get('close_time_dt'),
            "price": exit_data.get('price'),
            "reason": exit_data.get('reason', 'UNKNOWN')
        }
        
        self.current_trade["result"] = {
            "pnl_usd": exit_data.get('pnl_usd', 0),
            "pnl_pct": exit_data.get('pnl_pct', 0),
            "max_drawdown_usd": exit_data.get('max_drawdown_usd', 0),
            "max_drawdown_pct": exit_data.get('max_drawdown_pct', 0),
            "bars_held": exit_data.get('bars_held', 0),
            "duration_minutes": exit_data.get('duration_minutes', 0),
            "cumulative_pnl": exit_data.get('cumulative_pnl', 0),
            "win": exit_data.get('pnl_usd', 0) >= 0
        }
        
        # トレードを記録
        self.trades.append(self.current_trade)
        self.current_trade = None
    
    def save_trades_json(self, filename: str = None):
        """
        全トレードを JSON ファイルに保存
        
        Args:
            filename: 保存先ファイル名。省略時は自動生成
        """
        if filename is None:
            ts = _t.strftime('%Y%m%d%H%M%S')
            if self.quarterly_prefix:
                # Q別の場合：Q1_2024_trade_log_YYYYMMDD_HHMMSS.json
                filename = f"{self.quarterly_prefix}_trade_log_{ts}.json"
            else:
                # 通常の場合：trade_log_YYYYMMDD_HHMMSS.json
                filename = f"trade_log_{ts}.json"
        
        filepath = os.path.join(self.log_dir, filename)
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump({
                    "metadata": {
                        "generated_at": datetime.now().isoformat(),
                        "total_trades": len(self.trades),
                        "completed_trades": sum(1 for t in self.trades if t.get('result') is not None),
                        "quarterly_prefix": self.quarterly_prefix if self.quarterly_prefix else None
                    },
                    "trades": self.trades
                }, f, ensure_ascii=False, indent=2)
            return filepath
        except Exception as e:
            print(f"Error saving trade log: {e}")
            return None
    
    def get_trades(self) -> list:
        """
        記録されたトレード一覧を取得
        
        Returns:
            トレード情報のリスト
        """
        return self.trades
    
    def get_current_trade(self) -> dict:
        """
        現在進行中のトレード情報を取得
        
        Returns:
            トレード情報（進行中でない場合は None）
        """
        return self.current_trade
    
    def get_trade_count(self) -> int:
        """
        完了したトレード数を取得
        
        Returns:
            完了したトレード数
        """
        return sum(1 for t in self.trades if t.get('result') is not None)
    
    def get_statistics(self) -> dict:
        """
        簡単な統計情報を計算
        
        Returns:
            統計情報の辞書
        """
        completed = [t for t in self.trades if t.get('result') is not None]
        if not completed:
            return {
                "total_trades": 0,
                "completed_trades": 0,
                "wins": 0,
                "losses": 0,
                "win_rate": 0,
                "total_pnl": 0,
                "avg_pnl": 0
            }
        
        pnls = [t['result']['pnl_usd'] for t in completed]
        wins = sum(1 for p in pnls if p >= 0)
        losses = len(pnls) - wins
        
        return {
            "total_trades": len(self.trades),
            "completed_trades": len(completed),
            "wins": wins,
            "losses": losses,
            "win_rate": (wins / len(completed) * 100) if completed else 0,
            "total_pnl": sum(pnls),
            "avg_pnl": sum(pnls) / len(pnls) if pnls else 0
        }
