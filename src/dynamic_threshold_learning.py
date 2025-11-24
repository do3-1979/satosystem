#!/usr/bin/env python3
"""
Task 10: 動的基準学習システム
過去データから最適な threshold を導出し、自動更新する
"""

import sys
import os
import json
import numpy as np
from datetime import datetime, timedelta

sys.path.insert(0, 'src')

from logger import Logger

class DynamicThresholdLearning:
    """過去データから volatility_ratio と trend_strength の最適閾値を導出"""
    
    def __init__(self):
        self.logger = Logger()
        
        # 現在の固定閾値
        self.current_vol_threshold = 1.2
        self.current_trend_threshold = 0.6
    
    def learn_optimal_thresholds(self, historical_data, lookback_days=30):
        """
        過去データから最適な閾値を導出
        
        Args:
            historical_data: {
                'dates': [...],
                'volatility_ratios': [...],
                'trend_strengths': [...],
                'pnl': [...],
                'win_rates': [...]
            }
            lookback_days: 学習期間（日数）
        
        Returns:
            {
                'optimal_vol_threshold': float,
                'optimal_trend_threshold': float,
                'vol_percentile': int,
                'trend_percentile': int,
                'expected_improvement': float,
                'confidence_score': float,
                'recommendation': str
            }
        """
        
        vol_ratios = np.array(historical_data.get('volatility_ratios', []))
        trend_strengths = np.array(historical_data.get('trend_strengths', []))
        win_rates = np.array(historical_data.get('win_rates', []))
        pnls = np.array(historical_data.get('pnl', []))
        
        if len(vol_ratios) < 10:
            return {
                'recommendation': 'insufficient_data',
                'message': f'データポイント不足（{len(vol_ratios)}<10）。学習を延期してください。'
            }
        
        # 最適な percentile を探索
        best_vol_threshold = None
        best_trend_threshold = None
        best_score = -np.inf
        
        for vol_percentile in range(40, 80, 5):
            for trend_percentile in range(40, 80, 5):
                # その percentile での threshold を計算
                vol_thresh = np.percentile(vol_ratios, vol_percentile)
                trend_thresh = np.percentile(trend_strengths, trend_percentile)
                
                # その threshold での期待スコアを計算
                score = self._calculate_effectiveness_score(
                    vol_ratios, trend_strengths, win_rates, pnls,
                    vol_thresh, trend_thresh
                )
                
                if score > best_score:
                    best_score = score
                    best_vol_threshold = vol_thresh
                    best_trend_threshold = trend_thresh
                    best_vol_percentile = vol_percentile
                    best_trend_percentile = trend_percentile
        
        # 現在の閾値との比較
        improvement = best_score - self._calculate_effectiveness_score(
            vol_ratios, trend_strengths, win_rates, pnls,
            self.current_vol_threshold, self.current_trend_threshold
        )
        
        result = {
            'optimal_vol_threshold': round(best_vol_threshold, 3),
            'optimal_trend_threshold': round(best_trend_threshold, 3),
            'vol_percentile': best_vol_percentile,
            'trend_percentile': best_trend_percentile,
            'current_vol_threshold': self.current_vol_threshold,
            'current_trend_threshold': self.current_trend_threshold,
            'expected_improvement': round(improvement, 4),
            'confidence_score': min(1.0, best_score / 100),  # 0-1 に正規化
            'recommendation': self._get_recommendation(improvement, best_score),
            'analysis_period': f"{lookback_days}日間"
        }
        
        return result
    
    def _calculate_effectiveness_score(self, vol_ratios, trend_strengths, 
                                       win_rates, pnls, vol_thresh, trend_thresh):
        """
        given threshold での効果スコアを計算
        スコア = (Win Rate平均 + PnL平均 / 10) / 2
        """
        
        # threshold に基づいて regime を判定
        regimes = []
        for vol, trend in zip(vol_ratios, trend_strengths):
            if vol >= vol_thresh:
                regime = 'STRONG_TREND'
            elif trend >= trend_thresh:
                regime = 'WEAK_TREND'
            else:
                regime = 'SIDEWAYS'
            regimes.append(regime)
        
        # regime ごとに効果を集計
        strong_indices = [i for i, r in enumerate(regimes) if r == 'STRONG_TREND']
        weak_indices = [i for i, r in enumerate(regimes) if r == 'WEAK_TREND']
        sideways_indices = [i for i, r in enumerate(regimes) if r == 'SIDEWAYS']
        
        score = 0
        
        # STRONG_TREND では高い Win Rate が望ましい
        if strong_indices:
            strong_wr = np.mean(win_rates[strong_indices])
            score += strong_wr * 0.4  # 重み: 40%
        
        # WEAK_TREND では中程度の Win Rate
        if weak_indices:
            weak_wr = np.mean(win_rates[weak_indices])
            score += weak_wr * 0.3  # 重み: 30%
        
        # SIDEWAYS では low Win Rate でもいい（取引を控える）
        if sideways_indices:
            sideways_wr = np.mean(win_rates[sideways_indices])
            score += sideways_wr * 0.1  # 重み: 10%
        
        return score
    
    def _get_recommendation(self, improvement, best_score):
        """改善度合いから推奨を生成"""
        
        if best_score < 30:
            return 'insufficient_effectiveness'
        elif improvement > 5:
            return 'adopt_immediately'
        elif improvement > 1:
            return 'adopt_gradually'
        elif improvement < -2:
            return 'revert_to_current'
        else:
            return 'maintain_current'
    
    def generate_updated_config(self, result):
        """新しい閾値でのconfigを生成"""
        
        if result.get('recommendation') in ['insufficient_data', 'maintain_current']:
            return None
        
        config = {
            'volatility_ratio_threshold': result['optimal_vol_threshold'],
            'trend_strength_threshold': result['optimal_trend_threshold'],
            'effective_from': datetime.now().isoformat(),
            'learning_period': result.get('analysis_period', 'N/A'),
            'expected_improvement': result.get('expected_improvement', 0),
            'confidence': result.get('confidence_score', 0)
        }
        
        return config
    
    def report(self, result):
        """学習結果をレポート"""
        
        print("="*70)
        print("🧠 動的基準学習レポート (Task 10)")
        print("="*70)
        print()
        
        if result.get('recommendation') == 'insufficient_data':
            print(f"⚠️  {result.get('message', 'データ不足')}")
            print()
            return
        
        print(f"【学習期間】{result.get('analysis_period', 'N/A')}")
        print()
        
        print("【現在の固定閾値】")
        print(f"  Volatility Ratio:  {result.get('current_vol_threshold', 1.2)}")
        print(f"  Trend Strength:    {result.get('current_trend_threshold', 0.6)}")
        print()
        
        print("【導出された最適閾値】")
        print(f"  Volatility Ratio:  {result.get('optimal_vol_threshold', 'N/A')} "
              f"(P{result.get('vol_percentile', 'N/A')})")
        print(f"  Trend Strength:    {result.get('optimal_trend_threshold', 'N/A')} "
              f"(P{result.get('trend_percentile', 'N/A')})")
        print()
        
        print("【効果予測】")
        improvement = result.get('expected_improvement', 0)
        if improvement > 0:
            print(f"  ✅ 期待改善度: +{improvement:.4f} ポイント")
        elif improvement < 0:
            print(f"  ⚠️  期待悪化度: {improvement:.4f} ポイント")
        else:
            print(f"  ➡️  変化なし")
        print(f"  信頼度: {result.get('confidence_score', 0)*100:.1f}%")
        print()
        
        print("【推奨】")
        rec = result.get('recommendation', 'unknown')
        if rec == 'adopt_immediately':
            print("  🚀 即座に新しい閾値を採用してください")
        elif rec == 'adopt_gradually':
            print("  📈 段階的に新しい閾値に移行してください")
        elif rec == 'maintain_current':
            print("  ➡️  現在の閾値を継続してください")
        elif rec == 'revert_to_current':
            print("  ⬅️  現在の閾値に戻してください")
        else:
            print(f"  ℹ️  {rec}")
        print()
        
        print("="*70)


def main():
    """動的基準学習の実行"""
    
    print("\n🧠 Task 10: 動的基準学習システム開始\n")
    
    # モック用の過去30日データを生成
    np.random.seed(42)
    days = 30
    historical_data = {
        'dates': [(datetime.now() - timedelta(days=i)).date() for i in range(days)],
        'volatility_ratios': np.random.uniform(0.8, 1.5, days).tolist(),
        'trend_strengths': np.random.uniform(0.3, 0.9, days).tolist(),
        'win_rates': np.random.uniform(0.2, 0.6, days).tolist(),
        'pnl': np.random.normal(0, 100, days).tolist()
    }
    
    learner = DynamicThresholdLearning()
    result = learner.learn_optimal_thresholds(historical_data, lookback_days=30)
    
    # レポート出力
    learner.report(result)
    
    # JSON で保存
    output_file = f"work_reports/dynamic_threshold_learning_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    os.makedirs('work_reports', exist_ok=True)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ 学習結果を保存: {output_file}\n")


if __name__ == '__main__':
    main()
