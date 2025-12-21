"""
MarketRegimeDetector クラス:

ボックス相場（レンジ）とトレンド相場を判定するモジュールです。
ATR（平均真実値幅）とスイング構造を使用した判定ロジックを実装します。

判定結果：
- 'RANGING': ボックス相場（レンジトレード）
- 'TRENDING_UP': 上昇トレンド
- 'TRENDING_DOWN': 下降トレンド
- 'TRANSITION': 遷移中（判定不可）
"""

class MarketRegimeDetector:
    """
    市場体制（ボックス相場 vs トレンド相場）を判定するクラス。
    """
    
    def __init__(self, atr_period=14, atr_ma_period=28, lookback_period=20):
        """
        初期化メソッド
        
        Args:
            atr_period (int): ATR計算期間（デフォルト14）
            atr_ma_period (int): ATRの移動平均期間（デフォルト28 = 14*2）
            lookback_period (int): スイング判定用の遡り期間（デフォルト20）
        """
        self.atr_period = atr_period
        self.atr_ma_period = atr_ma_period
        self.lookback_period = lookback_period
        self.atr_values = []  # ATR値の履歴
    
    def calculate_atr(self, ohlcv_data, period=14):
        """
        Average True Range (ATR)を計算します
        
        Args:
            ohlcv_data (list): OHLCV データリスト（最新データが最後）
            period (int): 計算期間
        
        Returns:
            float: ATR値
        """
        if len(ohlcv_data) < period:
            return None
        
        tr_values = []
        for i in range(len(ohlcv_data) - period, len(ohlcv_data)):
            candle = ohlcv_data[i]
            high = candle['high']
            low = candle['low']
            close = candle['close'] if i > 0 else ohlcv_data[i-1]['close']
            prev_close = ohlcv_data[i-1]['close'] if i > 0 else candle['close']
            
            tr = max(
                high - low,
                abs(high - prev_close),
                abs(low - prev_close)
            )
            tr_values.append(tr)
        
        # SMA of TR
        atr = sum(tr_values[-period:]) / period
        return atr
    
    def detect_regime(self, ohlcv_data, atr_range_lower=0.75, atr_range_upper=1.25):
        """
        市場体制を判定します（手法1: ATR比較 + スイング判定）
        
        Args:
            ohlcv_data (list): OHLCV データリスト
            atr_range_lower (float): ボックス判定の下限倍率（デフォルト0.75 = 75%）
            atr_range_upper (float): トレンド判定の上限倍率（デフォルト1.25 = 125%）
        
        Returns:
            dict: {
                'regime': 'RANGING' | 'TRENDING_UP' | 'TRENDING_DOWN' | 'TRANSITION',
                'atr_ratio': float (current_atr / avg_atr),
                'swing_direction': int (-1, 0, 1),
                'confidence': float (0.0 ~ 1.0)
            }
        """
        if len(ohlcv_data) < self.atr_ma_period + 10:
            return {
                'regime': 'TRANSITION',
                'atr_ratio': None,
                'swing_direction': 0,
                'confidence': 0.0,
                'reason': 'Insufficient data'
            }
        
        # ステップ1: ATR計算
        atr_current = self.calculate_atr(ohlcv_data, self.atr_period)
        atr_ma = self.calculate_atr_ma(ohlcv_data, self.atr_ma_period)
        
        if atr_current is None or atr_ma is None or atr_ma == 0:
            return {
                'regime': 'TRANSITION',
                'atr_ratio': 0,
                'swing_direction': 0,
                'confidence': 0.0,
                'reason': 'ATR calculation failed'
            }
        
        atr_ratio = atr_current / atr_ma
        
        # ステップ2: スイング判定
        swing_direction = self._detect_swing_direction(ohlcv_data, self.lookback_period)
        
        # ステップ3: 複合判定
        # より厳密な判定ルール
        if atr_ratio < atr_range_lower:
            # ATR低い＝ボックス相場の可能性
            regime = 'RANGING'
            confidence = min(0.9, 1.0 - (atr_ratio / atr_range_lower) * 0.3)
            reason = f'Low ATR (ratio={atr_ratio:.3f} < {atr_range_lower})'
        elif atr_ratio > atr_range_upper:
            # ATR高い＋スイング判定でトレンド確定
            if swing_direction > 0:
                regime = 'TRENDING_UP'
                confidence = min(0.95, 0.5 + (atr_ratio - 1.0) * 0.3)
            elif swing_direction < 0:
                regime = 'TRENDING_DOWN'
                confidence = min(0.95, 0.5 + (atr_ratio - 1.0) * 0.3)
            else:
                regime = 'TRANSITION'
                confidence = 0.3
            reason = f'High ATR (ratio={atr_ratio:.3f} > {atr_range_upper}), swing={swing_direction}'
        else:
            # 中間領域＝遷移中
            regime = 'TRANSITION'
            confidence = 0.4
            reason = f'Medium ATR (ratio={atr_ratio:.3f}), expected range [{atr_range_lower}, {atr_range_upper}]'
        
        return {
            'regime': regime,
            'atr_ratio': atr_ratio,
            'swing_direction': swing_direction,
            'confidence': confidence,
            'reason': reason,
            'atr_current': atr_current,
            'atr_ma': atr_ma
        }
    
    def calculate_atr_ma(self, ohlcv_data, ma_period):
        """
        ATRの移動平均を計算します
        
        Args:
            ohlcv_data (list): OHLCV データリスト
            ma_period (int): 移動平均期間
        
        Returns:
            float: ATR の移動平均値
        """
        if len(ohlcv_data) < ma_period + self.atr_period:
            return None
        
        atr_values = []
        
        # 直近のma_period分でATRを計算
        for i in range(len(ohlcv_data) - ma_period, len(ohlcv_data)):
            subset = ohlcv_data[max(0, i - self.atr_period + 1):i + 1]
            if len(subset) >= 2:
                tr_sum = 0
                for j in range(1, len(subset)):
                    candle = subset[j]
                    prev_close = subset[j - 1]['close']
                    high = candle['high']
                    low = candle['low']
                    
                    tr = max(
                        high - low,
                        abs(high - prev_close),
                        abs(low - prev_close)
                    )
                    tr_sum += tr
                
                atr = tr_sum / len(subset)
                if atr > 0:
                    atr_values.append(atr)
        
        if not atr_values or len(atr_values) < ma_period:
            # フォールバック: 直近ma_period本のATRを直接計算
            recent_atr_values = []
            for i in range(max(0, len(ohlcv_data) - ma_period * 2), len(ohlcv_data)):
                subset = ohlcv_data[max(0, i - self.atr_period + 1):i + 1]
                atr = self.calculate_atr(subset, min(self.atr_period, len(subset)))
                if atr is not None and atr > 0:
                    recent_atr_values.append(atr)
            
            if recent_atr_values:
                return sum(recent_atr_values) / len(recent_atr_values)
            else:
                return None
        
        return sum(atr_values[-ma_period:]) / len(atr_values[-ma_period:])
    
    def _detect_swing_direction(self, ohlcv_data, lookback_period=20):
        """
        スイング構造を判定します（上昇スイング、下降スイング、横ばい）
        
        Args:
            ohlcv_data (list): OHLCV データリスト
            lookback_period (int): 遡り期間
        
        Returns:
            int: -1 (下降スイング), 0 (横ばい/不確定), 1 (上昇スイング)
        """
        if len(ohlcv_data) < lookback_period:
            return 0
        
        recent = ohlcv_data[-lookback_period:]
        
        # 直近のHigh と Lowを取得
        highs = [c['high'] for c in recent]
        lows = [c['low'] for c in recent]
        
        # 最初と最後の半分で比較
        mid_point = len(recent) // 2
        
        first_half_high = max(highs[:mid_point])
        first_half_low = min(lows[:mid_point])
        second_half_high = max(highs[mid_point:])
        second_half_low = min(lows[mid_point:])
        
        # スイング判定
        higher_high = second_half_high > first_half_high
        higher_low = second_half_low > first_half_low
        lower_high = second_half_high < first_half_high
        lower_low = second_half_low < first_half_low
        
        # 上昇スイング判定
        if higher_high and higher_low:
            return 1  # TRENDING_UP
        # 下降スイング判定
        elif lower_high and lower_low:
            return -1  # TRENDING_DOWN
        # 横ばい判定
        else:
            return 0  # RANGING or TRANSITION


if __name__ == "__main__":
    # テスト用コード
    detector = MarketRegimeDetector()
    
    # ダミーデータ（通常はprice_data_managementから取得）
    test_data = [
        {'high': 100, 'low': 99, 'close': 99.5},
        {'high': 100.5, 'low': 99.5, 'close': 100},
        # ... 更にデータ追加必要
    ]
    
    # 判定実行
    result = detector.detect_regime(test_data)
    print(f"Market Regime: {result['regime']}")
    print(f"ATR Ratio: {result['atr_ratio']}")
    print(f"Confidence: {result['confidence']}")
