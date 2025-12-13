"""
新指標計算モジュール（Phase 22a-22c）

Bollinger Bands, RSI, SMA などの指標を計算するモジュール。
既存の PVO/ADX と同様の構造で実装し、config.ini で ON/OFF 切り替え可能。

指標:
1. Bollinger Bands (BB) - volatility 確認用
2. RSI (Relative Strength Index) - 過買い/過売り検出
3. SMA (Simple Moving Average) - トレンド確認
4. MACD (Moving Average Convergence Divergence) - モメンタム検出
"""

import numpy as np
from config import Config


class NewIndicators:
    """新指標計算クラス"""
    
    def __init__(self):
        """初期化"""
        self.bb_upper = None
        self.bb_lower = None
        self.bb_middle = None
        self.rsi = None
        self.sma_fast = None
        self.sma_slow = None
        self.macd = None
        self.macd_signal = None
    
    # ========== Bollinger Bands ==========
    def calc_bollinger_bands(self, close_data, period=20, num_std=2.0):
        """
        ボリンジャーバンドを計算
        
        Args:
            close_data (list): 終値データ
            period (int): 期間（デフォルト 20）
            num_std (float): シグマ倍数（デフォルト 2.0）
        
        Returns:
            tuple: (upper, middle, lower)
        """
        if len(close_data) < period:
            return None, None, None
        
        close_array = np.array(close_data[-period:])
        middle = np.mean(close_array)
        std = np.std(close_array)
        
        upper = middle + (num_std * std)
        lower = middle - (num_std * std)
        
        self.bb_upper = upper
        self.bb_middle = middle
        self.bb_lower = lower
        
        return upper, middle, lower
    
    def get_bb_upper(self):
        """BB上限を取得"""
        return self.bb_upper if self.bb_upper is not None else 0
    
    def get_bb_lower(self):
        """BB下限を取得"""
        return self.bb_lower if self.bb_lower is not None else 0
    
    def get_bb_middle(self):
        """BB中央（SMA）を取得"""
        return self.bb_middle if self.bb_middle is not None else 0
    
    # ========== RSI (Relative Strength Index) ==========
    def calc_rsi(self, close_data, period=14):
        """
        RSIを計算
        
        Args:
            close_data (list): 終値データ
            period (int): 期間（デフォルト 14）
        
        Returns:
            float: RSI 値（0-100）
        """
        if len(close_data) < period + 1:
            return None
        
        close_array = np.array(close_data[-(period + 1):])
        deltas = np.diff(close_array)
        
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        avg_gain = np.mean(gains)
        avg_loss = np.mean(losses)
        
        if avg_loss == 0:
            rsi = 100 if avg_gain > 0 else 50
        else:
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))
        
        self.rsi = rsi
        return rsi
    
    def get_rsi(self):
        """RSI を取得"""
        return self.rsi if self.rsi is not None else 50
    
    # ========== SMA (Simple Moving Average) ==========
    def calc_sma(self, close_data, fast_period=50, slow_period=200):
        """
        SMA を計算（fast と slow）
        
        Args:
            close_data (list): 終値データ
            fast_period (int): 短期期間（デフォルト 50）
            slow_period (int): 長期期間（デフォルト 200）
        
        Returns:
            tuple: (sma_fast, sma_slow)
        """
        if len(close_data) < slow_period:
            return None, None
        
        close_array = np.array(close_data)
        
        sma_fast = np.mean(close_array[-fast_period:]) if len(close_data) >= fast_period else None
        sma_slow = np.mean(close_array[-slow_period:]) if len(close_data) >= slow_period else None
        
        self.sma_fast = sma_fast
        self.sma_slow = sma_slow
        
        return sma_fast, sma_slow
    
    def get_sma_fast(self):
        """短期 SMA を取得"""
        return self.sma_fast if self.sma_fast is not None else 0
    
    def get_sma_slow(self):
        """長期 SMA を取得"""
        return self.sma_slow if self.sma_slow is not None else 0
    
    # ========== MACD (Moving Average Convergence Divergence) ==========
    def calc_macd(self, close_data, fast_period=12, slow_period=26, signal_period=9):
        """
        MACD を計算
        
        Args:
            close_data (list): 終値データ
            fast_period (int): 短期 EMA 期間（デフォルト 12）
            slow_period (int): 長期 EMA 期間（デフォルト 26）
            signal_period (int): シグナル期間（デフォルト 9）
        
        Returns:
            tuple: (macd, signal, histogram)
        """
        if len(close_data) < slow_period:
            return None, None, None
        
        close_array = np.array(close_data)
        
        # EMA 計算
        ema_fast = self._calc_ema(close_array, fast_period)
        ema_slow = self._calc_ema(close_array, slow_period)
        
        macd = ema_fast - ema_slow
        
        # MACD 系列から Signal EMA を計算
        # 簡易版: 直近の MACD から Signal を計算
        signal = self._calc_ema(np.array([macd]), signal_period)
        
        self.macd = macd
        self.macd_signal = signal
        
        return macd, signal, macd - signal
    
    def get_macd(self):
        """MACD 値を取得"""
        return self.macd if self.macd is not None else 0
    
    def get_macd_signal(self):
        """MACD シグナルを取得"""
        return self.macd_signal if self.macd_signal is not None else 0
    
    # ========== ユーティリティ ==========
    @staticmethod
    def _calc_ema(data, period):
        """
        EMA（指数平滑移動平均）を計算
        
        Args:
            data (np.array): データ配列
            period (int): 期間
        
        Returns:
            float: EMA 値
        """
        if len(data) == 0:
            return 0
        
        result = []
        multiplier = 2 / (period + 1)
        
        for i, price in enumerate(data):
            if i == 0:
                result.append(price)
            else:
                ema = result[-1] * (1 - multiplier) + price * multiplier
                result.append(ema)
        
        return result[-1] if result else 0
    
    # ========== シグナル評価 ==========
    def evaluate_bollinger_signal(self, current_price):
        """
        BB に基づくシグナルを評価
        
        Returns:
            dict: {"signal": bool, "type": "overbought" | "oversold" | None}
        """
        if self.bb_upper is None or self.bb_lower is None:
            return {"signal": False, "type": None}
        
        if current_price > self.bb_upper:
            return {"signal": True, "type": "overbought"}
        elif current_price < self.bb_lower:
            return {"signal": True, "type": "oversold"}
        else:
            return {"signal": False, "type": None}
    
    def evaluate_rsi_signal(self, overbought_level=70, oversold_level=30):
        """
        RSI に基づくシグナルを評価
        
        Args:
            overbought_level (int): 過買い閾値（デフォルト 70）
            oversold_level (int): 過売り閾値（デフォルト 30）
        
        Returns:
            dict: {"signal": bool, "type": "overbought" | "oversold" | None}
        """
        if self.rsi is None:
            return {"signal": False, "type": None}
        
        if self.rsi > overbought_level:
            return {"signal": True, "type": "overbought"}
        elif self.rsi < oversold_level:
            return {"signal": True, "type": "oversold"}
        else:
            return {"signal": False, "type": None}
    
    def evaluate_sma_signal(self, current_price):
        """
        SMA に基づくシグナルを評価
        
        Returns:
            dict: {"signal": bool, "trend": "bullish" | "bearish" | None}
        """
        if self.sma_fast is None or self.sma_slow is None:
            return {"signal": False, "trend": None}
        
        # fast > slow: 上トレンド (bullish)
        # fast < slow: 下トレンド (bearish)
        if self.sma_fast > self.sma_slow:
            return {"signal": True, "trend": "bullish"}
        else:
            return {"signal": False, "trend": "bearish"}
    
    def evaluate_macd_signal(self):
        """
        MACD に基づくシグナルを評価
        
        Returns:
            dict: {"signal": bool, "type": "bullish" | "bearish" | None}
        """
        if self.macd is None or self.macd_signal is None:
            return {"signal": False, "type": None}
        
        # MACD > Signal: 上昇局面
        # MACD < Signal: 下降局面
        if self.macd > self.macd_signal:
            return {"signal": True, "type": "bullish"}
        else:
            return {"signal": False, "type": "bearish"}


if __name__ == "__main__":
    # テスト用ダミーデータ
    close_prices = [100, 101, 102, 101, 103, 102, 104, 103, 105, 104, 106, 105, 107, 106, 108, 107, 109, 108, 110, 109, 111]
    
    indicators = NewIndicators()
    
    # BB
    upper, middle, lower = indicators.calc_bollinger_bands(close_prices, period=5)
    print(f"BB: upper={upper}, middle={middle}, lower={lower}")
    
    # RSI
    rsi = indicators.calc_rsi(close_prices, period=5)
    print(f"RSI: {rsi}")
    
    # SMA
    sma_fast, sma_slow = indicators.calc_sma(close_prices, fast_period=5, slow_period=10)
    print(f"SMA: fast={sma_fast}, slow={sma_slow}")
    
    # MACD
    macd, signal, histogram = indicators.calc_macd(close_prices, fast_period=3, slow_period=6, signal_period=3)
    print(f"MACD: macd={macd}, signal={signal}, histogram={histogram}")
