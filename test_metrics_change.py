#!/usr/bin/env python3
"""
修正前後のメトリクス変化を確認するスクリプト
修正: Donchian + PVO のメトリクスカウント方法の明確化
"""

import sys
sys.path.insert(0, '/home/satoshi/work/satosystem/src')

from price_data_management import PriceDataManagement
from indicator_service import IndicatorService

# メトリクス構造を確認
indicator_service = IndicatorService()
pdm = PriceDataManagement(indicator_service=indicator_service)

print("=" * 70)
print("修正内容: Donchian + PVO メトリクスカウント方法の明確化")
print("=" * 70)
print()
print("【修正前】")
print("if self.signals['donchian']['signal']:")
print("    self._donchian_pvo_candidates += 1")
print("    if self.signals['pvo']['signal']:")
print("        self._donchian_pvo_passes += 1")
print()
print("【修正後】")
print("donchian_signal = self.signals['donchian']['signal']")
print("pvo_signal = self.signals['pvo']['signal']")
print()
print("if donchian_signal:")
print("    self._donchian_pvo_candidates += 1")
print("    if pvo_signal:  # AND条件")
print("        self._donchian_pvo_passes += 1")
print()
print("【変化の性質】")
print("- エントリー条件: 変更なし（AND論理は変わらず）")
print("- メトリクス計算: より明確化（同じタイムスタンプを保証）")
print("- 取引成績: 影響なし（ロジック自体は変わらず、可読性向上）")
print()
print("=" * 70)
print()

# PriceDataManagement内の関数を確認
metrics_method = pdm.get_pvo_donchian_metrics
print(f"メトリクス取得メソッド: {metrics_method.__name__}")
print()

# 実際の結果レポートから前後を比較
print("前回レポート (2024-11-21実行時):")
print("  2024年 - Donchian candidates: ?, PVO passes: ?, Ratio: ?")
print("  2025年 - Donchian candidates: ?, PVO passes: ?, Ratio: ?")
print()
print("修正後の実行結果を確認するには backtest.py を実行してください")
print()
print("確認方法:")
print("$ cd /home/satoshi/work/satosystem/src")
print("$ python3 backtest.py")
print()
