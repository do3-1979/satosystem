"""
複合テスト：exchange, order, metrics, util, event, side

小規模なクラス・モジュールの統合テスト
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

ANALYSIS_DIR = os.path.join(WORKSPACE_ROOT, "docs/analysis")


def test_exchange_base_class():
    """Exchange 基底クラスが存在することを確認"""
    try:
        from exchange import Exchange
        
        if hasattr(Exchange, "__init__") and hasattr(Exchange, "get_account_balance"):
            return True, f"✅ Exchange 基底クラスが存在（__init__, get_account_balance）"
        else:
            return False, f"❌ Exchange 基底クラスが不完全"
    except ImportError as e:
        return False, f"❌ Exchange のインポート失敗: {e}"


def test_order_dto():
    """Order DTO クラスが存在することを確認"""
    try:
        from order import Order
        
        required = ["__init__", "to_dict"]
        missing = [m for m in required if not hasattr(Order, m)]
        
        if missing:
            return False, f"❌ Order DTO が不完全: {missing}"
        else:
            return True, f"✅ Order DTO が存在（__init__, to_dict）"
    except ImportError as e:
        return False, f"❌ Order のインポート失敗: {e}"


def test_metrics_functions():
    """Metrics の compute_metrics 関数が存在することを確認"""
    try:
        from metrics import compute_metrics
        
        if callable(compute_metrics):
            return True, f"✅ compute_metrics 関数が存在"
        else:
            return False, f"❌ compute_metrics が実行可能でない"
    except ImportError as e:
        return False, f"❌ Metrics のインポート失敗: {e}"


def test_util_class():
    """Util クラスが存在することを確認"""
    try:
        from util import Util
        
        required = ["extract_and_export_logs", "generate_line_chart"]
        missing = [m for m in required if not hasattr(Util, m)]
        
        if missing:
            return False, f"❌ Util クラスが不完全: {missing}"
        else:
            return True, f"✅ Util クラスが存在（主要メソッド確認）"
    except ImportError as e:
        return False, f"❌ Util のインポート失敗: {e}"


def test_event_bus():
    """EventBus クラスが存在することを確認"""
    try:
        from event import EventBus
        
        required = ["subscribe", "unsubscribe", "emit"]
        missing = [m for m in required if not hasattr(EventBus, m)]
        
        if missing:
            return False, f"❌ EventBus が不完全: {missing}"
        else:
            return True, f"✅ EventBus が存在（subscribe, unsubscribe, emit）"
    except ImportError as e:
        return False, f"❌ EventBus のインポート失敗: {e}"


def test_side_functions():
    """Side 関数（normalize_side, to_exchange_side）が存在することを確認"""
    try:
        from side import normalize_side, to_exchange_side
        
        if callable(normalize_side) and callable(to_exchange_side):
            return True, f"✅ Side 関数が存在（normalize_side, to_exchange_side）"
        else:
            return False, f"❌ Side 関数が実行可能でない"
    except ImportError as e:
        return False, f"❌ Side のインポート失敗: {e}"


def run_all_tests():
    """全テストを実行"""
    tests = [
        ("Exchange 基底クラス確認", test_exchange_base_class),
        ("Order DTO 確認", test_order_dto),
        ("Metrics 関数確認", test_metrics_functions),
        ("Util クラス確認", test_util_class),
        ("EventBus クラス確認", test_event_bus),
        ("Side 関数確認", test_side_functions),
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
    print("🧪 補足的なクラス・関数レグレッションテスト")
    print("=" * 70)
    results = run_all_tests()
    
    passed_count = sum(1 for r in results if r["passed"])
    total_count = len(results)
    
    print()
    print(f"📊 結果: {passed_count}/{total_count} 成功")
    
    # 結果を JSON で保存
    RESULTS_DIR = os.path.join(WORKSPACE_ROOT, "docs/regression_test_results")
    os.makedirs(RESULTS_DIR, exist_ok=True)
    
    with open(os.path.join(RESULTS_DIR, "test_supplementary_regression.json"), "w", encoding="utf-8") as f:
        json.dump({
            "file": "exchange, order, metrics, util, event, side",
            "total": total_count,
            "passed": passed_count,
            "results": results,
            "timestamp": datetime.now().isoformat()
        }, f, ensure_ascii=False, indent=2)
    
    sys.exit(0 if passed_count == total_count else 1)
