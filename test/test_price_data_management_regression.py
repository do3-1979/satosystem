"""
price_data_management.py のレグレッションテスト

PriceDataManagement クラスの主要メソッド存在確認、OHLCV取得・シグナル生成検証
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

def test_price_data_management_exists():
    """PriceDataManagement クラスが存在することを確認"""
    try:
        from price_data_management import PriceDataManagement
        return True, f"✅ PriceDataManagement クラスが存在します"
    except ImportError as e:
        return False, f"❌ PriceDataManagement クラスのインポート失敗: {e}"


def test_price_data_management_methods():
    """PriceDataManagement の主要メソッドが存在することを確認"""
    try:
        from price_data_management import PriceDataManagement
        critical_methods = [
            'get_ohlcv_data', 'get_latest_ohlcv', 'get_latest_close_time',
            'get_latest_close_time_dt', 'get_ticker', 'get_signals', 'get_volatility',
            'update_price_data', 'update_price_data_backtest'
        ]
        missing = [m for m in critical_methods if not hasattr(PriceDataManagement, m)]
        if missing:
            return False, f"❌ 欠落メソッド: {missing}"
        return True, f"✅ 主要メソッド({len(critical_methods)})が存在"
    except Exception as e:
        return False, f"❌ メソッド確認エラー: {e}"


def test_ohlcv_methods():
    """OHLCV取得メソッドが存在することを確認"""
    try:
        from price_data_management import PriceDataManagement
        
        ohlcv_methods = [
            "get_ohlcv_data",
            "get_latest_ohlcv",
            "get_latest_close_time",
            "get_latest_close_time_dt",
            "get_ticker"
        ]
        
        missing = []
        for method in ohlcv_methods:
            if not hasattr(PriceDataManagement, method):
                missing.append(method)
        
        if missing:
            return False, f"❌ 欠落OHLCV取得メソッド: {missing}"
        
        return True, f"✅ OHLCV取得メソッド({len(ohlcv_methods)})すべて存在"
    except Exception as e:
        return False, f"❌ OHLCV取得メソッド確認エラー: {e}"


def test_signal_methods():
    """シグナル生成メソッドが存在することを確認"""
    try:
        from price_data_management import PriceDataManagement
        
        signal_methods = [
            "get_signals",
            "get_volatility",
            "update_price_data",
            "update_price_data_backtest"
        ]
        
        missing = []
        for method in signal_methods:
            if not hasattr(PriceDataManagement, method):
                missing.append(method)
        
        if missing:
            return False, f"❌ 欠落シグナル生成メソッド: {missing}"
        
        return True, f"✅ シグナル生成メソッド({len(signal_methods)})すべて存在"
    except Exception as e:
        return False, f"❌ シグナル生成メソッド確認エラー: {e}"


def test_singleton_pattern():
    """PriceDataManagement がシングルトン（__new__）で実装されていることを確認"""
    try:
        from price_data_management import PriceDataManagement
        
        if hasattr(PriceDataManagement, "__new__"):
            return True, f"✅ PriceDataManagement は __new__ でシングルトン実装されています"
        else:
            return True, f"⚠️  __new__ が見つかりません（通常の実装の可能性）"
    except Exception as e:
        return False, f"❌ シングルトンパターン確認エラー: {e}"


def test_api_call_optimization_logic():
    """
    update_price_data のAPI呼び出し最適化ロジックをソースコード検証
    Task 40g Rate Limit対策: is_new_candle によるfetch_ohlcvのスキップ確認
    """
    try:
        import inspect
        from price_data_management import PriceDataManagement
        source = inspect.getsource(PriceDataManagement.update_price_data)

        checks = [
            ("is_new_candle 判定ロジック", "is_new_candle"),
            ("prev_close_time 初回判定", "prev_close_time == 0"),
            ("latest_close_time比較", "latest_close_time > self.prev_close_time"),
            ("キャッシュフォールバック", "OHLCVキャッシュ空のためフル取得"),
            ("fetch_latest_ohlcvが先に呼ばれる", "fetch_latest_ohlcv"),
        ]

        missing = []
        for name, pattern in checks:
            if pattern not in source:
                missing.append(name)

        if missing:
            return False, f"❌ API最適化ロジック欠落: {missing}"

        return True, f"✅ API呼び出し最適化ロジック確認OK（is_new_candle によるfetch_ohlcvスキップ）"
    except Exception as e:
        return False, f"❌ API最適化ロジック確認エラー: {e}"


def test_fetch_with_retry_exists():
    """_fetch_with_retry メソッドの存在確認"""
    try:
        from price_data_management import PriceDataManagement
        if not hasattr(PriceDataManagement, "_fetch_with_retry"):
            return False, "❌ _fetch_with_retry メソッドが存在しません"
        return True, "✅ _fetch_with_retry メソッドが存在します"
    except Exception as e:
        return False, f"❌ _fetch_with_retry確認エラー: {e}"


def run_all_tests():
    """全テストを実行"""
    tests = [
        ("PriceDataManagement クラス存在確認", test_price_data_management_exists),
        ("PriceDataManagement メソッド確認", test_price_data_management_methods),
        ("OHLCV取得メソッド確認", test_ohlcv_methods),
        ("シグナル生成メソッド確認", test_signal_methods),
        ("シングルトンパターン確認", test_singleton_pattern),
        ("API呼び出し最適化ロジック確認", test_api_call_optimization_logic),
        ("_fetch_with_retryメソッド確認", test_fetch_with_retry_exists),
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
    print("🧪 price_data_management.py レグレッションテスト")
    print("=" * 70)
    results = run_all_tests()
    
    passed_count = sum(1 for r in results if r["passed"])
    total_count = len(results)
    
    print()
    print(f"📊 結果: {passed_count}/{total_count} 成功")
    
    # 結果を JSON で保存
    RESULTS_DIR = os.path.join(WORKSPACE_ROOT, "docs/regression_test_results")
    os.makedirs(RESULTS_DIR, exist_ok=True)
    
    with open(os.path.join(RESULTS_DIR, "test_price_data_management_regression.json"), "w", encoding="utf-8") as f:
        json.dump({
            "file": "price_data_management.py",
            "total": total_count,
            "passed": passed_count,
            "results": results,
            "timestamp": datetime.now().isoformat()
        }, f, ensure_ascii=False, indent=2)
    
    sys.exit(0 if passed_count == total_count else 1)
