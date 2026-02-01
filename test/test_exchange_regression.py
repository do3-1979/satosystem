"""exchange.py のレグレッションテスト

Exchange 基底クラスの存在と基本仕様（NotImplementedError）を確認します。
"""

import os
import sys
import json
from datetime import datetime

WORKSPACE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(WORKSPACE_ROOT, "src")
sys.path.insert(0, SRC_DIR)


def test_exchange_class_exists():
    try:
        from exchange import Exchange
        return True, "✅ Exchange クラスが存在します"
    except Exception as e:
        return False, f"❌ Exchange インポート失敗: {e}"


def test_exchange_methods_raise_not_implemented():
    try:
        from exchange import Exchange

        ex = Exchange(api_key="dummy", api_secret="dummy")

        ok = True
        messages = []

        try:
            ex.get_account_balance()
            ok = False
            messages.append("get_account_balance が例外を投げませんでした")
        except NotImplementedError:
            messages.append("✅ get_account_balance は NotImplementedError")

        try:
            ex.execute_order(
                symbol="BTC/USDT",
                side="buy",
                quantity=0.001,
                price=100.0,
                order_type="limit",
            )
            ok = False
            messages.append("execute_order が例外を投げませんでした")
        except NotImplementedError:
            messages.append("✅ execute_order は NotImplementedError")

        return ok, " / ".join(messages)
    except Exception as e:
        return False, f"❌ メソッド例外確認エラー: {e}"


def run_all_tests():
    tests = [
        ("Exchange クラス存在確認", test_exchange_class_exists),
        ("Exchange 抽象メソッド確認", test_exchange_methods_raise_not_implemented),
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
    print("🧪 exchange.py レグレッションテスト")
    print("=" * 70)

    results = run_all_tests()
    passed_count = sum(1 for r in results if r["passed"])
    total_count = len(results)

    print()
    print(f"📊 結果: {passed_count}/{total_count} 成功")

    results_dir = os.path.join(WORKSPACE_ROOT, "docs/regression_test_results")
    os.makedirs(results_dir, exist_ok=True)

    with open(os.path.join(results_dir, "test_exchange_regression.json"), "w", encoding="utf-8") as f:
        json.dump(
            {
                "file": "exchange.py",
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
