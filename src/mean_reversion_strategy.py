"""
Mean Reversion Strategy Implementation

目的:
- Bollinger Band 2σ逸脱 + RSI < 30 でエントリーシグナル生成
- 2025年レンジ/高ボラティリティ市場に適合する逆張り戦略

理論:
- BB下限到達 = 統計的に極端な売られすぎ状態
- RSI < 30 = モメンタム的にも売られすぎ確認
- レンジ相場では価格が平均に回帰する傾向を利用

実装日: 2026-01-05 (Phase 1)
"""

from logger import Logger
from config import Config
import statistics
from typing import List, Dict, Tuple, Optional


class MeanReversionStrategy:
    """
    Mean Reversion (平均回帰) 戦略
    
    BB 2σ逸脱 + RSI < 30 の条件で平均回帰を狙う逆張りエントリー
    """
    
    def __init__(self):
        """初期化"""
        self.logger = Logger()
        
        # 設定読み込み
        self.enable_mean_reversion_strategy = Config.get_enable_mean_reversion_strategy()
        self.bb_period = Config.get_bb_period()
        self.bb_std_dev = Config.get_bb_std_dev()
        self.rsi_period = Config.get_rsi_period()
        self.rsi_oversold_threshold = Config.get_rsi_oversold_threshold()
        
        # ログ出力
        if self.enable_mean_reversion_strategy:
            self.logger.log(
                f"[Mean Reversion] 有効化: BB({self.bb_period}, {self.bb_std_dev}σ), "
                f"RSI({self.rsi_period}, <{self.rsi_oversold_threshold})"
            )
        else:
            self.logger.log("[Mean Reversion] 無効")
    
    def calculate_bollinger_bands(
        self, 
        candles: List[List]
    ) -> Tuple[Optional[float], Optional[float], Optional[float]]:
        """
        Bollinger Bands を計算
        
        Args:
            candles: OHLCVデータ [[timestamp, open, high, low, close, volume], ...]
        
        Returns:
            (upper, middle, lower) - BB上限、中央、下限
            計算不可の場合は (None, None, None)
        """
        if len(candles) < self.bb_period:
            return None, None, None
        
        try:
            # 直近 bb_period 本のclose価格を取得
            closes = []
            for i, candle in enumerate(candles[-self.bb_period:]):
                try:
                    # candleがdictかlistかを判定
                    if isinstance(candle, dict):
                        closes.append(float(candle['close_price']))
                    elif isinstance(candle, (list, tuple)):
                        if len(candle) < 5:
                            raise ValueError(f"candle[{i}]の長さが不足: {len(candle)} (最低5必要)")
                        closes.append(float(candle[4]))
                    else:
                        raise ValueError(f"candle[{i}]の型が不正: {type(candle)}")
                except (IndexError, KeyError, TypeError, ValueError) as e:
                    raise ValueError(f"candle[{i}]のclose価格取得エラー: {e}, candle型={type(candle)}")
            
            # 中央値 (SMA)
            middle = statistics.mean(closes)
            
            # 標準偏差
            std = statistics.stdev(closes)
            
            # 上限・下限
            upper = middle + (self.bb_std_dev * std)
            lower = middle - (self.bb_std_dev * std)
            
            return upper, middle, lower
        except Exception as e:
            self.logger.log(f"[BB計算エラー] {type(e).__name__}: {e}")
            return None, None, None
    
    def calculate_rsi(
        self, 
        candles: List[List]
    ) -> Optional[float]:
        """
        RSI (Relative Strength Index) を計算
        
        Args:
            candles: OHLCVデータ [[timestamp, open, high, low, close, volume], ...]
        
        Returns:
            RSI値 (0-100)
            計算不可の場合は None
        """
        if len(candles) < self.rsi_period + 1:
            return None
        
        try:
            # 直近 rsi_period+1 本のclose価格を取得
            closes = []
            for i, candle in enumerate(candles[-(self.rsi_period + 1):]):
                try:
                    # candleがdictかlistかを判定
                    if isinstance(candle, dict):
                        closes.append(float(candle['close_price']))
                    elif isinstance(candle, (list, tuple)):
                        if len(candle) < 5:
                            raise ValueError(f"candle[{i}]の長さが不足: {len(candle)} (最低5必要)")
                        closes.append(float(candle[4]))
                    else:
                        raise ValueError(f"candle[{i}]の型が不正: {type(candle)}")
                except (IndexError, KeyError, TypeError, ValueError) as e:
                    raise ValueError(f"candle[{i}]のclose価格取得エラー: {e}, candle型={type(candle)}")
            
            # 価格変化を計算
            deltas = [closes[i] - closes[i-1] for i in range(1, len(closes))]
            
            # 上昇幅と下落幅を分離
            gains = [d if d > 0 else 0 for d in deltas]
            losses = [-d if d < 0 else 0 for d in deltas]
            
            # 平均上昇幅・平均下落幅
            avg_gain = sum(gains) / self.rsi_period
            avg_loss = sum(losses) / self.rsi_period
            
            # RSI計算
            if avg_loss == 0:
                return 100.0  # 下落なし = 完全に買われすぎ
            
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))
            
            return rsi
        except Exception as e:
            self.logger.log(f"[RSI計算エラー] {type(e).__name__}: {e}")
            return None
    
    def evaluate_entry(
        self,
        candles: List[List],
        current_price: float
    ) -> Dict:
        """
        Mean Reversionエントリーシグナルを評価
        
        条件:
        1. 現在価格 < BB下限 (2σ逸脱)
        2. RSI < oversold_threshold (売られすぎ)
        
        Args:
            candles: OHLCVデータ
            current_price: 現在価格
        
        Returns:
            {
                'signal': True/False,
                'bb_upper': float,
                'bb_middle': float,
                'bb_lower': float,
                'bb_position': float,  # (price - lower) / (upper - lower)
                'rsi': float,
                'reason': str
            }
        """
        # デフォルト結果
        result = {
            'signal': False,
            'bb_upper': None,
            'bb_middle': None,
            'bb_lower': None,
            'bb_position': 0.0,
            'rsi': None,
            'reason': ''
        }
        
        # BB計算
        bb_upper, bb_middle, bb_lower = self.calculate_bollinger_bands(candles)
        
        if bb_upper is None:
            result['reason'] = f'BB計算不可 (期間不足: {len(candles)}/{self.bb_period})'
            return result
        
        result['bb_upper'] = bb_upper
        result['bb_middle'] = bb_middle
        result['bb_lower'] = bb_lower
        
        # BB position計算 (0=下限, 0.5=中央, 1=上限)
        bb_range = bb_upper - bb_lower
        if bb_range > 0:
            result['bb_position'] = (current_price - bb_lower) / bb_range
        
        # RSI計算
        rsi = self.calculate_rsi(candles)
        
        if rsi is None:
            result['reason'] = f'RSI計算不可 (期間不足: {len(candles)}/{self.rsi_period + 1})'
            return result
        
        result['rsi'] = rsi
        
        # シグナル判定
        # 条件1: 現在価格 < BB下限
        if current_price >= bb_lower:
            result['reason'] = f'BB下限未達 (Price={current_price:.2f} >= Lower={bb_lower:.2f})'
            return result
        
        # 条件2: RSI < oversold_threshold
        if rsi >= self.rsi_oversold_threshold:
            result['reason'] = f'RSI売られすぎ未達 (RSI={rsi:.1f} >= {self.rsi_oversold_threshold})'
            return result
        
        # ✅ 両条件を満たす = エントリーシグナル
        result['signal'] = True
        result['reason'] = (
            f'Mean Reversion シグナル: '
            f'Price={current_price:.2f} < BB_Lower={bb_lower:.2f} '
            f'(逸脱={(bb_lower - current_price) / bb_lower * 100:.2f}%), '
            f'RSI={rsi:.1f} < {self.rsi_oversold_threshold}'
        )
        
        self.logger.log(result['reason'])
        
        return result
    
    def get_status_string(self) -> str:
        """
        戦略ステータスを文字列で取得
        
        Returns:
            ステータス文字列
        """
        if not self.enable_mean_reversion_strategy:
            return "Mean Reversion: OFF"
        
        return (
            f"Mean Reversion: ON | "
            f"BB({self.bb_period}, {self.bb_std_dev}σ) | "
            f"RSI({self.rsi_period}, <{self.rsi_oversold_threshold})"
        )
