"""vcp_strategy.py のレグレッションテスト

VCPStrategy の検出/エントリー評価が例外なく動作し、戻り値形式が崩れていないことを確認します。
"""

import os
import sys
import json
from datetime import datetime

WORKSPACE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(WORKSPACE_ROOT, "src")
sys.path.insert(0, SRC_DIR)


def _make_ohlcv(n=80, start=100.0, step=0.1, range_size=3.0):
    candles = []
    price = start
    for _ in range(n):
        price += step
        candles.append(
            {
                "high_price": price + range_size,
                "low_price": price - range_size,
                "close_price": price,
            }
        )
    return candles


def test_import_and_construct():
    try:
        from vcp_strategy import VCPStrategy

        s = VCPStrategy()
        return True, f"✅ VCPStrategy 初期化OK: enabled={getattr(s, 'enable_vcp_strategy', None)}"
    except Exception as e:
        return False, f"❌ VCPStrategy インポート/初期化失敗: {e}"


def test_detect_vcp_output_shape():
    try:
        from vcp_strategy import VCPStrategy

        s = VCPStrategy()
        candles = _make_ohlcv(80)
        result = s.detect_vcp(candles)

        required_keys = {"detected", "confidence", "reason", "current_atr", "avg_atr", "contraction_ratio"}
        missing = required_keys - set(result.keys())
        if missing:
            return False, f"❌ detect_vcp 戻り値キー不足: {sorted(missing)}"

        if not (0.0 <= float(result["confidence"]) <= 1.0):
            return False, f"❌ confidence 範囲外: {result['confidence']}"

        return True, f"✅ detect_vcp 形式OK: detected={result['detected']}, conf={result['confidence']:.2f}"

    except Exception as e:
        return False, f"❌ detect_vcp 実行失敗: {e}"


def test_evaluate_entry_output_shape():
    try:
        from vcp_strategy import VCPStrategy

        s = VCPStrategy()
        candles = _make_ohlcv(80)
        current_price = candles[-1]["close_price"]

        result = s.evaluate_entry(
            candles=candles,
            donchian_high=current_price * 1.01,
            donchian_low=current_price * 0.99,
            current_price=current_price,
        )

        required_keys = {"signal", "confidence", "reason"}
        missing = required_keys - set(result.keys())
        if missing:
            return False, f"❌ evaluate_entry 戻り値キー不足: {sorted(missing)}"

        if int(result["signal"]) not in [-1, 0, 1]:
            return False, f"❌ signal 値が不正: {result['signal']}"

        return True, f"✅ evaluate_entry 形式OK: signal={result['signal']}, conf={result['confidence']:.2f}"

    except Exception as e:
        return False, f"❌ evaluate_entry 実行失敗: {e}"


def run_all_tests():
    tests = [
        ("VCPStrategy import/初期化", test_import_and_construct),
        ("detect_vcp 戻り値形式", test_detect_vcp_output_shape),
        ("evaluate_entry 戻り値形式", test_evaluate_entry_output_shape),
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
    print("🧪 vcp_strategy.py レグレッションテスト")
    print("=" * 70)

    results = run_all_tests()
    passed_count = sum(1 for r in results if r["passed"])
    total_count = len(results)

    print()
    print(f"📊 結果: {passed_count}/{total_count} 成功")

    results_dir = os.path.join(WORKSPACE_ROOT, "docs/regression_test_results")
    os.makedirs(results_dir, exist_ok=True)

    with open(
        os.path.join(results_dir, "test_vcp_strategy_regression.json"),
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            {
                "file": "vcp_strategy.py",
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
