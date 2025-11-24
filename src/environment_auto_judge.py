#!/usr/bin/env python3
"""
Task 7: 環境自動判定ロジック
過去30日のレジーム分析 → Phase2 有効/無効の自動判定
"""

import sys
import os
import json
from datetime import datetime, timedelta

sys.path.insert(0, 'src')

from price_data_management import PriceDataManagement
from regime_detector import RegimeDetector
from logger import Logger

class EnvironmentAutoJudgement:
    """市場環境を自動分析し、Phase 2 (段階的フィルタリング)の適用判定を行う"""
    
    def __init__(self):
        self.logger = Logger()
        self.price_data_management = PriceDataManagement()
        self.regime_detector = RegimeDetector()
        
    def analyze_past_30days(self):
        """
        過去30日間のレジーム分析
        Returns: {
            'sideways_ratio': float (0-1),
            'weak_trend_ratio': float (0-1),
            'strong_trend_ratio': float (0-1),
            'avg_volatility_ratio': float,
            'volatility_stability': str ('stable'|'increasing'|'decreasing'),
            'recommendation': str ('enable_phase2'|'disable_phase2'|'manual_review'),
            'reasoning': str,
            'details': dict
        }
        """
        
        # 過去30日のデータを取得
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)
        
        self.logger.log(f"[環境自動判定] 分析期間: {start_date.date()} ～ {end_date.date()}")
        
        # キャッシュからデータを取得 (実装では実際の OHLCV データを使用)
        # ここではシミュレーション用に統計値を生成
        
        regime_history = []
        volatility_ratios = []
        trend_strengths = []
        
        # 過去データをスキャン（カレンダー日数でループ）
        current_date = start_date
        while current_date <= end_date:
            # 実装: cache.db または API から該当日のOHLCVを取得
            # ここではモック実装
            regime = self._get_regime_for_date(current_date)
            if regime:
                regime_history.append(regime)
            current_date += timedelta(days=1)
        
        # レジーム分布を計算
        if regime_history:
            total_bars = len(regime_history)
            sideways_count = sum(1 for r in regime_history if r == 'SIDEWAYS')
            weak_count = sum(1 for r in regime_history if r == 'WEAK_TREND')
            strong_count = sum(1 for r in regime_history if r == 'STRONG_TREND')
            
            sideways_ratio = sideways_count / total_bars
            weak_ratio = weak_count / total_bars
            strong_ratio = strong_count / total_bars
            
            # 判定ロジック
            recommendation = self._make_recommendation(
                sideways_ratio, weak_ratio, strong_ratio
            )
            
            result = {
                'sideways_ratio': round(sideways_ratio, 3),
                'weak_trend_ratio': round(weak_ratio, 3),
                'strong_trend_ratio': round(strong_ratio, 3),
                'avg_volatility_ratio': 1.0,  # プレースホルダー
                'volatility_stability': 'stable',  # プレースホルダー
                'recommendation': recommendation,
                'reasoning': self._get_reasoning(sideways_ratio, recommendation),
                'details': {
                    'total_bars': total_bars,
                    'sideways_count': sideways_count,
                    'weak_trend_count': weak_count,
                    'strong_trend_count': strong_count,
                    'analysis_period': f"{start_date.date()} to {end_date.date()}"
                }
            }
            
            return result
        else:
            return {
                'recommendation': 'manual_review',
                'reasoning': 'データ不足のため手動確認が必要',
                'details': {}
            }
    
    def _get_regime_for_date(self, date):
        """指定日のレジームを取得（モック実装）"""
        # 実装: cache.db から該当日の OHLCV を取得して regime_detector で計算
        # ここではシミュレーション用のプレースホルダー
        return 'WEAK_TREND'
    
    def _make_recommendation(self, sideways_ratio, weak_ratio, strong_ratio):
        """レジーム分布から推奨判定を生成"""
        
        if sideways_ratio >= 0.30:
            # SIDEWAYS が30%以上 → Phase 2 有効化推奨
            return 'enable_phase2'
        elif strong_ratio >= 0.50 and sideways_ratio < 0.10:
            # STRONG_TREND が50%以上かつ SIDEWAYS が10%未満 → Phase 2 無効化推奨
            return 'disable_phase2'
        else:
            # 判定が難しい中間的な環境 → 手動レビュー
            return 'manual_review'
    
    def _get_reasoning(self, sideways_ratio, recommendation):
        """推奨判定の根拠を説明"""
        if recommendation == 'enable_phase2':
            return (
                f"SIDEWAYS比率が {sideways_ratio*100:.1f}% で、"
                "30%以上です。保合い環境が多いため、"
                "Phase 2 の段階的フィルタリングが有効に機能します。"
            )
        elif recommendation == 'disable_phase2':
            return (
                f"STRONG_TREND が継続している環境です。"
                "エントリーを過度に制限することは機会損失につながります。"
                "Phase 2 は無効化し、通常取引を継続してください。"
            )
        else:
            return (
                "レジーム分布が中間的です。市場環境の詳細を確認した上で、"
                "Phase 2 の有効/無効を手動で判定してください。"
            )
    
    def generate_config_recommendation(self, result):
        """推奨 config.ini 設定を生成"""
        
        recommendation = result.get('recommendation', 'manual_review')
        
        if recommendation == 'enable_phase2':
            config_text = (
                "# Task 7 自動判定結果: Phase 2 有効化推奨\n"
                "# 根拠: SIDEWAYS比率が高い保合い環境\n"
                "[Strategy]\n"
                "regime_detection_enabled = True\n"
                "graduated_sizing_enabled = True\n"
                "sideways_position_multiplier = 0.75\n"
                "weak_trend_position_multiplier = 1.0\n"
                "strong_trend_position_multiplier = 1.25\n"
            )
        elif recommendation == 'disable_phase2':
            config_text = (
                "# Task 7 自動判定結果: Phase 2 無効化推奨\n"
                "# 根拠: STRONG_TREND が継続している\n"
                "[Strategy]\n"
                "regime_detection_enabled = False\n"
                "graduated_sizing_enabled = False\n"
            )
        else:
            config_text = (
                "# Task 7 自動判定結果: 手動レビュー推奨\n"
                "# 環境分析結果が中間的なため、手動で判定してください\n"
                "[Strategy]\n"
                "# regime_detection_enabled = False  # デフォルト\n"
                "# graduated_sizing_enabled = False\n"
            )
        
        return config_text
    
    def report(self, result):
        """分析結果をレポート"""
        
        print("="*70)
        print("📊 環境自動判定レポート (Task 7)")
        print("="*70)
        print()
        
        print(f"【分析期間】{result['details'].get('analysis_period', 'N/A')}")
        print()
        
        print("【レジーム分布】")
        print(f"  SIDEWAYS:     {result.get('sideways_ratio', 0)*100:5.1f}%")
        print(f"  WEAK_TREND:   {result.get('weak_trend_ratio', 0)*100:5.1f}%")
        print(f"  STRONG_TREND: {result.get('strong_trend_ratio', 0)*100:5.1f}%")
        print()
        
        print("【推奨判定】")
        rec = result.get('recommendation', 'unknown')
        if rec == 'enable_phase2':
            print(f"  ✅ Phase 2 有効化推奨")
        elif rec == 'disable_phase2':
            print(f"  ❌ Phase 2 無効化推奨")
        else:
            print(f"  ⚠️  手動レビュー推奨")
        print()
        
        print("【根拠】")
        print(f"  {result.get('reasoning', 'N/A')}")
        print()
        
        print("【推奨設定】")
        config = self.generate_config_recommendation(result)
        for line in config.split('\n'):
            if line:
                print(f"  {line}")
        print()
        
        print("="*70)


def main():
    """環境自動判定の実行"""
    
    print("\n🚀 Task 7: 環境自動判定 (EnvironmentAutoJudgement) 開始\n")
    
    judger = EnvironmentAutoJudgement()
    
    # 過去30日を分析
    result = judger.analyze_past_30days()
    
    # レポート出力
    judger.report(result)
    
    # JSON で work_reports に保存
    output_file = f"work_reports/environment_auto_judgement_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    os.makedirs('work_reports', exist_ok=True)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ 分析結果を保存: {output_file}\n")


if __name__ == '__main__':
    main()
