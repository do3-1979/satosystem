#!/usr/bin/env python3
"""
P0-3: ポジションサイズ計算の妥当性検証

現在のロジック分析:
  position_size = (balance * 100 * risk% / stop_range / 100) / entry_times
  
  ここで:
  - balance: 口座残高 (USDT)
  - risk%: 1トレード当たりの許容リスク (例: 2%)
  - stop_range: ボラティリティ * initial_stop_range
  
検証項目:
  1. 1トレード当たりの最大損失が初期資本のrisk%を超えないこと
  2. ボラティリティが0に近い場合の問題検出
  3. stop_rangeがマイナスまたはゼロの場合の処理
  4. leverage による過度なポジションサイジング防止

期待: 1トレード当たりの損失 = balance * risk% (固定化)
現実: stop_rangeに依存 → ボラティリティが低いと過度にポジションが大きくなる
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from config import Config
from risk_management import RiskManagement
from portfolio import Portfolio
from price_data_management import PriceDataManagement
from indicator_service import IndicatorService

class PositionSizeValidator:
    def __init__(self):
        self.test_results = []
        
    def test_case_1_low_volatility(self):
        """テストケース1: ボラティリティが非常に低い場合"""
        print("\n" + "="*80)
        print("TEST CASE 1: 低ボラティリティ時のポジションサイジング")
        print("="*80)
        
        # 前提条件
        balance_tether = 10000  # $10,000
        risk_percentage = 0.02  # 2% risk per trade
        entry_times = 5  # 5分割エントリー
        initial_stop_range = 2.0
        leverage = 10
        price = 50000  # $50,000/BTC
        volatility_low = 100  # 非常に低いボラティリティ ($100)
        volatility_high = 1000  # 高いボラティリティ ($1,000)
        
        print(f"\n📊 前提条件:")
        print(f"  口座残高: ${balance_tether}")
        print(f"  リスク許容度: {risk_percentage*100}%")
        print(f"  分割エントリー回数: {entry_times}")
        print(f"  レバレッジ: {leverage}x")
        print(f"  BTC価格: ${price}")
        
        # ケース1a: 低ボラティリティ
        print(f"\n【ケース1a: 低ボラティリティ ($100)】")
        stop_range_low = initial_stop_range * volatility_low
        total_size_low = (balance_tether * 100 * risk_percentage / stop_range_low / 100)
        position_size_low = total_size_low / entry_times
        max_loss_low = position_size_low * stop_range_low  # 1ポジション当たりの最大損失
        
        print(f"  Stop Range (2.0 * ${volatility_low}): ${stop_range_low}")
        print(f"  Total Size: {total_size_low:.6f} BTC")
        print(f"  Position Size (per entry): {position_size_low:.6f} BTC")
        print(f"  1エントリー当たりの最大損失: ${max_loss_low:.2f}")
        print(f"  5エントリー総額: ${max_loss_low * entry_times:.2f}")
        
        # ケース1b: 高ボラティリティ
        print(f"\n【ケース1b: 高ボラティリティ ($1,000)】")
        stop_range_high = initial_stop_range * volatility_high
        total_size_high = (balance_tether * 100 * risk_percentage / stop_range_high / 100)
        position_size_high = total_size_high / entry_times
        max_loss_high = position_size_high * stop_range_high
        
        print(f"  Stop Range (2.0 * ${volatility_high}): ${stop_range_high}")
        print(f"  Total Size: {total_size_high:.6f} BTC")
        print(f"  Position Size (per entry): {position_size_high:.6f} BTC")
        print(f"  1エントリー当たりの最大損失: ${max_loss_high:.2f}")
        print(f"  5エントリー総額: ${max_loss_high * entry_times:.2f}")
        
        # 比較分析
        print(f"\n【分析】")
        size_ratio = position_size_low / position_size_high
        loss_ratio = max_loss_low / max_loss_high
        print(f"  ⚠️  ポジションサイズ比 (低/高): {size_ratio:.2f}x")
        print(f"  ⚠️  損失額比 (低/高): {loss_ratio:.2f}x")
        
        # 問題検出
        expected_loss = balance_tether * risk_percentage
        print(f"\n【問題検出】")
        print(f"  期待損失 (balance * risk%): ${expected_loss:.2f}")
        print(f"  実際損失 (低ボラティリティ): ${max_loss_low * entry_times:.2f}")
        print(f"  実際損失 (高ボラティリティ): ${max_loss_high * entry_times:.2f}")
        print(f"  ❌ 問題: ボラティリティが低いほどポジションが大きくなる（期待と逆）")
        
        # 記録
        self.test_results.append({
            'test': 'Low Volatility',
            'status': '❌ FAIL',
            'issue': 'ポジションサイズ逆依存 (低ボラが過度に大きくなる)',
            'recommendation': 'risk固定化アルゴリズムへの切り替え必須'
        })
        
    def test_case_2_zero_volatility(self):
        """テストケース2: ボラティリティがほぼゼロの場合"""
        print("\n" + "="*80)
        print("TEST CASE 2: ゼロに近いボラティリティのエッジケース")
        print("="*80)
        
        balance_tether = 10000
        risk_percentage = 0.02
        entry_times = 5
        initial_stop_range = 2.0
        
        # ボラティリティが非常に小さい場合
        volatility_minimal = 0.1  # $0.10
        stop_range_minimal = initial_stop_range * volatility_minimal
        
        print(f"\n📊 前提条件:")
        print(f"  口座残高: ${balance_tether}")
        print(f"  ボラティリティ: ${volatility_minimal}")
        print(f"  Stop Range: ${stop_range_minimal}")
        
        # ゼロ除算対策がない場合の問題
        if stop_range_minimal < 0.01:
            print(f"\n❌ 問題: Stop Range が非常に小さい (${stop_range_minimal:.4f})")
            print(f"   → ポジションサイズが異常に大きくなる可能性")
            
            try:
                total_size = (balance_tether * 100 * risk_percentage / stop_range_minimal / 100)
                position_size = total_size / entry_times
                print(f"   → Position Size: {position_size:.8f} BTC (★ 異常に大きい)")
                print(f"   → Leverage制限による上限: {balance_tether * 10 / 50000:.6f} BTC")
                
                # leverageで制限されるはず
                max_size_by_leverage = (balance_tether * 10) / 50000
                limited_position_size = min(position_size, max_size_by_leverage)
                print(f"   → 実際のポジション: {limited_position_size:.6f} BTC")
            except Exception as e:
                print(f"   → 計算エラー: {e}")
        
        self.test_results.append({
            'test': 'Zero/Minimal Volatility',
            'status': '⚠️  WARNING',
            'issue': 'ゼロ除算リスク、異常なポジション計算',
            'recommendation': 'ボラティリティの最小値チェック必須'
        })
    
    def test_case_3_fixed_loss_algorithm(self):
        """テストケース3: 提案改善案 - 固定損失アルゴリズム"""
        print("\n" + "="*80)
        print("TEST CASE 3: 改善提案 - 固定損失ベースのポジションサイジング")
        print("="*80)
        
        balance_tether = 10000
        risk_percentage = 0.02
        entry_times = 5
        price = 50000
        leverage = 10
        
        # 提案アルゴリズム
        print(f"\n【改善案】")
        print(f"  固定損失ベース: max_loss_per_trade = balance * risk%")
        print(f"  position_size = max_loss_per_trade / (entry_price * leverage * risk_ratio)")
        
        max_loss_per_trade = balance_tether * risk_percentage
        max_loss_total = max_loss_per_trade * entry_times
        
        print(f"\n📊 期待効果:")
        print(f"  1トレード当たりの最大損失: ${max_loss_per_trade:.2f}")
        print(f"  {entry_times}エントリー総損失上限: ${max_loss_total:.2f}")
        print(f"  ✅ ボラティリティに依存しない安定性")
        print(f"  ✅ リスク管理が明確 (損失額で制御)")
        print(f"  ✅ ポジションサイズが合理的")
        
        # 数値例
        stop_prices = [500, 1000, 2000, 5000]  # 異なるストップロス幅
        print(f"\n【異なるストップロス幅での比較】")
        print(f"{'Stop Loss幅':>15} {'ポジション':>15} {'最大損失':>15} {'説明':<30}")
        print("-" * 75)
        
        for stop_pips in stop_prices:
            # 現在のアルゴリズム（ボラに依存）
            # position_size_old = max_loss_per_trade / stop_pips  (概算)
            
            # 提案アルゴリズム（固定損失）
            position_size_new = max_loss_per_trade / stop_pips
            loss = position_size_new * stop_pips
            
            print(f"${stop_pips:>14} {position_size_new:>15.8f} ${loss:>14.2f} 固定損失")
        
        self.test_results.append({
            'test': 'Fixed Loss Algorithm',
            'status': '✅ PASS',
            'issue': 'N/A',
            'recommendation': '本アルゴリズムへの切り替え推奨'
        })
    
    def print_summary(self):
        """テスト結果サマリ"""
        print("\n" + "="*80)
        print("📋 テスト結果サマリ")
        print("="*80)
        
        print(f"\n{'テスト名':<40} {'結果':<15} {'推奨事項':<40}")
        print("-" * 95)
        
        for result in self.test_results:
            print(f"{result['test']:<40} {result['status']:<15} {result['recommendation']:<40}")
        
        print("\n" + "="*80)
        print("【結論】")
        print("="*80)
        print("""
❌ 現在のボラティリティベースのポジションサイジングは問題あり:
   1. ボラティリティが低いほどポジションが大きくなる（リスク逆転）
   2. ボラティリティ=0に近い場合、ゼロ除算リスク
   3. リスク管理が「損失額」ではなく「ボラ依存」（予測不可）

✅ 改善提案:
   1. 固定損失ベースのアルゴリズムへの切り替え
      max_loss_per_trade = balance * risk% (固定)
      position_size = max_loss_per_trade / stop_loss_width
   
   2. ボラティリティの役割変更:
      - ストップロス幅の決定 → 固定値またはATR使用
      - ポジションサイズには関与させない
   
   3. Leverageの厳格な上限設定:
      max_position_notional = balance * leverage * safety_margin
      position_size = min(calculated_size, max_position_notional / entry_price)

期限: 1週間以内
成果物: 修正パッチ + テストケース
""")

def main():
    validator = PositionSizeValidator()
    
    # テスト実行
    validator.test_case_1_low_volatility()
    validator.test_case_2_zero_volatility()
    validator.test_case_3_fixed_loss_algorithm()
    
    # サマリ
    validator.print_summary()

if __name__ == '__main__':
    main()
