"""market_regime_detector.py のレグレッションテスト

MarketRegimeDetector の主要APIが例外なく動作し、戻り値の形式が崩れていないことを確認します。
"""

import os
import sys
import json
from datetime import datetime

WORKSPACE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(WORKSPACE_ROOT, "src")
sys.path.insert(0, SRC_DIR)


def _make_ohlcv(n=60, start=100.0, step=0.2, range_size=5.0):
    ohlcv = []
    price = start
    for i in range(n):
        price += step
        ohlcv.append(
            {
                "open_price": price,
                "high_price": price + range_size,
                "low_price": price - range_size,
                "close_price": price,
                "Volume": 1000,
            }
        )
    return ohlcv


def test_detector_import_and_construct():
    try:
        from market_regime_detector import MarketRegimeDetector

        det = MarketRegimeDetector()
        return True, f"✅ MarketRegimeDetector 初期化OK: atr_period={det.atr_period}"
    except Exception as e:
        return False, f"❌ MarketRegimeDetector インポート/初期化失敗: {e}"


def test_detect_regime_output_shape():
    try:
        from market_regime_detector import MarketRegimeDetector

        det = MarketRegimeDetector()
        data = _make_ohlcv(60)
        result = det.detect_regime(data)

        required_keys = {"regime", "atr_ratio", "swing_direction", "confidence", "reason"}
        missing = required_keys - set(result.keys())
        if missing:
            return False, f"❌ detect_regime 戻り値キー不足: {sorted(missing)}"

        if result["regime"] not in ["RANGING", "TRENDING_UP", "TRENDING_DOWN", "TRANSITION"]:
            return False, f"❌ regime 値が不正: {result['regime']}"

        if not (0.0 <= float(result["confidence"]) <= 1.0):
            return False, f"❌ confidence 範囲外: {result['confidence']}"

        return True, f"✅ detect_regime 形式OK: regime={result['regime']}, conf={result['confidence']:.2f}"
    except Exception as e:
        return False, f"❌ detect_regime 実行失敗: {e}"


def test_detect_regime_simple_output_shape():
    try:
        from market_regime_detector import MarketRegimeDetector

        det = MarketRegimeDetector()
        data = _make_ohlcv(80, step=0.0)  # 横ばい
        result = det.detect_regime_simple(data, lookback_period=20)

        required_keys = {"regime", "range_ratio", "confidence", "reason"}
        missing = required_keys - set(result.keys())
        if missing:
            return False, f"❌ detect_regime_simple 戻り値キー不足: {sorted(missing)}"

        if result["regime"] not in ["RANGING", "TRENDING_UP", "TRENDING_DOWN", "TRANSITION"]:
            return False, f"❌ regime 値が不正: {result['regime']}"

        if not (0.0 <= float(result["confidence"]) <= 1.0):
            return False, f"❌ confidence 範囲外: {result['confidence']}"

        return True, f"✅ detect_regime_simple 形式OK: regime={result['regime']}, conf={result['confidence']:.2f}"
    except Exception as e:
        return False, f"❌ detect_regime_simple 実行失敗: {e}"


def run_all_tests():
    tests = [
        ("MarketRegimeDetector import/初期化", test_detector_import_and_construct),
        ("detect_regime 戻り値形式", test_detect_regime_output_shape),
        ("detect_regime_simple 戻り値形式", test_detect_regime_simple_output_shape),
    ]

    results = []
    for test_name, test_func in tests:
        try:
            passed, message = test_func()
            results.append(
                {
                    "name": test_name,
                    "passed": passed,
                    "message": message,
                    "timestamp": datetime.now().isoformat(),
                }
            )
            print(message)
        except Exception as e:
            results.append(
                {
                    "name": test_name,
                    "passed": False,
                    "message": f"❌ テスト実行エラー: {e}",
                    "timestamp": datetime.now().isoformat(),
                }
            )
            print(f"❌ テスト実行エラー ({test_name}): {e}")

    return results


if __name__ == "__main__":
    print("=" * 70)
    print("🧪 market_regime_detector.py レグレッションテスト")
    print("=" * 70)

    results = run_all_tests()
    passed_count = sum(1 for r in results if r["passed"])
    total_count = len(results)

    print()
    print(f"📊 結果: {passed_count}/{total_count} 成功")

    results_dir = os.path.join(WORKSPACE_ROOT, "docs/regression_test_results")
    os.makedirs(results_dir, exist_ok=True)

    with open(
        os.path.join(results_dir, "test_market_regime_detector_regression.json"),
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            {
                "file": "market_regime_detector.py",
                "total": total_count,
                "passed": passed_count,
                "results": results,
                "timestamp": datetime.now().isoformat(),
            },
            f,
            ensure_ascii=False,
            indent=2,
        )

    sys.exit(0 if passed_count == total_count else 1)
