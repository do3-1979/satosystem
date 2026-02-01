"""new_indicators.py のレグレッションテスト

既存の test_indicators_regression.py は "new_indicators" ではなく "indicators" 名で管理されるため、
ソース-テスト対応チェック（prj-test-update）で missing 扱いになります。

ここでは NewIndicators の基本 API が動作するスモークテストを追加します。
"""

import os
import sys
import json
from datetime import datetime

WORKSPACE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(WORKSPACE_ROOT, "src")
sys.path.insert(0, SRC_DIR)


def test_import_and_basic_calcs():
    try:
        import numpy as np
        from new_indicators import NewIndicators

        ind = NewIndicators()

        # データ不足
        upper, mid, lower = ind.calc_bollinger_bands([100, 101, 102], period=20)
        if (upper, mid, lower) != (None, None, None):
            return False, "❌ BB: データ不足時に None が返りません"

        rsi = ind.calc_rsi([100, 101, 102], period=14)
        if rsi is not None:
            return False, "❌ RSI: データ不足時に None が返りません"

        # 十分なデータ
        close = list(range(100, 131))
        upper, mid, lower = ind.calc_bollinger_bands(close, period=20, num_std=2.0)
        if not (np.isfinite(upper) and np.isfinite(mid) and np.isfinite(lower) and upper > mid > lower):
            return False, f"❌ BB 計算が不正: {upper}, {mid}, {lower}"

        rsi = ind.calc_rsi(close, period=14)
        if rsi is None or not (0.0 <= float(rsi) <= 100.0):
            return False, f"❌ RSI 計算が不正: {rsi}"

        return True, f"✅ NewIndicators 計算OK: BB(mid={mid:.2f}), RSI={rsi:.2f}"

    except Exception as e:
        return False, f"❌ NewIndicators スモーク失敗: {e}"


def run_all_tests():
    tests = [
        ("NewIndicators import/基本計算", test_import_and_basic_calcs),
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
    print("🧪 new_indicators.py レグレッションテスト")
    print("=" * 70)

    results = run_all_tests()
    passed_count = sum(1 for r in results if r["passed"])
    total_count = len(results)

    print()
    print(f"📊 結果: {passed_count}/{total_count} 成功")

    results_dir = os.path.join(WORKSPACE_ROOT, "docs/regression_test_results")
    os.makedirs(results_dir, exist_ok=True)

    with open(
        os.path.join(results_dir, "test_new_indicators_regression.json"),
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            {
                "file": "new_indicators.py",
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
