"""
RegimeDetector: 適応型市場レジーム検出

市場のボラティリティとトレンド強度から現在のレジームを分類し、
最適なパラメータセットを動的に選択します。

レジーム分類:
- STRONG_TREND: 強いトレンド、高ボラティリティ
- WEAK_TREND: 弱いトレンド、中程度ボラティリティ  
- SIDEWAYS: レンジ相場、低ボラティリティ

動的パラメータ:
- Keltner ATR乗数 (k2)
- Keltner EMA期間
- Entry Range
- Stop Range
- Leverage
"""

import numpy as np
from config import Config
from logger import Logger


class RegimeDetector:
    """
    市場レジームを検出し、動的にパラメータを調整するクラス
    """
    
    # レジーム定義
    STRONG_TREND = "STRONG_TREND"
    WEAK_TREND = "WEAK_TREND"
    SIDEWAYS = "SIDEWAYS"
    
    # レジーム別パラメータセット
    REGIME_PARAMETERS = {
        STRONG_TREND: {
            'keltner_atr_multiplier': 2.5,  # k2: 広めのバンド
            'keltner_ema_period': 20,
            'entry_range': 3.0,              # 広めのエントリー範囲
            'stop_range': 3.0,               # 広めのストップ
            'leverage': 100,                 # 高レバレッジ（強トレンドで積極的）
            'keltner_enabled': True,         # フィルタ有効
            'description': '強トレンド: 高ボラ、積極的'
        },
        WEAK_TREND: {
            'keltner_atr_multiplier': 2.0,  # k2: 標準
            'keltner_ema_period': 20,
            'entry_range': 2.0,              # 標準
            'stop_range': 2.0,               # 標準
            'leverage': 50,                  # 中レバレッジ
            'keltner_enabled': True,
            'description': '弱トレンド: 中ボラ、標準的'
        },
        SIDEWAYS: {
            'keltner_atr_multiplier': 1.5,  # k2: 狭めのバンド
            'keltner_ema_period': 20,
            'entry_range': 1.5,              # 狭めのエントリー範囲
            'stop_range': 1.5,               # 狭めのストップ
            'leverage': 20,                  # 低レバレッジ（慎重）
            'keltner_enabled': True,         # フィルタ有効（だまし回避）
            'description': 'レンジ: 低ボラ、慎重'
        }
    }
    
    # レジーム判定閾値（デフォルト値）
    VOLATILITY_HIGH_THRESHOLD = 1.2    # ボラティリティが平均の1.2倍以上
    VOLATILITY_LOW_THRESHOLD = 0.8     # ボラティリティが平均の0.8倍以下
    TREND_STRONG_THRESHOLD = 0.6       # トレンド強度が0.6以上
    TREND_WEAK_THRESHOLD = 0.3         # トレンド強度が0.3以下
    
    def __init__(self):
        self.logger = Logger()
        self.current_regime = self.WEAK_TREND  # デフォルト
        self.regime_history = []
        self.volatility_history = []
        self.trend_strength_history = []
        
        # 設定から閾値を読み込む（あれば上書き）
        try:
            config = Config.get_config()
            self.volatility_high_threshold = float(config['Strategy'].get(
                'regime_volatility_ratio_threshold_high', self.VOLATILITY_HIGH_THRESHOLD))
            self.volatility_low_threshold = float(config['Strategy'].get(
                'regime_volatility_ratio_threshold_low', self.VOLATILITY_LOW_THRESHOLD))
            self.trend_strong_threshold = float(config['Strategy'].get(
                'regime_trend_strength_threshold_strong', self.TREND_STRONG_THRESHOLD))
            self.trend_weak_threshold = float(config['Strategy'].get(
                'regime_trend_strength_threshold_weak', self.TREND_WEAK_THRESHOLD))
        except:
            # 設定読み込み失敗時はデフォルト値を使用
            self.volatility_high_threshold = self.VOLATILITY_HIGH_THRESHOLD
            self.volatility_low_threshold = self.VOLATILITY_LOW_THRESHOLD
            self.trend_strong_threshold = self.TREND_STRONG_THRESHOLD
            self.trend_weak_threshold = self.TREND_WEAK_THRESHOLD
        
        # ログ出力制御
        self._regime_change_count = 0
        self._last_logged_regime = None
        
    def detect_regime(self, price_data_management):
        """
        現在の市場レジームを検出
        
        Args:
            price_data_management: PriceDataManagement インスタンス
            
        Returns:
            str: レジーム名 (STRONG_TREND, WEAK_TREND, SIDEWAYS)
        """
        # ボラティリティを取得
        current_volatility = price_data_management.get_volatility()
        
        # OHLCV データを取得
        time_frame = Config.get_time_frame()
        ohlcv_data = price_data_management.get_ohlcv_data(time_frame)
        
        if len(ohlcv_data) < 50:
            # データ不足の場合はデフォルト
            return self.current_regime
        
        # トレンド強度を計算
        trend_strength = self._calculate_trend_strength(ohlcv_data)
        
        # ボラティリティ比率を計算（過去50期間の平均との比較）
        self.volatility_history.append(current_volatility)
        if len(self.volatility_history) > 50:
            self.volatility_history.pop(0)
        
        avg_volatility = np.mean(self.volatility_history)
        volatility_ratio = current_volatility / avg_volatility if avg_volatility > 0 else 1.0
        
        # トレンド強度履歴を記録
        self.trend_strength_history.append(trend_strength)
        if len(self.trend_strength_history) > 50:
            self.trend_strength_history.pop(0)
        
        # レジーム判定
        regime = self._classify_regime(volatility_ratio, trend_strength)
        
        # レジーム変更時のログ出力
        if regime != self.current_regime:
            self._regime_change_count += 1
            self.logger.log(
                f"[REGIME CHANGE] {self.current_regime} → {regime} "
                f"(Vol比={volatility_ratio:.2f}, Trend={trend_strength:.2f}) "
                f"#{self._regime_change_count}"
            )
            self.current_regime = regime
            self._last_logged_regime = regime
        
        # レジーム履歴を記録
        self.regime_history.append({
            'regime': regime,
            'volatility_ratio': volatility_ratio,
            'trend_strength': trend_strength,
            'volatility': current_volatility
        })
        if len(self.regime_history) > 100:
            self.regime_history.pop(0)
        
        return regime
    
    def _calculate_trend_strength(self, ohlcv_data):
        """
        トレンド強度を計算（ADX風の指標）
        
        Args:
            ohlcv_data: OHLCV データリスト
            
        Returns:
            float: トレンド強度 (0.0-1.0)
        """
        if len(ohlcv_data) < 20:
            return 0.5
        
        # 最近20期間の終値を取得
        closes = [bar['close_price'] for bar in ohlcv_data[-20:]]
        
        # 線形回帰の傾きを計算
        x = np.arange(len(closes))
        coeffs = np.polyfit(x, closes, 1)
        slope = coeffs[0]
        
        # 傾きを価格に対する比率に正規化
        avg_price = np.mean(closes)
        normalized_slope = abs(slope) / avg_price if avg_price > 0 else 0
        
        # トレンド強度を0-1の範囲にスケーリング
        # 1期間あたり1%の変化で強度1.0とする
        trend_strength = min(normalized_slope * 20, 1.0)
        
        return trend_strength
    
    def _classify_regime(self, volatility_ratio, trend_strength):
        """
        ボラティリティ比率とトレンド強度からレジームを分類
        
        動的STRONG_TREND判定:
        - 高ボラティリティ & 強トレンド → STRONG_TREND（従来通り）
        - 中程度ボラティリティ & 非常に強トレンド(>0.7) → STRONG_TREND（トレンド継続時に適用）
        
        Args:
            volatility_ratio: ボラティリティ比率（平均に対する比率）
            trend_strength: トレンド強度 (0.0-1.0)
            
        Returns:
            str: レジーム名
        """
        # パターン1: 高ボラティリティ & 強トレンド → STRONG_TREND（従来通り）
        if volatility_ratio >= self.volatility_high_threshold and \
           trend_strength >= self.trend_strong_threshold:
            return self.STRONG_TREND
        
        # パターン2: トレンド非常に強い(>0.7)場合はSTRONG_TRENDに昇格
        # （トレンド継続環境での過度な制限を回避）
        if trend_strength > 0.7:
            return self.STRONG_TREND
        
        # 低ボラティリティ & 弱トレンド → SIDEWAYS
        if volatility_ratio <= self.volatility_low_threshold and \
           trend_strength <= self.trend_weak_threshold:
            return self.SIDEWAYS
        
        # その他 → WEAK_TREND（デフォルト）
        return self.WEAK_TREND
    
    def get_current_regime(self):
        """現在のレジームを取得"""
        return self.current_regime
    
    def get_regime_parameters(self, regime=None):
        """
        指定されたレジームのパラメータセットを取得
        
        Args:
            regime: レジーム名（Noneの場合は現在のレジーム）
            
        Returns:
            dict: パラメータセット
        """
        if regime is None:
            regime = self.current_regime
        
        return self.REGIME_PARAMETERS.get(regime, self.REGIME_PARAMETERS[self.WEAK_TREND])
    
    def get_regime_stats(self):
        """
        レジーム統計情報を取得
        
        Returns:
            dict: 統計情報
        """
        if not self.regime_history:
            return {}
        
        # レジーム別の出現回数をカウント
        regime_counts = {}
        for record in self.regime_history:
            regime = record['regime']
            regime_counts[regime] = regime_counts.get(regime, 0) + 1
        
        total = len(self.regime_history)
        regime_percentages = {
            regime: (count / total * 100) for regime, count in regime_counts.items()
        }
        
        return {
            'current_regime': self.current_regime,
            'regime_change_count': self._regime_change_count,
            'regime_percentages': regime_percentages,
            'history_length': total,
            'avg_volatility_ratio': np.mean([r['volatility_ratio'] for r in self.regime_history]),
            'avg_trend_strength': np.mean([r['trend_strength'] for r in self.regime_history])
        }
