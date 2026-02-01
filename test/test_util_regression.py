"""util.py のレグレッションテスト

Util はログ抽出/Excel出力系で依存が多いので、ここでは import と主要メソッド存在確認のスモークを行います。
"""

import os
import sys
import json
from datetime import datetime

WORKSPACE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(WORKSPACE_ROOT, "src")
sys.path.insert(0, SRC_DIR)


def test_import_and_methods_exist():
    try:
        from util import Util

        required_methods = [
            "extract_and_export_logs",
            "generate_line_chart",
            "generate_line_profit_and_loss",
        ]

        missing = [m for m in required_methods if not hasattr(Util, m)]
        if missing:
            return False, f"❌ Util 欠落メソッド: {missing}"

        return True, f"✅ Util import/主要メソッドOK ({len(required_methods)} methods)"

    except Exception as e:
        return False, f"❌ Util import 失敗: {e}"


def run_all_tests():
    tests = [
        ("Util import/主要メソッド存在", test_import_and_methods_exist),
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
    print("🧪 util.py レグレッションテスト")
    print("=" * 70)

    results = run_all_tests()
    passed_count = sum(1 for r in results if r["passed"])
    total_count = len(results)

    print()
    print(f"📊 結果: {passed_count}/{total_count} 成功")

    results_dir = os.path.join(WORKSPACE_ROOT, "docs/regression_test_results")
    os.makedirs(results_dir, exist_ok=True)

    with open(
        os.path.join(results_dir, "test_util_regression.json"),
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            {
                "file": "util.py",
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
