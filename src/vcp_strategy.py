"""
VCP (Volatility Contraction Pattern) Strategy

ボラティリティ収縮パターンを検出し、ブレイクアウト時にエントリーする戦略。
2025年型の高ボラティリティ市場に対応するため開発。

理論根拠:
- ATRが収縮（低ボラティリティ）→ エネルギー蓄積
- その後のブレイクアウト → 高確率でトレンド継続
- 2025年は高ボラティリティのため、VCP発生頻度が高い

戦略ロジック:
1. ATR収縮検出: 現在ATR < 過去20期間のATR平均 × contraction_ratio
2. Donchianブレイク確認: 高値更新でロング
3. エントリー条件: VCP検出 + Donchianブレイク + PVOフィルター
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from logger import Logger
from config import Config
import statistics

class VCPStrategy:
    """
    Volatility Contraction Pattern (VCP) 戦略クラス
    
    ボラティリティ収縮後のブレイクアウトを狙う戦略。
    2025年型の高ボラティリティ・レンジ相場に適応。
    """
    
    def __init__(self):
        self.logger = Logger()
        
        # VCP検出パラメータ（config.iniから読み込み）
        self.enable_vcp_strategy = Config.get_enable_vcp_strategy()
        self.vcp_contraction_ratio = Config.get_vcp_contraction_ratio()  # 例: 0.75 (75%以下に収縮)
        self.vcp_lookback_period = Config.get_vcp_lookback_period()      # 例: 20 (20期間の平均ATR)
        self.vcp_breakout_threshold = Config.get_vcp_breakout_threshold()  # 例: 1.02 (2%のブレイク)
        self.vcp_min_confidence = Config.get_vcp_min_confidence()        # 例: 0.6 (最低信頼度)
        
        # 状態変数
        self.vcp_signal = 0  # 0: no signal, 1: buy signal, -1: sell signal
        self.vcp_confidence = 0.0
        self.vcp_reason = ''
        self.is_vcp_detected = False  # VCP検出状態
        
    def detect_vcp(self, candles):
        """
        VCP（ボラティリティ収縮パターン）を検出
        
        Args:
            candles (list): OHLCV足データのリスト
            
        Returns:
            dict: {
                'detected': bool,
                'confidence': float,
                'reason': str,
                'current_atr': float,
                'avg_atr': float,
                'contraction_ratio': float
            }
        """
        if not self.enable_vcp_strategy:
            return {
                'detected': False,
                'confidence': 0.0,
                'reason': 'VCP strategy disabled',
                'current_atr': 0.0,
                'avg_atr': 0.0,
                'contraction_ratio': 0.0
            }
        
        # 十分なデータがない場合
        if len(candles) < self.vcp_lookback_period + 15:
            return {
                'detected': False,
                'confidence': 0.0,
                'reason': f'Insufficient data: {len(candles)} candles',
                'current_atr': 0.0,
                'avg_atr': 0.0,
                'contraction_ratio': 0.0
            }
        
        # ATR計算（直近14期間）
        current_atr = self._calculate_atr(candles[-14:])
        
        # 過去ATR平均計算（lookback期間）
        atr_values = []
        for i in range(self.vcp_lookback_period):
            lookback_idx = -(i + 15)  # 現在ATRより過去のATRを計算
            if abs(lookback_idx) > len(candles):
                break
            atr_14 = self._calculate_atr(candles[lookback_idx-14:lookback_idx])
            atr_values.append(atr_14)
        
        if len(atr_values) < self.vcp_lookback_period * 0.8:  # 80%以上のデータが必要
            return {
                'detected': False,
                'confidence': 0.0,
                'reason': f'Insufficient ATR data: {len(atr_values)} periods',
                'current_atr': current_atr,
                'avg_atr': 0.0,
                'contraction_ratio': 0.0
            }
        
        avg_atr = statistics.mean(atr_values)
        
        # 収縮率計算
        contraction_ratio = current_atr / avg_atr if avg_atr > 0 else 1.0
        
        # VCP検出判定
        is_contracting = contraction_ratio <= self.vcp_contraction_ratio
        
        # 信頼度計算（収縮が強いほど信頼度が高い）
        if is_contracting:
            # 収縮率が小さいほど信頼度が高い
            # 例: 0.60 → confidence 0.9, 0.70 → confidence 0.7, 0.75 → confidence 0.6
            confidence = min(1.0, (self.vcp_contraction_ratio - contraction_ratio) / self.vcp_contraction_ratio + 0.5)
            confidence = max(0.0, confidence)
            
            reason = f"VCP detected: ATR={current_atr:.2f}, Avg={avg_atr:.2f}, Ratio={contraction_ratio:.3f}"
        else:
            confidence = 0.0
            reason = f"No VCP: ATR={current_atr:.2f}, Avg={avg_atr:.2f}, Ratio={contraction_ratio:.3f} (>{self.vcp_contraction_ratio})"
        
        self.is_vcp_detected = is_contracting
        self.vcp_confidence = confidence
        self.vcp_reason = reason
        
        return {
            'detected': is_contracting,
            'confidence': confidence,
            'reason': reason,
            'current_atr': current_atr,
            'avg_atr': avg_atr,
            'contraction_ratio': contraction_ratio
        }
    
    def evaluate_entry(self, candles, donchian_high, donchian_low, current_price):
        """
        VCP戦略のエントリー判定
        
        Args:
            candles (list): OHLCV足データ
            donchian_high (float): Donchianチャネル上限
            donchian_low (float): Donchianチャネル下限
            current_price (float): 現在価格
            
        Returns:
            dict: {
                'signal': int (0=no signal, 1=buy, -1=sell),
                'confidence': float,
                'reason': str
            }
        """

        if not self.enable_vcp_strategy:
            return {'signal': 0, 'confidence': 0.0, 'reason': 'VCP strategy disabled'}
        
        # VCP検出
        vcp_result = self.detect_vcp(candles)
        
        if not vcp_result['detected']:
            self.vcp_signal = 0
            return {'signal': 0, 'confidence': 0.0, 'reason': vcp_result['reason']}
        
        # VCP検出済み → ブレイクアウト確認
        # Donchian highの1%以内ならブレイクアウトとみなす（既にDonchianシグナル発生済みのため）
        breakout_threshold = donchian_high * 0.99  # 1%以内ならOK
        is_breakout = current_price >= breakout_threshold
        
        if is_breakout:
            # エントリーシグナル生成
            signal = 1  # Buy signal
            confidence = vcp_result['confidence']
            reason = f"VCP + Breakout: price={current_price:.2f}, donchian={donchian_high:.2f}, {vcp_result['reason']}"
            
            self.vcp_signal = signal
            self.vcp_confidence = confidence
            self.vcp_reason = reason
            
            return {'signal': signal, 'confidence': confidence, 'reason': reason}
        else:
            # VCP検出済みだがブレイクアウト未発生
            reason = f"VCP detected but no breakout: price={current_price:.2f} < donchian={donchian_high:.2f}"
            self.vcp_signal = 0
            self.vcp_confidence = vcp_result['confidence']
            self.vcp_reason = reason
            
            return {'signal': 0, 'confidence': vcp_result['confidence'], 'reason': reason}
    
    def _calculate_atr(self, candles):
        """
        ATR (Average True Range) を計算
        
        Args:
            candles (list): OHLCV足データ（最低14期間必要）
            
        Returns:
            float: ATR値
        """
        if len(candles) < 2:
            return 0.0
        
        true_ranges = []
        for i in range(1, len(candles)):
            high = candles[i].get('high_price', candles[i].get('high', 0))
            low = candles[i].get('low_price', candles[i].get('low', 0))
            prev_close = candles[i-1].get('close_price', candles[i-1].get('close', 0))
            
            tr = max(
                high - low,
                abs(high - prev_close),
                abs(low - prev_close)
            )
            true_ranges.append(tr)
        
        if not true_ranges:
            return 0.0
        
        # ATRは直近14期間のTRの平均
        atr_period = min(14, len(true_ranges))
        return statistics.mean(true_ranges[-atr_period:])
    
    def get_signal(self):
        """現在のVCPシグナルを取得"""
        return self.vcp_signal
    
    def get_confidence(self):
        """現在のVCP信頼度を取得"""
        return self.vcp_confidence
    
    def get_reason(self):
        """現在のVCP判定理由を取得"""
        return self.vcp_reason
    
    def is_vcp_active(self):
        """VCP検出状態を取得"""
        return self.is_vcp_detected
