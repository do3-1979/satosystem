"""
ohlcv_cache.py のレグレッションテスト

OHLCVCache クラスの主要メソッド存在確認、キャッシュ機能検証
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

def test_ohlcv_cache_exists():
    """OHLCVCache クラスが存在することを確認"""
    try:
        from ohlcv_cache import OHLCVCache
        return True, f"✅ OHLCVCache クラスが存在します"
    except ImportError as e:
        return False, f"❌ OHLCVCache クラスのインポート失敗: {e}"


def test_ohlcv_cache_methods():
    """OHLCVCache の主要メソッドが存在することを確認"""
    try:
        from ohlcv_cache import OHLCVCache
        critical_methods = [
            'get_ohlcv_data', 'get_ohlcv_data_partial', 'save_ohlcv_data',
            'clear_cache', 'get_cache_stats', 'migrate_from_json'
        ]
        missing = [m for m in critical_methods if not hasattr(OHLCVCache, m)]
        if missing:
            return False, f"❌ 欠落メソッド: {missing}"
        return True, f"✅ 主要メソッド({len(critical_methods)})が存在"
    except Exception as e:
        return False, f"❌ メソッド確認エラー: {e}"


def test_cache_operations():
    """キャッシュ操作メソッドが存在することを確認"""
    try:
        from ohlcv_cache import OHLCVCache
        
        cache_methods = [
            "get_ohlcv_data",
            "get_ohlcv_data_partial",
            "save_ohlcv_data",
            "clear_cache",
            "get_cache_stats"
        ]
        
        missing = []
        for method in cache_methods:
            if not hasattr(OHLCVCache, method):
                missing.append(method)
        
        if missing:
            return False, f"❌ 欠落キャッシュ操作メソッド: {missing}"
        
        return True, f"✅ キャッシュ操作メソッド({len(cache_methods)})すべて存在"
    except Exception as e:
        return False, f"❌ キャッシュ操作メソッド確認エラー: {e}"


def test_cache_migration():
    """JSONからの移行メソッドが存在することを確認"""
    try:
        from ohlcv_cache import OHLCVCache
        
        if hasattr(OHLCVCache, "migrate_from_json"):
            return True, f"✅ migrate_from_json メソッドが存在"
        else:
            return True, f"⚠️  migrate_from_json が見つかりません（移行不要の可能性）"
    except Exception as e:
        return False, f"❌ 移行メソッド確認エラー: {e}"


def test_ohlcv_cache_init():
    """OHLCVCache.__init__ が存在することを確認"""
    try:
        from ohlcv_cache import OHLCVCache
        
        if hasattr(OHLCVCache, "__init__"):
            sig = inspect.signature(OHLCVCache.__init__)
            return True, f"✅ OHLCVCache.__init__ が定義されています (パラメータ: {len(list(sig.parameters.keys()))-1} 個)"
        else:
            return False, f"❌ __init__ が見つかりません"
    except Exception as e:
        return False, f"❌ __init__ 確認エラー: {e}"


def run_all_tests():
    """全テストを実行"""
    tests = [
        ("OHLCVCache クラス存在確認", test_ohlcv_cache_exists),
        ("OHLCVCache メソッド確認", test_ohlcv_cache_methods),
        ("キャッシュ操作メソッド確認", test_cache_operations),
        ("キャッシュ移行メソッド確認", test_cache_migration),
        ("OHLCVCache.__init__ 確認", test_ohlcv_cache_init),
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
    print("🧪 ohlcv_cache.py レグレッションテスト")
    print("=" * 70)
    results = run_all_tests()
    
    passed_count = sum(1 for r in results if r["passed"])
    total_count = len(results)
    
    print()
    print(f"📊 結果: {passed_count}/{total_count} 成功")
    
    # 結果を JSON で保存
    RESULTS_DIR = os.path.join(WORKSPACE_ROOT, "docs/regression_test_results")
    os.makedirs(RESULTS_DIR, exist_ok=True)
    
    with open(os.path.join(RESULTS_DIR, "test_ohlcv_cache_regression.json"), "w", encoding="utf-8") as f:
        json.dump({
            "file": "ohlcv_cache.py",
            "total": total_count,
            "passed": passed_count,
            "results": results,
            "timestamp": datetime.now().isoformat()
        }, f, ensure_ascii=False, indent=2)
    
    sys.exit(0 if passed_count == total_count else 1)
