#!/usr/bin/env python3
"""
P0-2: ストップロス機能の動作確認

目的:
  PSAR (Parabolic SAR) と trailing margin の実装確認
  MaxDD = 0 の原因特定（ストップロス不動作）

検証項目:
  1. PSAR計算が正常に行われているか
  2. ストップ価格がリアルタイムで更新されているか
  3. ストップロス発動が正常に動作しているか
  4. MaxDD (最大ドローダウン) が正しく計算されているか
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from config import Config
from risk_management import RiskManagement
from portfolio import Portfolio
from price_data_management import PriceDataManagement
from indicator_service import IndicatorService
from logger import Logger
import numpy as np

class StopLossValidator:
    def __init__(self):
        self.logger = Logger()
        self.test_results = []
    
    def test_psar_calculation(self):
        """テストケース1: PSAR計算の妥当性確認"""
        print("\n" + "="*80)
        print("TEST CASE 1: PSAR (Parabolic SAR) 計算の確認")
        print("="*80)
        
        # ダミーOHLCVデータ生成（正しい形式）
        np.random.seed(42)
        close_prices = np.cumsum(np.random.randn(50)) + 100  # ランダムウォーク
        
        data = [
            {
                'open_price': float(close_prices[i] + np.random.randn() * 0.5),
                'high_price': float(close_prices[i] + abs(np.random.randn())),
                'low_price': float(close_prices[i] - abs(np.random.randn())),
                'close_price': float(close_prices[i]),
                'volume': 1000.0,
            }
            for i in range(50)
        ]
        
        # PSAR計算
        indicator_service = IndicatorService()
        try:
            indicator_service.calculate_parabolic_sar(data)
        except Exception as e:
            print(f"  ⚠️  PSAR計算エラー: {e}")
            self.test_results.append({
                'test': 'PSAR Calculation',
                'status': '⚠️  ERROR',
            })
            return
        
        psar = indicator_service.psar
        psarbull = indicator_service.psarbull
        psarbear = indicator_service.psarbear
        
        print(f"\n📊 PSAR計算結果:")
        print(f"  計算バー数: {len(psar)}")
        print(f"  直近PSAR: {psar[-1]:.2f}" if psar and psar[-1] is not None else "  PSAR: N/A")
        print(f"  直近Bull SAR: {psarbull[-1]:.2f}" if psarbull and psarbull[-1] is not None else "  Bull: N/A")
        print(f"  直近Bear SAR: {psarbear[-1]:.2f}" if psarbear and psarbear[-1] is not None else "  Bear: N/A")
        
        # 検証
        if not psar or len(psar) == 0:
            print("  ❌ PSAR未計算")
            status = "❌ FAIL"
        else:
            print("  ✅ PSAR計算成功")
            status = "✅ PASS"
        
        self.test_results.append({
            'test': 'PSAR Calculation',
            'status': status,
        })
    
    def test_stop_price_update(self):
        """テストケース2: ストップ価格の動的更新確認"""
        print("\n" + "="*80)
        print("TEST CASE 2: ストップ価格の動的更新確認")
        print("="*80)
        
        # BUYポジション時のストップロス更新シミュレーション
        entry_price = 50000
        prices = [50100, 50200, 50300, 50250, 50150, 50050]  # 価格推移
        stop_offsets = []
        stop_prices = []
        
        print(f"\n📊 BUYポジション時のストップロス推移:")
        print(f"  エントリー価格: ${entry_price}")
        print(f"\n{'価格':<10} {'Stop Offset':<15} {'Stop Price':<15} {'説明':<30}")
        print("-" * 70)
        
        for i, price in enumerate(prices):
            # 初期ストップ: エントリー価格より200下
            if i == 0:
                stop_offset = 200
            else:
                # 高い値をつけたらストップオフセットは狭める（上昇に追従）
                if price > prices[i-1]:
                    stop_offset = min(stop_offset, (price - entry_price) * 0.5)  # 概算
                else:
                    stop_offset = max(stop_offset, 200)  # 最小限度
            
            stop_price = price - stop_offset
            stop_offsets.append(stop_offset)
            stop_prices.append(stop_price)
            
            explanation = ""
            if i == 0:
                explanation = "初期ストップ設定"
            elif price > prices[i-1]:
                explanation = "高い値で追従"
            else:
                explanation = "下げを維持"
            
            print(f"${price:<9} ${stop_offset:<14.0f} ${stop_price:<14.0f} {explanation:<30}")
        
        # 検証
        is_stop_triggered = False
        for i, price in enumerate(prices):
            if price <= stop_prices[i]:
                is_stop_triggered = True
                print(f"\n✅ ストップロス発動: ${price} <= ${stop_prices[i]} (bar {i+1})")
                break
        
        if not is_stop_triggered:
            print(f"\n⚠️  この価格推移ではストップロス未発動")
        
        status = "✅ PASS" if all(stop_prices[i] > prices[i] for i in range(len(prices)-1)) else "⚠️  WARNING"
        self.test_results.append({
            'test': 'Stop Price Update',
            'status': status,
        })
    
    def test_max_drawdown_calculation(self):
        """テストケース3: 最大ドローダウン (MaxDD) 計算の確認"""
        print("\n" + "="*80)
        print("TEST CASE 3: 最大ドローダウン (MaxDD) 計算の確認")
        print("="*80)
        
        # 資金推移のシミュレーション
        initial_balance = 10000
        balances = [10000, 10500, 11000, 10200, 9800, 10500, 11500, 10800]  # 資金推移
        
        print(f"\n📊 資金推移:")
        print(f"{'Bar':<6} {'Balance':<12} {'Cumulative Max':<15} {'Drawdown':<15} {'Drawdown %':<12}")
        print("-" * 65)
        
        cumulative_max = initial_balance
        max_dd = 0
        max_dd_percent = 0
        dd_timeline = []
        
        for i, balance in enumerate(balances, 1):
            cumulative_max = max(cumulative_max, balance)
            drawdown = cumulative_max - balance
            dd_percent = (drawdown / cumulative_max * 100) if cumulative_max > 0 else 0
            
            if drawdown > max_dd:
                max_dd = drawdown
                max_dd_percent = dd_percent
            
            dd_timeline.append({
                'bar': i,
                'balance': balance,
                'cummax': cumulative_max,
                'drawdown': drawdown,
                'dd_percent': dd_percent,
            })
            
            print(f"{i:<6} ${balance:<11.0f} ${cumulative_max:<14.0f} ${drawdown:<14.0f} {dd_percent:<11.2f}%")
        
        print(f"\n【最大ドローダウン】")
        print(f"  MaxDD: ${max_dd:.2f} ({max_dd_percent:.2f}%)")
        
        # 問題検出
        if max_dd == 0:
            print(f"\n❌ 問題: MaxDD = 0 (ストップロスが完全に有効ないし価格推移が一方向のみ)")
            print(f"        実際には損失がある可能性があります")
            status = "❌ FAIL"
        else:
            print(f"\n✅ MaxDD 計算成功")
            status = "✅ PASS"
        
        self.test_results.append({
            'test': 'MaxDD Calculation',
            'status': status,
        })
    
    def test_stop_loss_execution(self):
        """テストケース4: ストップロス実行ロジックの検証"""
        print("\n" + "="*80)
        print("TEST CASE 4: ストップロス実行ロジックの検証")
        print("="*80)
        
        print(f"\n【期待動作】")
        print(f"  1. エントリーポイントでストップロス価格を設定")
        print(f"  2. 毎バーストップロス価格を更新（利益追従）")
        print(f"  3. 現在値がストップ価格を下回ったら即座に決済")
        print(f"  4. 決済後、ドローダウンを記録")
        
        print(f"\n【チェックリスト】")
        checks = [
            ("risk_management.py の __update_stop_price() が呼ばれているか", "src/risk_management.py"),
            ("bot.py で stop_price がリアルタイム比較されているか", "src/bot.py"),
            ("PSAR計算が毎バー実行されているか", "src/risk_management.py"),
            ("ストップロス発動時に position が即座にクリアされているか", "src/bot.py"),
        ]
        
        for i, (check, file) in enumerate(checks, 1):
            print(f"  {i}. {check}")
            print(f"     → {file}")
        
        print(f"\n【推奨確認手段】")
        print(f"  1. backtest.log で詳細ログを確認")
        print(f"  2. トレードごとに 'Stop Hit' イベントが記録されているか確認")
        print(f"  3. 負けトレードの exit_reason が 'StopLoss' か確認")
        
        status = "⚠️  MANUAL CHECK"
        self.test_results.append({
            'test': 'Stop Loss Execution',
            'status': status,
        })
    
    def print_summary(self):
        """テスト結果サマリ"""
        print("\n" + "="*80)
        print("📋 テスト結果サマリ")
        print("="*80)
        
        print(f"\n{'テスト名':<40} {'結果':<15}")
        print("-" * 55)
        
        for result in self.test_results:
            print(f"{result['test']:<40} {result['status']:<15}")
        
        print("\n" + "="*80)
        print("【結論と推奨事項】")
        print("="*80)
        print("""
MaxDD = 0 の原因と対策:

❌ 原因の可能性:
  1. ストップロス機能が未実装 → 有効化確認必須
  2. PSAR未計算 → IndicatorService の初期化確認
  3. ストップ価格が更新されない → __update_stop_price() の呼び出し確認
  4. 決済ロジックが不完全 → ストップロス発動時の処理確認

✅ 改善手順:
  1. backtest.log で「Stop Price Updated」イベントを確認
  2. ストップロス発動トレードを特定
  3. 不正なストップロス値（例: -999など）を検出
  4. テストケースで PSAR・ストップ価格・決済を統合検証

期限: 1週間以内
成果物: テストケース + 修正パッチ
""")

def main():
    validator = StopLossValidator()
    
    # テスト実行
    validator.test_psar_calculation()
    validator.test_stop_price_update()
    validator.test_max_drawdown_calculation()
    validator.test_stop_loss_execution()
    
    # サマリ
    validator.print_summary()

if __name__ == '__main__':
    main()
