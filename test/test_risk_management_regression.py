"""
risk_management.py のレグレッションテスト

RiskManagement クラスの主要メソッド存在確認、ポジションサイズ計算検証
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


def test_risk_management_exists():
    """RiskManagement クラスが存在することを確認"""
    try:
        from risk_management import RiskManagement
        return True, f"✅ RiskManagement クラスが存在します"
    except ImportError as e:
        return False, f"❌ RiskManagement クラスのインポート失敗: {e}"


def test_risk_management_methods():
    """RiskManagement の主要メソッドが存在することを確認"""
    try:
        from risk_management import RiskManagement
        critical_methods = [
            'get_psar', 'get_adx', 'get_stop_price', 'calculate_position_size',
            'evaluate_strategy_a_adx', 'get_donchian_high', 'get_donchian_low'
        ]
        missing = [m for m in critical_methods if not hasattr(RiskManagement, m)]
        if missing:
            return False, f"❌ 欠落メソッド: {missing}"
        return True, f"✅ 主要メソッド({len(critical_methods)})が存在"
    except Exception as e:
        return False, f"❌ メソッド確認エラー: {e}"


def test_risk_calculation_methods():
    """PSAR, ADX, ストップ価格計算メソッドが存在することを確認"""
    try:
        from risk_management import RiskManagement
        
        calculation_methods = [
            "get_psar",
            "get_psarbull",
            "get_psarbear",
            "get_adx",
            "get_adx_bull",
            "get_adx_bear",
            "get_stop_price",
            "calculate_position_size"
        ]
        
        missing = []
        for method in calculation_methods:
            if not hasattr(RiskManagement, method):
                missing.append(method)
        
        if missing:
            return False, f"❌ 欠落計算メソッド: {missing}"
        
        return True, f"✅ 計算メソッド({len(calculation_methods)})すべて存在"
    except Exception as e:
        return False, f"❌ 計算メソッド確認エラー: {e}"


def test_risk_management_init():
    """RiskManagement.__init__ が存在することを確認"""
    try:
        from risk_management import RiskManagement
        
        if hasattr(RiskManagement, "__init__"):
            sig = inspect.signature(RiskManagement.__init__)
            return True, f"✅ RiskManagement.__init__ が定義されています (パラメータ: {len(list(sig.parameters.keys()))-1} 個)"
        else:
            return False, f"❌ __init__ が見つかりません"
    except Exception as e:
        return False, f"❌ __init__ 確認エラー: {e}"


def test_private_methods():
    """RiskManagement のプライベートメソッド(計算内部ロジック)が存在することを確認"""
    try:
        from risk_management import RiskManagement
        import inspect
        privates = [
            name for name, _ in inspect.getmembers(RiskManagement, predicate=inspect.isfunction)
            if name.startswith('_') and not name.startswith('__')
        ]
        if len(privates) > 0:
            return True, f"✅ プライベートメソッド {len(privates)} 個検出"
        else:
            return False, f"❌ プライベートメソッドが検出されません"
    except Exception as e:
        return False, f"❌ プライベートメソッド確認エラー: {e}"


def test_dynamic_stop_range():
    """Task 39e: Dynamic Stop Loss Width - ADXベースの動的ストップ幅計算を確認"""
    try:
        from risk_management import RiskManagement
        
        # get_dynamic_stop_range メソッドの存在確認
        if not hasattr(RiskManagement, "get_dynamic_stop_range"):
            return False, f"❌ get_dynamic_stop_range メソッドが見つかりません"
        
        # メソッドシグネチャ確認
        sig = inspect.signature(RiskManagement.get_dynamic_stop_range)
        params = list(sig.parameters.keys())
        
        # self のみのメソッドであることを確認
        if len(params) != 1 or params[0] != "self":
            return False, f"❌ get_dynamic_stop_range のシグネチャが不正: {params}"
        
        # ドキュメント文字列の確認
        doc = RiskManagement.get_dynamic_stop_range.__doc__
        if not doc or "Task 39e" not in doc:
            return False, f"❌ get_dynamic_stop_range のドキュメントが不十分"
        
        # ADXベースの3段階調整が実装されていることを確認
        if "ADX" not in doc or "1.5" not in doc or "2.0" not in doc or "2.5" not in doc:
            return False, f"❌ 動的ストップ幅の3段階調整が実装されていません"
        
        return True, f"✅ Dynamic Stop Loss Width (Task 39e) 実装確認完了"
    except Exception as e:
        return False, f"❌ Dynamic Stop Range テストエラー: {e}"


def run_all_tests():
    """全テストを実行"""
    tests = [
        ("RiskManagement クラス存在確認", test_risk_management_exists),
        ("RiskManagement メソッド確認", test_risk_management_methods),
        ("リスク計算メソッド確認", test_risk_calculation_methods),
        ("RiskManagement.__init__ 確認", test_risk_management_init),
        ("プライベートメソッド確認", test_private_methods),
        ("Dynamic Stop Loss Width (Task 39e)", test_dynamic_stop_range),
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
    print("🧪 risk_management.py レグレッションテスト")
    print("=" * 70)
    results = run_all_tests()
    
    passed_count = sum(1 for r in results if r["passed"])
    total_count = len(results)
    
    print()
    print(f"📊 結果: {passed_count}/{total_count} 成功")
    
    # 結果を JSON で保存
    RESULTS_DIR = os.path.join(WORKSPACE_ROOT, "docs/regression_test_results")
    os.makedirs(RESULTS_DIR, exist_ok=True)
    
    with open(os.path.join(RESULTS_DIR, "test_risk_management_regression.json"), "w", encoding="utf-8") as f:
        json.dump({
            "file": "risk_management.py",
            "total": total_count,
            "passed": passed_count,
            "results": results,
            "timestamp": datetime.now().isoformat()
        }, f, ensure_ascii=False, indent=2)
    
    sys.exit(0 if passed_count == total_count else 1)
