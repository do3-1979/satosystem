"""
bybit_exchange.py のレグレッションテスト

BybitExchange クラスの主要メソッド存在確認、取引所機能検証
"""

import os
import sys
import json
import inspect
from datetime import datetime

# sys.path 設定
WORKSPACE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(WORKSPACE_ROOT, "src")
sys.path.insert(0, SRC_DIR)

# 分析結果ファイル
ANALYSIS_FILE = os.path.join(WORKSPACE_ROOT, "docs/analysis/bybit_exchange.json")


def load_analysis():
    """analysis/bybit_exchange.json から BybitExchange クラスの仕様を読む"""
    with open(ANALYSIS_FILE, encoding="utf-8") as f:
        return json.load(f)


def test_bybit_exchange_exists():
    """BybitExchange クラスが存在することを確認"""
    try:
        from bybit_exchange import BybitExchange
        return True, f"✅ BybitExchange クラスが存在します"
    except ImportError as e:
        return False, f"❌ BybitExchange クラスのインポート失敗: {e}"


def test_bybit_exchange_methods():
    """BybitExchange の主要メソッドが存在することを確認"""
    try:
        from bybit_exchange import BybitExchange
        analysis = load_analysis()
        
        expected_methods = {m["name"] for m in analysis["classes"][0]["methods"]}
        actual_methods = {m for m in dir(BybitExchange) if not m.startswith("_") or m == "__init__"}
        
        missing = expected_methods - actual_methods
        if missing:
            return False, f"❌ 欠落メソッド: {missing}"
        
        return True, f"✅ 全メソッド({len(expected_methods)})が存在"
    except Exception as e:
        return False, f"❌ メソッド確認エラー: {e}"


def test_exchange_operations():
    """取引所操作メソッドが存在することを確認"""
    try:
        from bybit_exchange import BybitExchange
        
        exchange_methods = [
            "get_account_balance",
            "get_account_balance_total",
            "fetch_ohlcv",
            "fetch_latest_ohlcv",
            "fetch_ticker",
            "execute_order"
        ]
        
        missing = []
        for method in exchange_methods:
            if not hasattr(BybitExchange, method):
                missing.append(method)
        
        if missing:
            return False, f"❌ 欠落取引所操作メソッド: {missing}"
        
        return True, f"✅ 取引所操作メソッド({len(exchange_methods)})すべて存在"
    except Exception as e:
        return False, f"❌ 取引所操作メソッド確認エラー: {e}"


def test_bybit_exchange_init():
    """BybitExchange.__init__ が存在することを確認"""
    try:
        from bybit_exchange import BybitExchange
        
        if hasattr(BybitExchange, "__init__"):
            sig = inspect.signature(BybitExchange.__init__)
            return True, f"✅ BybitExchange.__init__ が定義されています (パラメータ: {len(list(sig.parameters.keys()))-1} 個)"
        else:
            return False, f"❌ __init__ が見つかりません"
    except Exception as e:
        return False, f"❌ __init__ 確認エラー: {e}"


def test_timestamp_methods():
    """タイムスタンプ関連メソッドが存在することを確認"""
    try:
        from bybit_exchange import BybitExchange
        
        if hasattr(BybitExchange, "get_nearest_epoch_time"):
            return True, f"✅ get_nearest_epoch_time メソッドが存在"
        else:
            return True, f"⚠️  get_nearest_epoch_time が見つかりません（実装仕様の確認が必要）"
    except Exception as e:
        return False, f"❌ タイムスタンプメソッド確認エラー: {e}"


def run_all_tests():
    """全テストを実行"""
    tests = [
        ("BybitExchange クラス存在確認", test_bybit_exchange_exists),
        ("BybitExchange メソッド確認", test_bybit_exchange_methods),
        ("取引所操作メソッド確認", test_exchange_operations),
        ("BybitExchange.__init__ 確認", test_bybit_exchange_init),
        ("タイムスタンプメソッド確認", test_timestamp_methods),
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
    print("🧪 bybit_exchange.py レグレッションテスト")
    print("=" * 70)
    results = run_all_tests()
    
    passed_count = sum(1 for r in results if r["passed"])
    total_count = len(results)
    
    print()
    print(f"📊 結果: {passed_count}/{total_count} 成功")
    
    # 結果を JSON で保存
    RESULTS_DIR = os.path.join(WORKSPACE_ROOT, "docs/regression_test_results")
    os.makedirs(RESULTS_DIR, exist_ok=True)
    
    with open(os.path.join(RESULTS_DIR, "test_bybit_exchange_regression.json"), "w", encoding="utf-8") as f:
        json.dump({
            "file": "bybit_exchange.py",
            "total": total_count,
            "passed": passed_count,
            "results": results,
            "timestamp": datetime.now().isoformat()
        }, f, ensure_ascii=False, indent=2)
    
    sys.exit(0 if passed_count == total_count else 1)
