"""
ATR最適化分析スクリプト

バックテストデータから各トレード時のATR比率を抽出し、
ボックス相場と損失四半期、トレンド相場と利益四半期のATR比率を比較して
最適な閾値を見つけます。
"""

import sys
import os
import json
import glob
import pandas as pd
from collections import defaultdict

# プロジェクトのsrcディレクトリを追加
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from config import Config
from price_data_management import PriceDataManagement
from market_regime_detector import MarketRegimeDetector


def get_latest_backtest_log():
    """最新のバックテストログファイルを取得"""
    log_files = glob.glob('src/logs/backtest_summary_*.json')
    if not log_files:
        return None
    log_files.sort(reverse=True)
    return log_files[0]


def analyze_atr_by_quarter():
    """
    各四半期のATR比率を分析
    """
    print("\n" + "="*80)
    print("📊 ATR比率分析 - 各四半期の平均ATR比率を計算")
    print("="*80)
    
    quarters = [
        ('Q1 2024', '2024-01-01', '2024-03-31', 921.85, 'PROFIT'),
        ('Q2 2024', '2024-04-01', '2024-06-30', -25.80, 'LOSS'),
        ('Q3 2024', '2024-07-01', '2024-09-30', -56.21, 'LOSS'),
        ('Q4 2024', '2024-10-01', '2024-12-31', 185.74, 'PROFIT'),
        ('Q1 2025', '2025-01-01', '2025-03-31', -172.30, 'LOSS'),
        ('Q2 2025', '2025-04-01', '2025-06-30', -123.88, 'LOSS'),
        ('Q3 2025', '2025-07-01', '2025-09-30', -79.36, 'LOSS'),
        ('Q4 2025', '2025-10-01', '2025-12-21', 254.32, 'PROFIT'),
    ]
    
    atr_analysis = defaultdict(list)
    
    for quarter_name, start_date, end_date, pnl, pnl_type in quarters:
        print(f"\n{quarter_name} ({start_date} ～ {end_date})")
        print(f"  損益: {pnl:+.2f} USD ({pnl_type})")
        
        try:
            # OHLCVデータを取得
            pdm = PriceDataManagement()
            ohlcv_data = pdm.get_ohlcv_data_by_time_frame(Config.get_time_frame())
            
            # 期間フィルタ
            import datetime as dt
            start_dt = dt.datetime.strptime(start_date, '%Y-%m-%d')
            end_dt = dt.datetime.strptime(end_date, '%Y-%m-%d')
            
            period_data = []
            for candle in ohlcv_data:
                candle_dt = dt.datetime.fromtimestamp(candle.get('timestamp', candle.get('time', 0)))
                if start_dt <= candle_dt <= end_dt:
                    period_data.append(candle)
            
            if len(period_data) < 30:
                print(f"  ⚠️ データ不足 ({len(period_data)} bars)")
                continue
            
            # ATR比率を計算
            detector = MarketRegimeDetector(atr_period=14, atr_ma_period=28, lookback_period=20)
            
            atr_ratios = []
            for i in range(28, len(period_data)):
                subset = period_data[:i+1]
                atr_current = detector.calculate_atr(subset, 14)
                atr_ma = detector.calculate_atr_ma(subset, 28)
                
                if atr_current and atr_ma and atr_ma > 0:
                    ratio = atr_current / atr_ma
                    atr_ratios.append(ratio)
            
            if atr_ratios:
                avg_ratio = sum(atr_ratios) / len(atr_ratios)
                min_ratio = min(atr_ratios)
                max_ratio = max(atr_ratios)
                
                atr_analysis[pnl_type].append({
                    'quarter': quarter_name,
                    'avg_ratio': avg_ratio,
                    'min_ratio': min_ratio,
                    'max_ratio': max_ratio,
                    'count': len(atr_ratios)
                })
                
                print(f"  ATR比率 - 平均: {avg_ratio:.3f}, 最小: {min_ratio:.3f}, 最大: {max_ratio:.3f}")
                print(f"  データ点数: {len(atr_ratios)}")
        
        except Exception as e:
            print(f"  ❌ エラー: {str(e)}")
    
    # 統計分析
    print("\n" + "="*80)
    print("📈 統計分析結果")
    print("="*80)
    
    for pnl_type in ['PROFIT', 'LOSS']:
        if atr_analysis[pnl_type]:
            ratios = [item['avg_ratio'] for item in atr_analysis[pnl_type]]
            avg = sum(ratios) / len(ratios)
            min_val = min(ratios)
            max_val = max(ratios)
            
            print(f"\n{pnl_type}四半期のATR比率:")
            for item in atr_analysis[pnl_type]:
                print(f"  {item['quarter']:8s}: {item['avg_ratio']:.3f}")
            
            print(f"\n{pnl_type}四半期の統計:")
            print(f"  平均: {avg:.3f}")
            print(f"  最小: {min_val:.3f}")
            print(f"  最大: {max_val:.3f}")
    
    # 推奨閾値
    print("\n" + "="*80)
    print("💡 推奨される閾値")
    print("="*80)
    
    profit_ratios = [item['avg_ratio'] for item in atr_analysis['PROFIT']]
    loss_ratios = [item['avg_ratio'] for item in atr_analysis['LOSS']]
    
    if profit_ratios and loss_ratios:
        profit_avg = sum(profit_ratios) / len(profit_ratios)
        loss_avg = sum(loss_ratios) / len(loss_ratios)
        
        # 現在の設定
        print(f"\n現在の設定:")
        print(f"  atr_range_threshold_lower = 0.75")
        print(f"  atr_range_threshold_upper = 1.25")
        
        # 分析結果に基づく推奨値
        print(f"\n分析結果:")
        print(f"  利益四半期の平均ATR比率: {profit_avg:.3f}")
        print(f"  損失四半期の平均ATR比率: {loss_avg:.3f}")
        print(f"  差分: {abs(profit_avg - loss_avg):.3f}")
        
        # 推奨閾値
        if profit_avg > loss_avg:
            # 利益四半期の方がATR比率が高い = トレンド相場
            recommended_lower = min(loss_ratios)
            recommended_upper = max(profit_ratios)
        else:
            # 損失四半期の方がATR比率が高い = ボックス相場が損失につながる
            recommended_lower = max(profit_ratios)
            recommended_upper = max(loss_ratios)
        
        print(f"\n推奨閾値:")
        print(f"  atr_range_threshold_lower = {recommended_lower:.2f}")
        print(f"  atr_range_threshold_upper = {recommended_upper:.2f}")
        print(f"  （ボックス相場判定: ATR比率 < {recommended_lower:.2f}）")
        print(f"  （トレンド相場判定: ATR比率 > {recommended_upper:.2f}）")


def test_atr_threshold(lower_threshold, upper_threshold):
    """
    指定された閾値でシミュレーション
    """
    print(f"\n{'='*80}")
    print(f"🧪 ATR閾値テスト: lower={lower_threshold:.2f}, upper={upper_threshold:.2f}")
    print(f"{'='*80}")
    
    quarters = [
        ('Q1 2024', 921.85, 'PROFIT'),
        ('Q2 2024', -25.80, 'LOSS'),
        ('Q3 2024', -56.21, 'LOSS'),
        ('Q4 2024', 185.74, 'PROFIT'),
        ('Q1 2025', -172.30, 'LOSS'),
        ('Q2 2025', -123.88, 'LOSS'),
        ('Q3 2025', -79.36, 'LOSS'),
        ('Q4 2025', 254.32, 'PROFIT'),
    ]
    
    print("\n四半期別判定結果:")
    print(f"{'期間':<10} {'損益(USD)':<12} {'判定':<15} {'推定改善効果':<15}")
    print("-" * 60)
    
    for quarter_name, pnl, actual_type in quarters:
        # 実際のATR比率（簡略版 - 平均値を使用）
        # 利益四半期: ATR比率高い傾向, 損失四半期: ATR比率低い傾向
        if actual_type == 'PROFIT':
            estimated_atr_ratio = 1.15  # トレンド
        else:
            estimated_atr_ratio = 0.85  # ボックス
        
        # 判定
        if estimated_atr_ratio < lower_threshold:
            regime = "RANGING (ボックス)"
            effect = "条件強化"
        elif estimated_atr_ratio > upper_threshold:
            regime = "TRENDING"
            effect = "通常進行"
        else:
            regime = "TRANSITION"
            effect = "様子見"
        
        print(f"{quarter_name:<10} {pnl:+8.2f}     {regime:<15} {effect:<15}")


if __name__ == "__main__":
    print("\n🔍 ATR最適化分析を開始します...")
    
    analyze_atr_by_quarter()
    
    # テスト: 異なる閾値でシミュレーション
    test_atr_threshold(0.80, 1.20)
    test_atr_threshold(0.70, 1.30)
    test_atr_threshold(0.85, 1.15)
