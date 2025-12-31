"""
bitget_exchange.py のレグレッションテスト

BitgetExchange クラスの主要メソッド存在確認、取引所機能検証
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

# 分析結果ファイル (bybit版を参照)
ANALYSIS_FILE = os.path.join(WORKSPACE_ROOT, "docs/analysis/bybit_exchange.json")


def load_analysis():
    """analysis/bybit_exchange.json から Exchange クラスの仕様を読む (Bitget も同じ構造)"""
    with open(ANALYSIS_FILE, encoding="utf-8") as f:
        return json.load(f)


def test_bitget_exchange_exists():
    """BitgetExchange クラスが存在することを確認"""
    try:
        from bitget_exchange import BitgetExchange
        return True, f"✅ BitgetExchange クラスが存在します"
    except ImportError as e:
        return False, f"❌ BitgetExchange クラスのインポート失敗: {e}"


def test_bitget_exchange_methods():
    """BitgetExchange の主要メソッドが存在することを確認"""
    try:
        from bitget_exchange import BitgetExchange
        
        # Bybit同様の基本メソッドをチェック
        expected_methods = {
            "__init__",
            "get_account_balance",
            "get_account_balance_total",
            "fetch_ohlcv",
            "fetch_latest_ohlcv",
            "fetch_ticker",
            "execute_order",
            "execute_entry_order",
            "execute_exit_order",
            "fetch_open_orders",
            "create_limit_order",
            "cancel_order"
        }
        
        actual_methods = {m for m in dir(BitgetExchange) if not m.startswith("_") or m == "__init__"}
        
        missing = expected_methods - actual_methods
        if missing:
            return False, f"❌ 欠落メソッド: {missing}"
        
        return True, f"✅ 全メソッド({len(expected_methods)})が存在"
    except Exception as e:
        return False, f"❌ メソッド確認エラー: {e}"


def test_exchange_operations():
    """取引所操作メソッドが存在することを確認"""
    try:
        from bitget_exchange import BitgetExchange
        
        exchange_methods = [
            "get_account_balance",
            "get_account_balance_total",
            "fetch_ohlcv",
            "fetch_latest_ohlcv",
            "fetch_ticker",
            "execute_order",
            "execute_entry_order",
            "execute_exit_order"
        ]
        
        missing = []
        for method in exchange_methods:
            if not hasattr(BitgetExchange, method):
                missing.append(method)
        
        if missing:
            return False, f"❌ 欠落取引所操作メソッド: {missing}"
        
        return True, f"✅ 取引所操作メソッド({len(exchange_methods)})すべて存在"
    except Exception as e:
        return False, f"❌ 取引所操作メソッド確認エラー: {e}"


def test_bitget_exchange_init():
    """BitgetExchange.__init__ が存在することを確認"""
    try:
        from bitget_exchange import BitgetExchange
        
        if hasattr(BitgetExchange, "__init__"):
            sig = inspect.signature(BitgetExchange.__init__)
            params = list(sig.parameters.keys())
            # Bitgetは api_key, api_secret, passphrase の3つのパラメータ
            if 'passphrase' in params:
                return True, f"✅ BitgetExchange.__init__ が定義されています (パラメータ: {len(params)-1} 個、passphrase対応)"
            else:
                return False, f"❌ BitgetExchange.__init__ に passphrase パラメータがありません"
        else:
            return False, f"❌ __init__ が見つかりません"
    except Exception as e:
        return False, f"❌ __init__ 確認エラー: {e}"


def test_api_compatibility():
    """Bitget固有のAPI互換性を確認"""
    try:
        from bitget_exchange import BitgetExchange
        
        # Bitget特有のメソッド
        bitget_specific_methods = [
            "fetch_open_orders",
            "create_limit_order",
            "cancel_order"
        ]
        
        missing = []
        for method in bitget_specific_methods:
            if not hasattr(BitgetExchange, method):
                missing.append(method)
        
        if missing:
            return False, f"❌ 欠落Bitget固有メソッド: {missing}"
        
        return True, f"✅ Bitget固有メソッド({len(bitget_specific_methods)})すべて存在"
    except Exception as e:
        return False, f"❌ Bitget API互換性確認エラー: {e}"


def run_all_tests():
    """全テストを実行"""
    tests = [
        ("BitgetExchange クラス存在確認", test_bitget_exchange_exists),
        ("BitgetExchange メソッド確認", test_bitget_exchange_methods),
        ("取引所操作メソッド確認", test_exchange_operations),
        ("BitgetExchange.__init__ 確認", test_bitget_exchange_init),
        ("Bitget API互換性確認", test_api_compatibility),
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
    print("🧪 bitget_exchange.py レグレッションテスト")
    print("=" * 70)
    results = run_all_tests()
    
    passed_count = sum(1 for r in results if r["passed"])
    total_count = len(results)
    
    print()
    print(f"📊 結果: {passed_count}/{total_count} 成功")
    
    # 結果を JSON で保存
    RESULTS_DIR = os.path.join(WORKSPACE_ROOT, "docs/regression_test_results")
    os.makedirs(RESULTS_DIR, exist_ok=True)
    
    with open(os.path.join(RESULTS_DIR, "test_bitget_exchange_regression.json"), "w", encoding="utf-8") as f:
        json.dump({
            "file": "bitget_exchange.py",
            "total": total_count,
            "passed": passed_count,
            "results": results,
            "timestamp": datetime.now().isoformat()
        }, f, ensure_ascii=False, indent=2)
    
    sys.exit(0 if passed_count == total_count else 1)
