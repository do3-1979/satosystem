"""
order.py のレグレッションテスト

Order クラスの機能検証
"""

import os
import sys
import json
from datetime import datetime

# sys.path 設定
WORKSPACE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(WORKSPACE_ROOT, "src")
sys.path.insert(0, SRC_DIR)

# 分析結果ファイル
ANALYSIS_FILE = os.path.join(WORKSPACE_ROOT, "docs/analysis/src/order.json")


def load_analysis():
    """分析ファイルから仕様を読む"""
    with open(ANALYSIS_FILE, encoding="utf-8") as f:
        return json.load(f)


def test_order_class_exists():
    """Order クラスが存在することを確認"""
    try:
        from order import Order
        return True, f"✅ Order クラスが存在します"
    except ImportError as e:
        return False, f"❌ Order クラスのインポート失敗: {e}"


def test_order_key_methods():
    """Order の主要メソッドが存在することを確認"""
    try:
        from order import Order
        
        key_methods = [
            "__init__",
            "to_dict",
            "__str__"
        ]
        
        missing = []
        for method in key_methods:
            if not hasattr(Order, method):
                missing.append(method)
        
        if missing:
            return False, f"❌ 欠落主要メソッド: {missing}"
        
        return True, f"✅ 主要メソッド({len(key_methods)})すべて存在"
    except Exception as e:
        return False, f"❌ 主要メソッド確認エラー: {e}"


def test_order_instantiation():
    """Order インスタンス化確認"""
    try:
        from order import Order
        
        # 必要なパラメータでインスタンス化
        order = Order(
            symbol="BTC/USDT",
            side="BUY",
            price=100,
            quantity=1,
            order_type="limit"
        )
        
        if order:
            return True, f"✅ Order インスタンス化成功"
        else:
            return False, f"❌ Order インスタンス化失敗"
    except Exception as e:
        return False, f"❌ Order インスタンス化エラー: {e}"


def run_all_tests():
    """全テストを実行"""
    tests = [
        ("Order クラス存在確認", test_order_class_exists),
        ("Order 主要メソッド確認", test_order_key_methods),
        ("Order インスタンス化確認", test_order_instantiation),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            passed, message = test_func()
            results.append({
                "name": test_name,
                "passed": passed,
                "message": message,
                "timestamp": datetime.now().isoformat()
            })
            print(message)
        except Exception as e:
            results.append({
                "name": test_name,
                "passed": False,
                "message": f"❌ テスト実行エラー: {e}",
                "timestamp": datetime.now().isoformat()
            })
            print(f"❌ テスト実行エラー ({test_name}): {e}")
    
    return results


if __name__ == "__main__":
    print("=" * 70)
    print("🧪 order.py レグレッションテスト")
    print("=" * 70)
    results = run_all_tests()
    
    passed_count = sum(1 for r in results if r["passed"])
    total_count = len(results)
    
    print()
    print(f"📊 結果: {passed_count}/{total_count} 成功")
    
    # 結果を JSON で保存
    RESULTS_DIR = os.path.join(WORKSPACE_ROOT, "docs/regression_test_results")
    os.makedirs(RESULTS_DIR, exist_ok=True)
    
    with open(os.path.join(RESULTS_DIR, "test_order_regression.json"), "w", encoding="utf-8") as f:
        json.dump({
            "file": "order.py",
            "total": total_count,
            "passed": passed_count,
            "results": results,
            "timestamp": datetime.now().isoformat()
        }, f, ensure_ascii=False, indent=2)
    
    sys.exit(0 if passed_count == total_count else 1)
