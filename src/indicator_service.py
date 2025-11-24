"""
IndicatorService: テクニカル指標を計算するサービス

※ 簡易実装版（indicator_service.pyが削除されていたため）
実際の計算ロジックが必要な場合は、各メソッドを実装してください
"""

import numpy as np


class IndicatorService:
    """テクニカル指標計算サービス"""
    
    def __init__(self, adx_term=14, adx_continue_num=3, 
                 adx_bull_threshold=25, adx_bear_threshold=25):
        """
        Args:
            adx_term: ADX計算期間
            adx_continue_num: ADX連続判定数
            adx_bull_threshold: ADX強気閾値
            adx_bear_threshold: ADX弱気閾値
        """
        self.adx_term = adx_term
        self.adx_continue_num = adx_continue_num
        self.adx_bull_threshold = adx_bull_threshold
        self.adx_bear_threshold = adx_bear_threshold
        
        # PSAR計算用の状態保持
        self.psar = []         # Parabolic SAR値
        self.psarbull = []     # SAR (bull trend)
        self.psarbear = []     # SAR (bear trend)
        self.psar_af = 0.02    # Acceleration Factor
        self.psar_trend = 'up' # 'up' or 'down'
        self.psar_ep = 0       # Extreme Point
        
        # ADX計算用の状態保持
        self.adx = []          # ADX値
        self.adx_bull = []     # Plus DI
        self.adx_bear = []     # Minus DI
    
    def calculate_volatility(self, ohlcv_data, period=14):
        """
        ボラティリティを計算（標準偏差ベース）
        
        Args:
            ohlcv_data: OHLCVデータ
            period: 計算期間
            
        Returns:
            float: ボラティリティ（%）
        """
        if len(ohlcv_data) < period:
            return 0.0
        
        closes = np.array([d.get('close_price', 0) for d in ohlcv_data[-period:]], dtype=float)
        if len(closes) == 0 or np.all(closes == 0):
            return 0.0
        
        # 日次リターンを計算
        returns = np.diff(closes) / closes[:-1]
        
        # 標準偏差をパーセンテージで返す
        volatility = np.std(returns) * 100
        return float(volatility)
    
    def calculate_donchian(self, ohlcv_data, period=20, side='buy'):
        """
        ドンチャンチャネルを計算
        
        Args:
            ohlcv_data: OHLCVデータ
            period: 計算期間
            side: 'buy' or 'sell' または 価格値（後方互換性）
            
        Returns:
            dict または str: シグナル情報 または 'BUY'/'SELL'/'None'
        """
        if len(ohlcv_data) < period:
            return {'signal': False, 'side': None, 'value': 0}
        
        recent_data = ohlcv_data[-period:]
        
        # 後方互換性: side が数値の場合は価格値として扱う
        if isinstance(side, (int, float)):
            current_price = side
            # BUY/SELL判定用に買い側を基本とする
            side_type = 'buy'
        else:
            current_price = ohlcv_data[-1].get('close_price', 0)
            side_type = side
        
        if side_type == 'buy':
            # 過去期間の高値を取得
            high_value = max([d.get('high_price', 0) for d in recent_data])
            signal = current_price >= high_value if high_value > 0 else False
            return_side = 'BUY' if signal else 'None'
        else:  # sell
            # 過去期間の安値を取得
            low_value = min([d.get('low_price', float('inf')) for d in recent_data])
            signal = current_price <= low_value if low_value != float('inf') else False
            return_side = 'SELL' if signal else 'None'
        
        # 辞書形式と文字列形式の両方をサポート
        return return_side  # 後方互換性のため文字列を返す
    
    def calculate_pvo(self, ohlcv_data, short_period=12, long_period=26, threshold=0):
        """
        PVO（Percentage Volume Oscillator）を計算
        後方互換性: short_period が数値（出来高）の場合は処理を変える
        
        Args:
            ohlcv_data: OHLCVデータ
            short_period: 短期EMA期間 または 出来高（後方互換性）
            long_period: 長期EMA期間（デフォルト26）
            threshold: シグナル閾値（デフォルト0）
            
        Returns:
            dict または float: シグナル情報 または PVO値
        """
        # 後方互換性チェック: short_period が数値の場合は出来高パラメータ
        if isinstance(short_period, (int, float)) and short_period > 1000:
            # volume値としての処理
            return short_period  # 簡易実装: 出来高そのものを返す
        
        if len(ohlcv_data) < long_period:
            return {'signal': False, 'side': None, 'value': 0}
        
        volumes = [d.get('volume', 0) for d in ohlcv_data]
        
        # ボリュームが利用不可の場合（データが全て0またはNone）
        # → 価格ボラティリティをPVOの代替指標として使用
        if all(v == 0 or v is None for v in volumes):
            # 価格ボラティリティベースのPVO計算（フォールバック）
            closes = [d.get('close_price', 0) for d in ohlcv_data]
            if len(closes) < long_period:
                return {'signal': False, 'side': None, 'value': 0}
            
            # 最近のボラティリティを計算
            recent_closes = closes[-long_period:]
            price_change = recent_closes[-1] - recent_closes[0]
            price_volatility = abs(price_change) / recent_closes[0] * 100 if recent_closes[0] != 0 else 0
            
            # ボラティリティ > 0.5% → シグナル判定
            signal = price_volatility > 0.5
            return {
                'signal': signal,
                'side': 'buy' if signal else None,
                'value': price_volatility
            }
        
        # 簡易EMA計算
        short_ema = self._calculate_ema(volumes, short_period)
        long_ema = self._calculate_ema(volumes, long_period)
        
        if long_ema == 0:
            pvo = 0
        else:
            pvo = ((short_ema - long_ema) / long_ema) * 100
        
        signal = pvo > threshold
        
        return {
            'signal': signal,
            'side': 'buy' if signal else None,
            'value': pvo
        }
    
    def calculate_adx(self, ohlcv_data, period=14):
        """
        ADX（Average Directional Index）を計算（簡易版）
        
        Args:
            ohlcv_data: OHLCVデータ
            period: 計算期間
            
        Returns:
            なし（self.adx, self.adx_bull, self.adx_bear を更新）
        """
        if len(ohlcv_data) < period:
            if not self.adx:
                self.adx = []
                self.adx_bull = []
                self.adx_bear = []
            return
        
        # 簡易実装：価格トレンドで判定
        recent = ohlcv_data[-period:]
        first_close = recent[0].get('close_price', 0)
        last_close = recent[-1].get('close_price', 0)
        
        if first_close == 0:
            adx = 0
            trend = 'NONE'
        else:
            price_change_pct = ((last_close - first_close) / first_close) * 100
            adx = abs(price_change_pct)
            
            if adx > self.adx_bull_threshold:
                trend = 'UP' if price_change_pct > 0 else 'DOWN'
            else:
                trend = 'NONE'
        
        # ADX値を記録
        self.adx.append(adx)
        
        # Plus DI / Minus DI を記録（簡易版）
        if trend == 'UP':
            self.adx_bull.append(adx)
            self.adx_bear.append(0)
        elif trend == 'DOWN':
            self.adx_bull.append(0)
            self.adx_bear.append(adx)
        else:
            self.adx_bull.append(0)
            self.adx_bear.append(0)
        
        return
    
    @staticmethod
    def _calculate_ema(data, period):
        """簡易EMA計算"""
        if len(data) < period:
            return sum(data) / len(data) if data else 0
        
        multiplier = 2 / (period + 1)
        ema = sum(data[:period]) / period
        
        for value in data[period:]:
            ema = value * multiplier + ema * (1 - multiplier)
        
        return ema
    
    def calculate_ema(self, term, data):
        """
        EMA（指数平滑移動平均）を計算
        
        Args:
            term: EMA期間
            data: データリスト
            
        Returns:
            float: EMA値
        """
        return self._calculate_ema(data, term)
    
    def evaluate_pvo(self, ohlcv_data, short_period=12, long_period=26, threshold=0):
        """
        PVOを評価し、シグナルの強さを返す
        
        Args:
            ohlcv_data: OHLCVデータ
            short_period: 短期EMA期間
            long_period: 長期EMA期間
            threshold: 閾値
            
        Returns:
            dict: {'signal': bool, 'strength': float}
        """
        pvo_result = self.calculate_pvo(ohlcv_data, short_period, long_period, threshold)
        
        if isinstance(pvo_result, dict):
            return {
                'signal': pvo_result.get('signal', False),
                'strength': abs(pvo_result.get('value', 0))
            }
        else:
            # 数値が返った場合（後方互換性）
            return {'signal': False, 'strength': 0}
    
    def calculate_parabolic_sar(self, ohlcv_data, start_af=0.02, max_af=0.2):
        """
        放物線SAR（Parabolic SAR）を計算
        
        Args:
            ohlcv_data: OHLCVデータ
            start_af: 初期加速係数
            max_af: 最大加速係数
            
        Returns:
            なし（self.psar, self.psarbull, self.psarbear を更新）
        """
        if not ohlcv_data or len(ohlcv_data) < 2:
            if not self.psar:
                self.psar = []
                self.psarbull = []
                self.psarbear = []
            return
        
        # 直近データの高値/安値を取得
        recent = ohlcv_data[-20:] if len(ohlcv_data) >= 20 else ohlcv_data
        high = max([d.get('high_price', 0) for d in recent])
        low = min([d.get('low_price', float('inf')) for d in recent])
        current_price = ohlcv_data[-1].get('close_price', 0)
        
        # トレンド判定
        if len(self.psar) == 0:
            # 初期化
            if current_price > (high + low) / 2:
                self.psar_trend = 'up'
                sar = low
                self.psar_ep = high
            else:
                self.psar_trend = 'down'
                sar = high
                self.psar_ep = low
            self.psar_af = start_af
        else:
            # 前回のSAR値から継続
            sar = self.psar[-1] if self.psar else low
        
        # SAR値を記録
        self.psar.append(sar)
        
        # Bull/Bear SAR を記録
        if self.psar_trend == 'up':
            self.psarbull.append(sar)
            self.psarbear.append(None)
        else:
            self.psarbull.append(None)
            self.psarbear.append(sar)
        
        return
