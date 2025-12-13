#!/usr/bin/env python3
"""
新指標計算ロジックのレグレッションテスト

Bollinger Bands, RSI, SMA, MACD の計算結果が妥当かを検証します。

テスト項目:
1. 計算結果が数値的に有効か（NaN, Inf がないか）
2. サンプルデータに対して期待値が得られるか
3. エッジケース（データ不足）への対応が正しいか
4. 指標値が理論的な範囲内か
5. シグナル評価ロジックが正しいか
"""

import sys
import os
import json
from datetime import datetime

# ワークスペース設定
WORKSPACE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(WORKSPACE_ROOT, "src")
sys.path.insert(0, SRC_DIR)

import numpy as np
from new_indicators import NewIndicators


class IndicatorsRegressionTest:
    """新指標計算ロジックのレグレッションテスト"""
    
    def __init__(self):
        self.results = {
            "tests": [],
            "summary": {
                "total": 0,
                "passed": 0,
                "failed": 0
            },
            "timestamp": datetime.now().isoformat()
        }
    
    def run_all_tests(self):
        """すべてのテストを実行"""
        print("=" * 80)
        print("🧪 新指標計算ロジック レグレッションテスト")
        print("=" * 80 + "\n")
        
        # テストグループの実行
        self.test_bollinger_bands()
        self.test_rsi()
        self.test_sma()
        self.test_macd()
        self.test_edge_cases()
        self.test_signal_evaluation()
        
        # 結果を表示
        self.print_summary()
        
        return self.results
    
    def test_bollinger_bands(self):
        """ボリンジャーバンド計算のテスト"""
        print("📊 1. ボリンジャーバンド (BB) のテスト")
        print("-" * 80)
        
        # テストデータ（上昇トレンド）
        close_prices = [100, 101, 102, 101, 103, 102, 104, 103, 105, 104, 
                       106, 105, 107, 106, 108, 107, 109, 108, 110, 109, 111]
        
        indicators = NewIndicators()
        upper, middle, lower = indicators.calc_bollinger_bands(close_prices, period=5, num_std=2.0)
        
        tests = [
            {
                "name": "BB上限値が有効か",
                "condition": upper is not None and np.isfinite(upper),
                "expected": "上限値が数値（有限）",
                "actual": f"upper={upper}"
            },
            {
                "name": "BB中央値（SMA）が有効か",
                "condition": middle is not None and np.isfinite(middle),
                "expected": "中央値が数値（有限）",
                "actual": f"middle={middle}"
            },
            {
                "name": "BB下限値が有効か",
                "condition": lower is not None and np.isfinite(lower),
                "expected": "下限値が数値（有限）",
                "actual": f"lower={lower}"
            },
            {
                "name": "BB: 上限 > 中央 > 下限 の大小関係",
                "condition": upper > middle > lower,
                "expected": "上限 > 中央 > 下限",
                "actual": f"{upper} > {middle} > {lower}"
            },
            {
                "name": "BB: 中央値が close_prices 最後の5つの平均",
                "condition": abs(middle - np.mean(close_prices[-5:])) < 1e-10,
                "expected": "期待値と一致",
                "actual": f"期待値={np.mean(close_prices[-5:])}, 計算値={middle}"
            },
            {
                "name": "BB: データ不足時に None を返す",
                "condition": indicators.calc_bollinger_bands([100, 101, 102], period=5) == (None, None, None),
                "expected": "(None, None, None)",
                "actual": f"{indicators.calc_bollinger_bands([100, 101, 102], period=5)}"
            }
        ]
        
        self._record_tests("ボリンジャーバンド", tests)
    
    def test_rsi(self):
        """RSI計算のテスト"""
        print("\n📊 2. RSI (Relative Strength Index) のテスト")
        print("-" * 80)
        
        # テストデータ（上昇トレンド）
        close_prices = [100, 101, 102, 101, 103, 102, 104, 103, 105, 104, 
                       106, 105, 107, 106, 108, 107, 109, 108, 110, 109, 111]
        
        indicators = NewIndicators()
        rsi = indicators.calc_rsi(close_prices, period=5)
        
        tests = [
            {
                "name": "RSI が計算される",
                "condition": rsi is not None,
                "expected": "RSI が None でない",
                "actual": f"RSI={rsi}"
            },
            {
                "name": "RSI が有効な数値",
                "condition": rsi is not None and np.isfinite(rsi),
                "expected": "RSI が有限数値",
                "actual": f"RSI={rsi}"
            },
            {
                "name": "RSI が 0-100 範囲内",
                "condition": rsi is not None and 0 <= rsi <= 100,
                "expected": "0 <= RSI <= 100",
                "actual": f"RSI={rsi}"
            },
            {
                "name": "RSI: 上昇トレンドで RSI > 50",
                "condition": rsi is not None and rsi > 50,
                "expected": "RSI > 50",
                "actual": f"RSI={rsi}"
            },
            {
                "name": "RSI: データ不足時に None を返す",
                "condition": indicators.calc_rsi([100, 101, 102], period=5) is None,
                "expected": "None",
                "actual": f"{indicators.calc_rsi([100, 101, 102], period=5)}"
            },
            {
                "name": "RSI: 単調増加データで RSI が高い",
                "condition": indicators.calc_rsi([100, 101, 102, 103, 104, 105, 106], period=3) > 80,
                "expected": "RSI > 80",
                "actual": f"{indicators.calc_rsi([100, 101, 102, 103, 104, 105, 106], period=3)}"
            }
        ]
        
        self._record_tests("RSI", tests)
    
    def test_sma(self):
        """SMA計算のテスト"""
        print("\n📊 3. SMA (Simple Moving Average) のテスト")
        print("-" * 80)
        
        close_prices = [100, 101, 102, 101, 103, 102, 104, 103, 105, 104, 
                       106, 105, 107, 106, 108, 107, 109, 108, 110, 109, 111]
        
        indicators = NewIndicators()
        sma_fast, sma_slow = indicators.calc_sma(close_prices, fast_period=5, slow_period=10)
        
        tests = [
            {
                "name": "SMA Fast が計算される",
                "condition": sma_fast is not None,
                "expected": "SMA Fast が None でない",
                "actual": f"sma_fast={sma_fast}"
            },
            {
                "name": "SMA Slow が計算される",
                "condition": sma_slow is not None,
                "expected": "SMA Slow が None でない",
                "actual": f"sma_slow={sma_slow}"
            },
            {
                "name": "SMA Fast が有効な数値",
                "condition": sma_fast is not None and np.isfinite(sma_fast),
                "expected": "SMA Fast が有限数値",
                "actual": f"sma_fast={sma_fast}"
            },
            {
                "name": "SMA Slow が有効な数値",
                "condition": sma_slow is not None and np.isfinite(sma_slow),
                "expected": "SMA Slow が有限数値",
                "actual": f"sma_slow={sma_slow}"
            },
            {
                "name": "SMA: 上昇トレンドで SMA_fast > SMA_slow",
                "condition": sma_fast is not None and sma_slow is not None and sma_fast > sma_slow,
                "expected": "SMA_fast > SMA_slow",
                "actual": f"sma_fast={sma_fast}, sma_slow={sma_slow}"
            },
            {
                "name": "SMA Fast が最後の5個の平均",
                "condition": sma_fast is not None and abs(sma_fast - np.mean(close_prices[-5:])) < 1e-10,
                "expected": "期待値と一致",
                "actual": f"期待値={np.mean(close_prices[-5:])}, 計算値={sma_fast}"
            },
            {
                "name": "SMA: データ不足で Slow = None",
                "condition": indicators.calc_sma([100, 101, 102], fast_period=5, slow_period=10)[1] is None,
                "expected": "SMA Slow = None",
                "actual": f"{indicators.calc_sma([100, 101, 102], fast_period=5, slow_period=10)}"
            }
        ]
        
        self._record_tests("SMA", tests)
    
    def test_macd(self):
        """MACD計算のテスト"""
        print("\n📊 4. MACD (Moving Average Convergence Divergence) のテスト")
        print("-" * 80)
        
        # テストデータ（十分な長さ）
        close_prices = list(range(100, 150))  # 100 から 149
        
        indicators = NewIndicators()
        macd, signal, histogram = indicators.calc_macd(close_prices, fast_period=5, slow_period=10, signal_period=3)
        
        tests = [
            {
                "name": "MACD が計算される",
                "condition": macd is not None,
                "expected": "MACD が None でない",
                "actual": f"macd={macd}"
            },
            {
                "name": "Signal が計算される",
                "condition": signal is not None,
                "expected": "Signal が None でない",
                "actual": f"signal={signal}"
            },
            {
                "name": "Histogram が計算される",
                "condition": histogram is not None,
                "expected": "Histogram が None でない",
                "actual": f"histogram={histogram}"
            },
            {
                "name": "MACD が有効な数値",
                "condition": macd is not None and np.isfinite(macd),
                "expected": "MACD が有限数値",
                "actual": f"macd={macd}"
            },
            {
                "name": "Signal が有効な数値",
                "condition": signal is not None and np.isfinite(signal),
                "expected": "Signal が有限数値",
                "actual": f"signal={signal}"
            },
            {
                "name": "Histogram = MACD - Signal",
                "condition": histogram is not None and macd is not None and signal is not None and abs(histogram - (macd - signal)) < 1e-10,
                "expected": "histogram = macd - signal",
                "actual": f"histogram={histogram}, macd-signal={macd - signal}"
            },
            {
                "name": "MACD: データ不足時に None を返す",
                "condition": indicators.calc_macd([100, 101, 102], fast_period=5, slow_period=10) == (None, None, None),
                "expected": "(None, None, None)",
                "actual": f"{indicators.calc_macd([100, 101, 102], fast_period=5, slow_period=10)}"
            }
        ]
        
        self._record_tests("MACD", tests)
    
    def test_edge_cases(self):
        """エッジケースのテスト"""
        print("\n📊 5. エッジケースのテスト")
        print("-" * 80)
        
        indicators = NewIndicators()
        
        # 空データ
        empty_data = []
        
        # 最小限のデータ
        min_data = [100]
        
        tests = [
            {
                "name": "空配列での BB 計算",
                "condition": indicators.calc_bollinger_bands(empty_data, period=5) == (None, None, None),
                "expected": "(None, None, None)",
                "actual": f"{indicators.calc_bollinger_bands(empty_data, period=5)}"
            },
            {
                "name": "単一データでの RSI 計算",
                "condition": indicators.calc_rsi(min_data, period=5) is None,
                "expected": "None",
                "actual": f"{indicators.calc_rsi(min_data, period=5)}"
            },
            {
                "name": "単一データでの SMA 計算",
                "condition": indicators.calc_sma(min_data, fast_period=5, slow_period=10) == (None, None),
                "expected": "(None, None)",
                "actual": f"{indicators.calc_sma(min_data, fast_period=5, slow_period=10)}"
            },
            {
                "name": "bb upper/middle/lower getters がデフォルト値を返す",
                "condition": indicators.get_bb_upper() == 0 and indicators.get_bb_middle() == 0 and indicators.get_bb_lower() == 0,
                "expected": "デフォルト値 (0, 0, 0)",
                "actual": f"({indicators.get_bb_upper()}, {indicators.get_bb_middle()}, {indicators.get_bb_lower()})"
            },
            {
                "name": "RSI getter がデフォルト値を返す",
                "condition": indicators.get_rsi() == 50,
                "expected": "50",
                "actual": f"{indicators.get_rsi()}"
            },
            {
                "name": "SMA getter がデフォルト値を返す",
                "condition": indicators.get_sma_fast() == 0 and indicators.get_sma_slow() == 0,
                "expected": "(0, 0)",
                "actual": f"({indicators.get_sma_fast()}, {indicators.get_sma_slow()})"
            }
        ]
        
        self._record_tests("エッジケース", tests)
    
    def test_signal_evaluation(self):
        """シグナル評価ロジックのテスト"""
        print("\n📊 6. シグナル評価ロジックのテスト")
        print("-" * 80)
        
        # 上昇トレンドデータ
        close_prices = [100, 101, 102, 101, 103, 102, 104, 103, 105, 104, 
                       106, 105, 107, 106, 108, 107, 109, 108, 110, 109, 111]
        
        indicators = NewIndicators()
        
        # 各指標を計算
        indicators.calc_bollinger_bands(close_prices, period=5)
        indicators.calc_rsi(close_prices, period=5)
        indicators.calc_sma(close_prices, fast_period=5, slow_period=10)
        indicators.calc_macd(close_prices, fast_period=5, slow_period=10, signal_period=3)
        
        # BB シグナル（現在価格が BB 中央付近）
        bb_signal = indicators.evaluate_bollinger_signal(close_prices[-1])
        
        # RSI シグナル
        rsi_signal = indicators.evaluate_rsi_signal()
        
        # SMA シグナル
        sma_signal = indicators.evaluate_sma_signal(close_prices[-1])
        
        # MACD シグナル
        macd_signal = indicators.evaluate_macd_signal()
        
        tests = [
            {
                "name": "BB シグナルが dict を返す",
                "condition": isinstance(bb_signal, dict) and "signal" in bb_signal and "type" in bb_signal,
                "expected": "dict with 'signal' and 'type'",
                "actual": f"{bb_signal}"
            },
            {
                "name": "RSI シグナルが dict を返す",
                "condition": isinstance(rsi_signal, dict) and "signal" in rsi_signal and "type" in rsi_signal,
                "expected": "dict with 'signal' and 'type'",
                "actual": f"{rsi_signal}"
            },
            {
                "name": "SMA シグナルが dict を返す",
                "condition": isinstance(sma_signal, dict) and "signal" in sma_signal and "trend" in sma_signal,
                "expected": "dict with 'signal' and 'trend'",
                "actual": f"{sma_signal}"
            },
            {
                "name": "MACD シグナルが dict を返す",
                "condition": isinstance(macd_signal, dict) and "signal" in macd_signal and "type" in macd_signal,
                "expected": "dict with 'signal' and 'type'",
                "actual": f"{macd_signal}"
            },
            {
                "name": "上昇トレンドで SMA が Bullish シグナル",
                "condition": sma_signal.get("trend") == "bullish",
                "expected": "trend = 'bullish'",
                "actual": f"{sma_signal}"
            },
            {
                "name": "上昇トレンドで RSI が 50 以上",
                "condition": indicators.get_rsi() >= 50,
                "expected": "RSI >= 50",
                "actual": f"RSI = {indicators.get_rsi()}"
            }
        ]
        
        self._record_tests("シグナル評価", tests)
    
    def _record_tests(self, group_name, tests):
        """テスト結果を記録"""
        passed_count = 0
        
        for test in tests:
            passed = test["condition"]
            if passed:
                passed_count += 1
                print(f"  ✅ {test['name']}")
            else:
                print(f"  ❌ {test['name']}")
                print(f"     期待値: {test['expected']}")
                print(f"     実際: {test['actual']}")
            
            # numpy型をPython型に変換してJSON保存可能にする
            actual_str = str(test["actual"])
            if isinstance(test["actual"], np.ndarray):
                actual_str = test["actual"].tolist()
            elif isinstance(test["actual"], (np.floating, np.integer)):
                actual_str = float(test["actual"]) if isinstance(test["actual"], np.floating) else int(test["actual"])
            
            self.results["tests"].append({
                "group": group_name,
                "name": test["name"],
                "passed": passed,
                "expected": str(test["expected"]),
                "actual": actual_str
            })
            
            self.results["summary"]["total"] += 1
            if passed:
                self.results["summary"]["passed"] += 1
            else:
                self.results["summary"]["failed"] += 1
        
        print(f"  📊 {group_name}: {passed_count}/{len(tests)} 成功\n")
    
    def print_summary(self):
        """テスト結果のサマリーを表示"""
        summary = self.results["summary"]
        
        print("=" * 80)
        print("📈 テスト結果サマリー")
        print("=" * 80)
        print(f"  総テスト数: {summary['total']}")
        print(f"  ✅ 成功: {summary['passed']}")
        print(f"  ❌ 失敗: {summary['failed']}")
        print(f"  成功率: {summary['passed']/summary['total']*100:.1f}%")
        
        if summary['failed'] == 0:
            print("\n  🎯 ステータス: ✅ ALL PASS")
        else:
            print(f"\n  🎯 ステータス: ⚠️ {summary['failed']} 個のテスト失敗")
        
        print("=" * 80 + "\n")


def save_regression_results(results):
    """レグレッション結果を JSON に保存"""
    results_dir = os.path.join(WORKSPACE_ROOT, "docs/regression_test_results")
    os.makedirs(results_dir, exist_ok=True)
    
    # numpy型をPython型に変換
    def convert_numpy_types(obj):
        if isinstance(obj, dict):
            return {k: convert_numpy_types(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [convert_numpy_types(item) for item in obj]
        elif isinstance(obj, (np.bool_, np.integer, np.floating)):
            return obj.item()
        else:
            return obj
    
    # 既存フォーマットに合わせてレジストレーション結果を変換
    summary = results["summary"]
    test_results = [
        {
            "name": test["name"],
            "group": test["group"],
            "passed": test["passed"],
            "expected": test["expected"],
            "actual": test["actual"]
        }
        for test in results["tests"]
    ]
    
    output_data = {
        "file": "new_indicators.py",
        "total": summary["total"],
        "passed": summary["passed"],
        "results": test_results,
        "timestamp": datetime.now().isoformat()
    }
    
    output_data = convert_numpy_types(output_data)
    
    output_file = os.path.join(results_dir, "test_indicators_regression.json")
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
    
    print(f"✅ レグレッション結果を保存: {output_file}\n")
    
    return output_file


if __name__ == "__main__":
    # テストを実行
    tester = IndicatorsRegressionTest()
    results = tester.run_all_tests()
    
    # 結果を保存
    save_regression_results(results)
    
    # スクリプト終了コード
    sys.exit(0 if results['summary']['failed'] == 0 else 1)
